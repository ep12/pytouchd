#!/usr/bin/python3
import os
import sys
import math
import signal
import atexit
from gc import collect
from time import sleep, time as now
from argparse import ArgumentParser as ap

from psutil import pid_exists

from src.vectors import vec
from src.touchInput import getEvent
from src.touchIntermediate import touchEvt
from src.touchOutput import touchOut
from src.config import readConfig, writeConfig

if __name__ == '__main__':
    rdir = os.path.dirname(os.path.realpath(__file__))

def single(value):
    if isinstance(value, (list, tuple)):
        return value[0]
    else:
        return value

def handleEvent(event):
    global tout
    tout.handle(event)
    collect()

if __name__ == '__main__':
    isroot = os.getuid() is 0
    pidfile = '/tmp/pytouchd.pid'
    byteorder = 'big'  # sys.byteorder

    p = ap(
        prog='touchd',
        description='a adaptive touch driver (e.g. for ODROID VU7 Plus)',
        conflict_handler='resolve',
    )
    p.add_argument(
        'action',
        choices=['start', 'stop', 'status', 'zombie'],
        help='start the daemon or stop the running instance',
        action='store'
    )
    p.add_argument(
        '--device', '-d',
        help='path to the device, e.g. /dev/hidraw0',
        action='store',
        type=str,
        nargs=1,
        default='/dev/hidraw0'
    )
    p.add_argument(
        '--debug', '-D',
        help='enable debug output',
        action='store_true',
        default=False
    )
    p.add_argument(
        '--show-config',
        dest='show_config',
        action='store_true',
        default=False,
        help='Show configuration details'
    )
    p.add_argument(
        '--config',
        help='specify an alternative config file',
        action='store',
        nargs=1,
        default='touchd.ini'
    )

    args = p.parse_args()

    action = single(args.action)
    device = single(args.device)
    debug = args.debug

    if action == 'zombie':
        if os.path.isfile(pidfile):
            os.remove(pidfile)
        action = 'start'

    if action == 'stop':
        if os.path.isfile(pidfile):
            print('Stopping daemon...')
            with open(pidfile) as f:
                pid = int(f.read())
            os.kill(pid, signal.SIGTERM)
            exit(0)
        else:
            print('No daemon running!')
            exit(1)

    if action == 'status':
        if os.path.isfile(pidfile):
            print('pidfile %r exists' % pidfile)
            with open(pidfile) as f:
                pid = f.read()
            if pid_exists(int(pid)):
                print('process with pid %r exists!' % pidfile)
            elif isroot:
                print('process with pid %r does not exist, removing pidfile' % pid)
                os.remove(pidfile)
            else:
                print('process with pid %r does not exist!' % pid)
        else:
            print('pidfile does not exist, the daemon is not running')
        exit(0)

    # else: start daemon:

    if not isroot:
        print('Must be root!')
        exit(1)

    if os.path.isfile(pidfile):
        with open(pidfile) as f:
            pid = f.read()
        if pid_exists(int(pid)):
            print('Daemon already running!')
            exit(2)
        else:
            os.remove(pidfile)

    with open(pidfile, 'w') as f:
        f.write(str(os.getpid()))
        os.chmod(pidfile, 0o666)

    if not os.path.isfile(pidfile):
        print('Could not create PID file!')
        exit(3)

    cpath, cfg = readConfig(rdir, args.config)
    if args.show_config:
        print(cfg)
    rawBuffer = []
    bpc = None
    coordmode = None  # 0->%, 1->absolute
    minPoints, maxPoints, numPoints = 5, 8, None  # how many touch points
    allowZeroLine = True  # allow aa 00 00 .. bb 00 00 .. with 00 instead of cc
    minLen, maxLen = 5 + minPoints * [bpc, 1][bpc is None], 5 + maxPoints * [bpc, 2][bpc is None]
    Len = None
    tout = touchOut(cfg)
    s = now()
    exitreason = None

    ## for i in range(maxPoints):
        ## devs.append(emulatedDevice(i))
        ## sleep(0.2)

    @atexit.register
    def prepareExit():
        global tout, pidfile, exitreason
        signal.alarm(0)
        tout.close()
        if os.path.isfile(pidfile):
            os.remove(pidfile)
        if exitreason is None:
            print('EXITING FOR NO APPARENT REASON!')
            exit(255)
        else:
            print(exitreason)
            print('Good-bye.')
    
    def timeout(sig, frame):
        raise TimeoutError('input timed out')

    def stop(sig, frame):
        global pidfile, exitreason
        try:
            exitreason = 'STOP requested - SIGTERM'
            os.remove(pidfile)
        except Exception:
            pass

    def handleFatal(err):
        global exitreason
        import traceback
        etype, evalue, etb = sys.exc_info()
        fmt = traceback.format_exc()
        exitreason = 'FATAL: %r (file %r, line %s)\n%s' % (str(err), etb.tb_frame.f_code.co_filename, etb.tb_lineno, fmt)

    if debug:
        print('opening device %r' % device)
    with open(device, 'rb') as f:
        try:
            signal.signal(signal.SIGALRM, timeout)
            signal.signal(signal.SIGTERM, stop)
            while True:  # os.path.isfile(pidfile):
                if not os.path.isfile(pidfile):
                    if exitreason is None:
                        exitreason = 'STOP requested - pidfile deleted'
                if exitreason is not None:
                    break
                signal.alarm(1)
                try:
                    print(str(int(now()))[-3:], end='\r')
                    rawBuffer.append(f.read(1))
                    signal.alarm(0)
                except TimeoutError as err:
                    print('##', end='\r')
                    # releaseAll()
                    collect()
                if Len is None:
                    if rawBuffer and rawBuffer[-1] == b'\xcc':
                        success, event, Len, rawBuffer = getEvent(rawBuffer)
                        if debug:
                            print('Set Len to %d' % Len)
                        if event is not None:
                            handleEvent(event)
                elif len(rawBuffer) >= Len:
                    success, event, Len, rawBuffer = getEvent(rawBuffer)
                    if bpc is None and success:
                        bpc, coordmode, numPoints = event.details
                    if not success:
                        pass
                        exitreason = 'getEvent() failed'
                    elif event is not None:
                        handleEvent(event)
        except KeyboardInterrupt:
            print('\rKeyboardInterrupt. Exiting...')
            exitreason = 'KeyboardInterrupt'
        except Exception as err:
            handleFatal(err)

    
