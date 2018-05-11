#!/usr/bin/python3
import os
import sys
import math
import signal
from gc import collect
from time import sleep, time as now
from argparse import ArgumentParser as ap

import numpy as np
from evdev import UInput, AbsInfo, ecodes as e


class touchEvt(object):
    '''class touchEvt(object)
    A class describing touch events
    '''
    def __init__(self, absmode: bool, bpc, press: bool, aIDs: list, coordinates: list):
        '''touchEvt(absmode: bool, bpc, press: bool, aIDs: list, coordinates:list)
        Inititalises the class object with:
            - absmode: False for percentage, True for absolute mode
            - bpc: bytes per co-ordinate (normally 1 or 2)
            - press: whether the screen was touched or released
            - aIDs: a list of bools representing how many touches were registered
            - coordinates: a list of tuples (x, y) of bytes objects.
        '''
        assert isinstance(absmode, bool)
        assert isinstance(bpc, int) and bpc > 0
        assert isinstance(press, bool)
        assert isinstance(aIDs, list)
        assert isinstance(coordinates, list)
        assert len(aIDs) is len(coordinates)
        if len(aIDs) > 0:
            assert all(isinstance(x, bool) for x in aIDs)
            assert all(isinstance(x, tuple) and len(x) is 2 for x in coordinates)
            assert all(isinstance(y, int) for x in coordinates for y in x)
        self.bpc = bpc
        self.abs = absmode
        self.press = press
        if not press:
            self.aIDs = [False for x in range(len(aIDs))]
        else:
            self.aIDs = aIDs
        self.rawCoords = coordinates

    @property
    def absCoordinates(self):
        if self.abs:
            return [(int(pt[0]), int(pt[1])) for pt in self.rawCoords]
        else:
            import screeninfo
            monitor = screeninfo.get_monitors()[0]
            width, height = monitor.width, monitor.height
            return [(int(pt[0]) * width // 255, int(pt[1]) * height // 255) for pt in self.rawCoords]
    
    @property
    def relCoordinates(self):
        if self.abs:
            import screeninfo
            monitor = screeninfo.get_monitors()[0]
            width, height = monitor.width, monitor.height
            return [(int(pt[0]) / width, int(pt[1]) / height) for pt in self.rawCoords]
        else:
            return [(int(pt[0]) / 255, int(pt[1]) / 255) for pt in self.rawCoords]

    def activeCoordinates(self, absmode):
        from itertools import compress
        if absmode:
            return list(compress(self.absCoordinates, self.aIDs))
        else:
            return list(compress(self.relCoordinates, self.aIDs))

    def getState(self, id):
        try:
            return (*self.absCoordinates[id], self.aIDs[id])
        except IndexError:
            return None
        
    def __str__(self):
        tmp = ['released', 'pressed %s' % ', '.join(str(x) for x in self.activeCoordinates(True))]
        return tmp[self.press]

    @property
    def details(self):
        return self.bpc, self.absmode, len(self.rawCoords)
    
    @property
    def release(self):
        return self.press is False


class emulatedDevice(object):
    presstime = 0.2
    dragdist = 20  # = 0.5 cm for ODROID VU7+
    cap = {
            e.EV_KEY: [e.BTN_MOUSE],
            e.EV_ABS: [
                (e.ABS_X, AbsInfo(value=0, min=0, max=1023, fuzz=0, flat=0, resolution=0)),
                (e.ABS_Y, AbsInfo(value=0, min=0, max=599, fuzz=0, flat=0, resolution=0))
            ]
    }

    def __init__(self, id):
        print('Creating emulated touch device #%d' % id)
        self.id = id
        self.dev = UInput(self.cap, name='pytouchd-emutouchdev-%d' % id, version=0x0001)
        self.state = (0, 0, 0)  # (x, y, pressed)
        self.keydownstamp = None
        self.movebuffer = []

    def handle(self, event, runBufferMode=False):
        assert isinstance(event, touchEvt)
        newstate = event.getState(self.id)
        if newstate is None:
            return
        oldx, oldy, oldactive = self.state
        newx, newy, newactive = newstate
        if newactive and not oldactive:
            # initial press:
            self.keydownstamp = now()
            self.move(newx, newy)
            self.press()
        elif oldactive and not newactive:
            # final release
            self.release()
        elif oldactive and newactive:
            # move / keep / gesture
            if now() > self.keydownstamp + self.presstime \
              or runBufferMode \
              or math.sqrt(abs(newx - oldx) ** 2 + abs(newy - oldy) ** 2) > self.dragdist:
                # only move if not released
                if not runBufferMode:
                    self.runBuffer()
                self.move(newx, newy)
            else:
                self.movebuffer.append(event)
        else:
            self.release()

    def close(self):
        global debug
        if debug:
            print('Closing emulated touch device #%d' % self.id)
        self.dev.close()
        del(self)

    def release(self, quiet=False):
        global debug
        if debug and not quiet:
            print('REL #%d' % self.id)
        self.dev.write(e.EV_KEY, e.BTN_MOUSE, 0)
        self.dev.syn()
        self.state = (self.state[0], self.state[1], 0)

    def press(self, quiet=False):
        global debug
        if debug and not quiet:
            print('PRS #%d' % self.id)
        self.dev.write(e.EV_KEY, e.BTN_MOUSE, 1)
        self.dev.syn()
        self.state = (self.state[0], self.state[1], 1)

    def move(self, x, y, quiet=False):
        global debug
        if debug and not quiet:
            print('MOV #%d, (%d, %d)' % (self.id, x, y))
        self.dev.write(e.EV_ABS, e.ABS_X, x)
        self.dev.write(e.EV_ABS, e.ABS_Y, y)
        self.dev.syn()
        self.state = (x, y, self.state[2])

    def runBuffer(self):
        global debug
        if debug:
            print('BUF #%d' % self.id)
        for event in self.movebuffer:
            self.handle(event, True)
        self.movebuffer = []

def readCoord(buffer, ctr, bpc, invert=True):
    global byteorder
    a = int.from_bytes(b''.join(buffer[ctr:ctr + bpc]), byteorder)
    ctr += bpc
    b = int.from_bytes(b''.join(buffer[ctr:ctr + bpc]), byteorder)
    ctr += bpc
    return (a, b)[::1 - 2 * invert], ctr

def getEvent(buffer):
    global bpc, coordmode, numPoints, allowZeroLine
    global minPoints, maxPoints
    global debug
    global byteorder

    s = ''.join(chr(int.from_bytes(x, byteorder)) for x in buffer)
    coords = []
    tmp = 0
    event = None

    start = s.index(chr(0xaa))
    tmp = start + 1
    pressflag = bool(int.from_bytes(buffer[tmp], byteorder))
    tmp += 1

    mid = s.index(chr(0xbb), start + 4)
    if bpc is None:
        if (mid - start - 2) % 2 == 1:
            return False, None, None, buffer
        bpc = (mid - start - 2) // 2
        if debug:
            print('Set bpc to %d' % bpc)
    if coordmode is None:
        coordmode = bpc is 2
        if debug:
            print('Set absmode to %s' % coordmode)
   
    pt, tmp = readCoord(buffer, tmp, bpc, False)
    coords.append(pt)

    if tmp is not mid:
        print('tmp != mid', buffer)
        return False, None, None, buffer
    tmp += 1

    activeFlags = int.from_bytes(buffer[tmp], byteorder)
    active = [bool(activeFlags & 2 ** x) for x in range(8)]
    tmp += 1

    checkForZero = False
    if numPoints is None:
        i = 1
        while i <= maxPoints:
            if buffer[tmp] == b'\xcc':
                if debug:
                    print('Set numPoints to %d' % i)
                numPoints = i
                break
            i += 1
            pt, tmp = readCoord(buffer, tmp, bpc)
            coords.append(pt)
    else:
        for i in range(numPoints - 1):
            pt, tmp = readCoord(buffer, tmp, bpc)
            coords.append(pt)
        if not buffer[tmp] == b'\xcc':
            checkForZero = True

    tmp += 2  # start of next possible event
    if checkForZero:
        ref = 'aa' + '00' * (2 * bpc + 1) + 'bb' + '00' * (2 * bpc * (numPoints - 1) + 2)
    if checkForZero and not allowZeroLine:
        return False, None, None, buffer
    elif checkForZero and allowZeroLine:
        if b''.join(buffer[start:tmp]).hex() == ref:
            # okay:
            event = touchEvt(coordmode, bpc, False, [], [])
        else:
            print(b''.join(buffer[start:tmp]).hex())
            print(ref)
    else:
        event = touchEvt(coordmode, bpc, pressflag, active[:numPoints], coords)
    
    buffer = buffer[tmp:]
    return True, event, tmp - start - 1, buffer


def handleEvent(event):
    global devs
    print('Handling event %s' % event)

    for x in devs:
        x.handle(event)
    collect()

def releaseAll():
    global devs
    for x in devs:
        x.release(True)

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
        choices=['start', 'stop', 'zombie'],
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

args = p.parse_args()

action = args.action
if isinstance(action, list):
    action = action[0]
device = args.device
if isinstance(device, list):
    device = device[0]
debug = args.debug

if action == 'zombie':
    if os.path.isfile(pidfile):
        os.remove(pidfile)
    action = 'start'

if action == 'stop':
    if os.path.isfile(pidfile):
        print('Stopping daemon...')
        os.remove(pidfile)
        exit(0)
    else:
        print('No daemon running!')
        exit(1)

# else: start daemon:

if os.path.isfile(pidfile):
    print('Daemon already running!')
    exit(2)

if not isroot:
    print('Must be root!')
    exit(3)

with open(pidfile, 'w') as f:
    f.writelines('pid=%d' % os.getpid())

if not os.path.isfile(pidfile):
    print('Could not create PID file!')
    exit(4)

rawBuffer = []
bpc = None
coordmode = None  # 0->%, 1->absolute
minPoints, maxPoints, numPoints = 5, 8, None  # how many touch points
allowZeroLine = True  # allow aa 00 00 .. bb 00 00 .. with 00 instead of cc
minLen, maxLen = 5 + minPoints * [bpc, 1][bpc is None], 5 + maxPoints * [bpc, 2][bpc is None]
Len = None
devs = []
s = now()
for i in range(maxPoints):
    devs.append(emulatedDevice(i))
    sleep(0.2)

def timeout(sig, frame):
    raise TimeoutError('input timed out')

if debug:
    print('opening device %r' % device)
with open(device, 'rb') as f:
    try:
        signal.signal(signal.SIGALRM, timeout)
        while True:  # os.path.isfile(pidfile):
            if not os.path.isfile(pidfile):
                print('STOP requested')
                break
            signal.alarm(1)
            try:
                print(int(now()), end='\r')
                rawBuffer.append(f.read(1))
                print(str(now()).ljust(18, '0'), end=' ')
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
                    break
                elif event is not None:
                    handleEvent(event)
    except KeyboardInterrupt:
        print('\rKeyboardInterrupt. Exiting...')
    except Exception as err:
        raise err

signal.alarm(0)
for x in devs:
    x.close()
if os.path.isfile(pidfile):
    os.remove(pidfile)
print('Good-bye')
