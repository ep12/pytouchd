import re
from time import time as now

from evdev import UInput, AbsInfo, ecodes as e
import screeninfo

from .typehelper import guess, get
from .touchIntermediate import touchEvt
from .vectors import vec
debug = False

DBL   = 0b0001
MULTI = 0b0010
LONG  = 0b0100
DRAG  = 0b1000


class touchOut(object):
    def __init__(self, options, amount=8):
        if not options.hasValue('pixW') or not options.hasValue('pixH'):
            try:
                monitor = screeninfo.get_monitors()[0]
            except NotImplementedError:
                monitor = screeninfo.Monitor(0, 0, 1920, 1080)
            options.setv('pixW', monitor.width)
            options.setv('pixH', monitor.height)
        self.opt = options
        ppmmX, ppmmM, ppmmY = self.ppmm
        self.opt.setv('ppmmX', ppmmX)
        self.opt.setv('ppmmMean', ppmmM)
        self.opt.setv('ppmmY', ppmmY)

        self.ebuffer = []
        self.mode = 0b0000

        self.devs = []
        for i in range(amount):
            tmp = emulatedDevice(i)
            tmp.options = self.opt
            self.devs.append(tmp)
            self.__dict__['dev%d' % i] = tmp
        self.dead = None
        self.lastPress = 0.0
        self.pressPos1 = vec([0, 0])
        self.pressPos2 = vec([0, 0])
        self.lastEvent = touchEvt(True, 1, False, [0 for x in self.devs], [(0, 0) for x in self.devs])
        self.lastState = [(0, 0, 0) for x in self.devs]
        self.relMove = vec([0, 0])
        global debug
        debug = options.get('debug', False)

    @property
    def ppmm(self):
        w = self.opt['pixW'] / self.millimeters(self.opt['devW'])
        h = self.opt['pixH'] / self.millimeters(self.opt['devH'])
        return (w, h, (w + h) / 2)
        
    def pixels(self, value):
        if isinstance(value, str):
            m = re.fullmatch('(?P<value>\\d+) ?(?P<unit>[a-z]*)', value)
            if bool(m):
                d = m.groupdict()
                v = d.get('value')
                u = d.get('unit')
                if u in ['PX', 'px']:
                    return int(v)
                elif u == 'cm':
                    return int(float(v) * self.ppmm[2] * 10)
                elif u == 'mm':
                    return int(float(v) * self.ppmm[2] * 25.4)
                elif u == 'in':
                    return int(float(v) * self.ppmm[2])
                else:
                    raise ValueError('Unknown unit %r' % u)
            else:
                raise ValueError('%r cannot be parsed!' % value)
        else:
            return value
    
    def millimeters(self, value):
        if isinstance(value, str):
            m = re.fullmatch('(?P<value>[\\d]+[,.]?[\\d]*) ?(?P<unit>[a-z]*)', value)
            if bool(m):
                d = m.groupdict()
                v = d.get('value')
                u = d.get('unit')
                if u == 'in':
                    return float(v) * 25.4
                elif u == 'cm':
                    return float(v) * 10
                elif u == 'mm':
                    return float(v)
                else:
                    raise ValueError('Unknown unit %r' % u)
            else:
                raise ValueError('%r cannot be parsed!' % value)
        else:
            return value
    
    def close(self):
        for x in self.devs:
            x.close()
    
    def releaseAll(self, quiet=False):
        for x in self.devs:
            x.release(quiet=quiet)
    
    def passThrough(self, event, bufferMode=False):
        global debug
        if debug:
            print('PASSTHROUGH')
        if not bufferMode and self.ebuffer:
            if debug:
                print('BUFFER playback')
            for e in self.ebuffer:
                self.passThrough(e, True)
            self.ebuffer = []
        for id, state in enumerate(event.getState()):
            x, y, a = state
            if a:
                self.devs[id].move(x, y)
                self.devs[id].press()
            else:
                self.devs[id].release()

    def handle(self, event):
        global debug
        if self.dead is not None:
            if now() < self.dead + self.opt.get('gestureDeadTime', 0.1):
                if debug:
                    print('discarding event %s' % event)

                    return
            else:
                self.dead = None

        if self.lastEvent.release and event.release:
            self.releaseAll(quiet=True)
            return
        state = event.getState()
        x0, y0, _ = event.getState(0)
        x1, y1, _ = event.getState(1)
        ox0, oy0, _ = self.lastEvent.getState(0)
        ox1, oy1, _ = self.lastEvent.getState(1)
        print(str(now()).ljust(18, '0') + ' tOut: Handling %s' % event)
        
        if self.opt.get('live', vtype=bool):
            self.passThrough(event)
        elif (event.activeCount is 1 and not self.mode & MULTI) \
          or (event.activeCount is 0 and self.lastEvent.activeCount is 1):
            # sglClick event:
            # NOTE: if one touch point is still active although one or more other points are released, the event
            # is still a press event but the activeCount has changed. As an indicator, MULTI is used because it is
            # set when a 2 pt gesture is registered
            if event.press and not self.lastEvent.press:
                if debug:
                    print('raw: press')
                if event.time - self.lastPress < self.opt.get('dblClickTime') \
                  and (vec([ox0, oy0]) - vec(self.devs[0].state[:2])).length < self.pixels(self.opt.get('dragDist')):
                    self.mode ^= DBL
                    if debug:
                        print('enh: dblClick started')
                self.lastPress = event.time
                self.pressPos1 = vec(event.absXY(0))
            elif event.release:
                if debug:
                    print('raw: release')
                if bool(self.mode & DRAG) ^ bool(not self.mode & DBL):
                    if not self.mode & DRAG:
                        self.pressPos2 = vec(self.lastEvent.absXY(0))
                        x, y = tuple(round(self.pressPos1 + 0.5 * (self.pressPos2 - self.pressPos1)))
                        if debug:
                            print('enh: position interpolated: (%d, %s)' % (x, y))
                    else:
                        x, y = self.lastEvent.absXY(0)
                    self.devs[0].move(x, y)
                if not self.mode & DRAG:
                    if self.mode & LONG and self.opt.get('holdForRightClick'):
                        if debug:
                            print('enh: long click -> right click')
                        self.devs[0].press(key=e.BTN_RIGHT)
                    else:
                        self.devs[0].press()
                self.devs[0].release()
                
                self.mode = 0b0000
                self.relMove = vec([0, 0])
            else:
                self.relMove += vec([x0 - ox0, y0 - oy0])
                if not self.mode & DRAG:
                    if self.relMove.length > self.pixels(self.opt.get('dragDist')):
                        if debug:
                            print('enh: entering DRAG mode')
                        self.mode ^= DRAG
                        self.passThrough(event)
                    if not self.mode & DRAG and now() - self.lastPress > self.opt.get('longClickTime'):
                        if debug:
                            print('enh: LONG click detected')
                        self.mode ^= LONG
                if self.mode & DRAG:
                    self.passThrough(event)
                else:
                    self.ebuffer.append(event)
        elif (event.activeCount is 1 and self.mode & MULTI) \
          or (event.release and self.mode & MULTI and self.lastEvent.activeCount is 2):
            self.pressPos2 = [vec(self.lastEvent.absXY(0)), vec(self.lastEvent.absXY(1))]
            if debug:
                print('enh: end 2ptGesture')
            v1, v2 = self.relMove[0], self.relMove[1]
            if v1.isNullVector or v2.isNullVector:
                if debug:
                    print('ERR: Null vector detected!')
                    print('v1:\n%r\nv2:\n%r' % (v1, v2))
                    print('|v1|=%f\n|v2|=%f' % (v1.length, v2.length))
            else:
                alpha = v1.angle(v2, todegrees=True)
                if debug:
                    print('enh: angle between vectors: %d °' % alpha)
                if abs(alpha - 180) < self.opt.get('pinchAngleThreshold', 30):
                    # pinch
                    d1 = (self.pressPos1[0] - self.pressPos1[1]).length
                    d2 = (self.pressPos2[0] - self.pressPos2[1]).length
                    k = d2 / d1 
                    p = k * 100
                    if debug:
                        print('enh: pinch detected: %f -> %f (%f %%)' % (d1, d2, p))
                    nclicks = int(eval(self.opt.get('pinchToZoomClicksFormula', '1', vtype=str)))
                    if debug:
                        print('enh: clicking ZOOM%s %d times' % (['OUT', 'IN'][k > 1.0], nclicks))
                    if self.opt.get('zoomModeCtrlPlusMinus', True):
                        #
                        self.devs[0].press(e.KEY_LEFTCTRL)
                        self.devs[0].press(e.KEY_LEFTCTRL, value=2)
                        if k < 1.0:
                            for click in range(nclicks):
                                self.devs[0].press(key=e.KEY_SLASH)
                                self.devs[0].release()
                        elif k > 1.0:
                            for click in range(nclicks):
                                self.devs[0].press(key=e.KEY_RIGHTBRACE)
                                self.devs[0].release()
                        self.devs[0].release(key=e.KEY_LEFTCTRL)
                    else:
                        if k < 1.0:
                            for click in range(nclicks):
                                self.devs[0].press(key=e.KEY_ZOOMIN)
                                self.devs[0].release()
                        elif k > 1.0:
                            for click in range(nclicks):
                                self.devs[0].press(key=e.KEY_ZOOMOUT)
                                self.devs[0].release()
                elif alpha < self.opt.get('parallelAngleThreshold', 30):
                    vm = 0.5 * (v1 + v2)
                    l = vm.length
                    nscroll = int(eval(self.opt.get('scrollAmountFormula', 'l / 10')))
                    nscrollh = int(eval(self.opt.get('horScrollAmountFormula', 'l / 15')))
                    nmove = int(eval(self.opt.get('moveGestureFormula', 'l / 10')))
                    if debug:
                        print('enh: ean movement: %r' % vm)

                    # Note: inverse! Finger from top to bottom means a ScrollUp
                    beta_up = vm.angle(vec([0, 1]), todegrees=True)
                    beta_down = vm.angle(vec([0, -1]), todegrees=True)
                    beta_left = vm.angle(vec([1, 0]), todegrees=True)
                    beta_right = vm.angle(vec([-1, 0]), todegrees=True)

                    dt = self.opt.get('directionAngleThreshold', 15)  # max angle between gesture mean and axis
                    if beta_up < dt:
                        if debug:
                            print('enh: ScrollUp %d' % nscroll)
                        self.devs[0].scroll(nscroll)
                    elif beta_down < dt:
                        if debug:
                            print('enh: ScrollDown %d' % nscroll)
                        self.devs[0].scroll(-nscroll)
                    elif beta_left < dt:
                        if self.opt.get('enableHorizontalScroll', True):
                            if debug:
                                print('enh: ScrollLeft %d' % nscrollh)
                            self.devs[0].scroll(-nscrollh, horizontal=True)
                        else:
                            if debug:
                                print('enh: left')
                            self.devs[0].press(key=e.KEY_LEFT)
                            self.devs[0].release()
                    elif beta_right < dt:
                        if self.opt.get('enableHorizontalScroll', True):
                            if debug:
                                print('enh: ScrollRight %d' % nscrollh)
                            self.devs[0].scroll(nscrollh, horizontal=True)
                        else:
                            if debug:
                                print('enh: right')
                            self.devs[0].press(key=e.KEY_RIGHT)
                            self.devs[0].release()
                    else:
                        if debug:
                            print('enh: unhandled diagonal gesture')

            self.relMove = vec([0, 0])
            self.pressPos1 = vec([0, 0])
            self.pressPos2 = vec([0, 0])
            self.mode = 0
            self.dead = now()
        elif event.activeCount is 2:
            if not self.mode & MULTI:
                if debug:
                    print('enh: entering 2ptGesture mode')
                self.ebuffer = []
                self.mode ^= MULTI
                self.pressPos1 = [vec(event.absXY(0)), vec(event.absXY(1))]
                self.relMove = [vec([0, 0]), vec([0, 0])]
            else:
                self.relMove[0] += vec([x0 - ox0, y0 - oy0])
                self.relMove[1] += vec([x1 - ox1, y1 - oy1])
        else:
            if debug:
                print('raw: %d active touch input points' % event.activeCount)
        self.lastEvent = event
        self.lastState = state

        
class emulatedDevice(object):
    cap = {
            e.EV_KEY: [e.BTN_MOUSE, e.BTN_WHEEL, e.BTN_MIDDLE, e.BTN_RIGHT, e.BTN_SIDE,
                e.KEY_ZOOM, e.KEY_ZOOMIN, e.KEY_ZOOMOUT, e.KEY_ZOOMRESET,
                e.KEY_LEFTCTRL, e.KEY_SLASH, e.KEY_RIGHTBRACE,
                e.KEY_LEFT, e.KEY_UP, e.KEY_RIGHT, e.KEY_DOWN],
            e.EV_ABS: [
                (e.ABS_X, AbsInfo(value=0, min=0, max=1023, fuzz=0, flat=0, resolution=0)),
                (e.ABS_Y, AbsInfo(value=0, min=0, max=599, fuzz=0, flat=0, resolution=0))
            ],
            e.EV_REL: [
                e.REL_WHEEL, e.REL_HWHEEL
            ],
            e.EV_MSC: [e.MSC_SCAN]
    }
    def __init__(self, id):
        print('Creating emulated touch device #%d' % id)
        self.id = id
        self.dev = UInput(self.cap, name='pytouchd-emutouchdev-%d' % id, version=0x0001)
        self.state = (0, 0, 0)  # (x, y, which key pressed)
        self.keydownstamp = None
        self.movebuffer = []

    def close(self):
        global debug
        if debug:
            print('Closing emulated touch device #%d' % self.id)
        self.dev.close()
        del(self)

    def release(self, key=None, quiet=False):
        global debug
        if not self.state[2] and key is None:
            return
        if debug and not quiet:
            print('REL #%d' % self.id)
        if key is None:
            key = self.state[2]
            noupdate = True
        else:
            noupdate = False
        self.dev.write(e.EV_KEY, key, 0)
        self.dev.syn()
        if not noupdate:
            self.state = (self.state[0], self.state[1], 0)

    def press(self, key=e.BTN_MOUSE, quiet=False, *, value=1):
        global debug
        if not key in self.cap[e.EV_KEY]:
            raise ValueError('Keycode %d is not valid!' % key)
        if debug and not quiet:
            print('PRS #%d, %d' % (self.id, key))
        self.dev.write(e.EV_KEY, key, value)
        self.dev.syn()
        self.state = (self.state[0], self.state[1], key)

    def move(self, x, y, quiet=False):
        global debug
        if debug and not quiet:
            print('MOV #%d, (%d, %d)' % (self.id, x, y))
        self.dev.write(e.EV_ABS, e.ABS_X, x)
        self.dev.write(e.EV_ABS, e.ABS_Y, y)
        self.dev.syn()
        self.state = (x, y, self.state[2])

    def scroll(self, amount, horizontal=False):
        if horizontal:
            wheel = e.REL_HWHEEL
        else:
            wheel = e.REL_WHEEL
        self.dev.write(e.EV_REL, wheel, amount)
        self.dev.syn()

    def runBuffer(self):
        global debug
        if debug:
            print('BUF #%d' % self.id)
        for event in self.movebuffer:
            # TODO new-old handle function
            self.handle(event, True)
        self.movebuffer = []

    #def handle(self, event, runBufferMode=False):
    #    assert isinstance(event, touchEvt)
    #    newstate = event.getState(self.id)
    #    if newstate is None:
    #        return
    #    oldx, oldy, oldactive = self.state
    #    newx, newy, newactive = newstate
    #    if newactive and not oldactive:
    #        # initial press:
    #        self.keydownstamp = now()
    #        self.move(newx, newy)
    #        self.press()
    #    elif oldactive and not newactive:
    #        # final release
    #        self.release()
    #    elif oldactive and newactive:
    #        # move / keep / gesture
    #        if now() > self.keydownstamp + self.presstime \
    #          or runBufferMode \
    #          or math.sqrt(abs(newx - oldx) ** 2 + abs(newy - oldy) ** 2) > self.dragdist:
    #            # only move if not released
    #            if not runBufferMode:
    #                self.runBuffer()
    #            self.move(newx, newy)
    #        else:
    #            self.movebuffer.append(event)
    #    else:
    #        self.release()
