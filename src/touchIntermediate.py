from time import time as now

import screeninfo

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
        assert isinstance(absmode, bool), 'absmode must be a boolean value, not %s' % type(absmode)
        assert isinstance(bpc, int) and bpc > 0, 'bpc must be a positive, non-zero integer, not %r' % bpc
        assert isinstance(press, bool), 'press must be a boolean value, not %s' % type(press)
        assert isinstance(aIDs, list), 'aIDs must be of type list, not %s' % type(aIDs)
        assert isinstance(coordinates, list), 'coordinates must be a list, not %s' % type(coordinates)
        assert len(aIDs) is len(coordinates), 'len(aIDs) must be len(coordinates): %d != %d' % (len(aIDs), len(coordinates))
        if len(aIDs) > 0:
            assert all(isinstance(x, (bool, int)) for x in aIDs), 'aIDs elements must be int or bool: %r' % aIDs
            assert all(isinstance(x, tuple) and len(x) is 2 for x in coordinates), 'coordinates elements must be tuples: %r' % coordinates
            assert all(isinstance(y, int) for x in coordinates for y in x), 'coordinates elements must be tuples of type int'
        else:
            raise ValueError('empty input arguments!')
        self.time = now()
        self.bpc = bpc
        self.absmode = absmode
        self.pressed = press
        # if not press:
        #     self.aIDs = [False for x in range(len(aIDs))]
        # else:
        self.aIDs = aIDs
        self.rawCoords = coordinates

    @property
    def absCoordinates(self):
        if self.absmode:
            return [(int(pt[0]), int(pt[1])) for pt in self.rawCoords]
        else:
            monitor = screeninfo.get_monitors()[0]
            width, height = monitor.width, monitor.height
            return [(int(pt[0]) * width // 255, int(pt[1]) * height // 255) for pt in self.rawCoords]
    
    @property
    def relCoordinates(self):
        if self.absmode:
            monitor = screeninfo.get_monitors()[0]
            width, height = monitor.width, monitor.height
            return [(int(pt[0]) / width, int(pt[1]) / height) for pt in self.rawCoords]
        else:
            return [(int(pt[0]) / 255, int(pt[1]) / 255) for pt in self.rawCoords]

    # @property
    def activeCoordinates(self, absmode):
        from itertools import compress
        if absmode:
            return list(compress(self.absCoordinates, self.aIDs))
        else:
            return list(compress(self.relCoordinates, self.aIDs))

    def getState(self, id=None):
        try:
            if id is None:
                return [(*self.absCoordinates[id], self.aIDs[id]) for id in range(len(self.aIDs))]
            else:
                return (*self.absCoordinates[id], self.aIDs[id])
        except IndexError as e:
            print(self.rawCoords)
            print(self.absCoordinates)
            print(self.aIDs)
            print(repr(self))
            print('DICT DUMP:')
            for k, v in self.__dict__.items():
                print('  {0!r:<10}: {1!r}'.format(k, v))
            raise e
            return (-1, -1, 0)

    @property
    def activeCount(self):
        return sum(self.aIDs)
        
    def __str__(self):
        tmp = ['released', 'pressed coords=%r' % ', '.join(str(x) for x in self.activeCoordinates(True))]
        return 'Event (%f) %s' % (self.time, tmp[self.press])

    def __repr__(self):
        return '<touchEvt id=%r time=%r coords=%r>' % \
          (hex(id(self)), self.time, ', '.join(str(x) for x in self.activeCoordinates(True)))

    @property
    def details(self):
        return self.bpc, self.absmode, len(self.rawCoords)
    
    @property
    def release(self):
        return self.pressed is False

    @property
    def press(self):
        return self.pressed is True

    def absX(self, id):
        return self.absCoordinates[id][0]
    
    def absY(self, id):
        return self.absCoordinates[id][1]

    def absXY(self, id):
        return self.absCoordinates[id]
