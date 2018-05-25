from .touchIntermediate import touchEvt

byteorder = 'big'

# TODO options integration
bpc = None
coordmode = None
numPoints = None
allowZeroLine = True
minPoints = 5
maxPoints = 8
debug = True


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

    if tmp is not mid and buffer[tmp].hex() != 'bb':
        print('tmp != mid', b''.join(buffer).hex())
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
            event = touchEvt(coordmode, bpc, False,
                    [False for x in range(numPoints)], [(0, 0) for x in range(numPoints)])
        else:
            print(b''.join(buffer[start:tmp]).hex())
            print(ref)
    else:
        if len(active[:numPoints]) != len(coords):
            print('ERROR:\n active=%r\ncoords=%r' % (active[:numPoints], coords))
        event = touchEvt(coordmode, bpc, pressflag, active[:numPoints], coords)
    
    buffer = buffer[tmp:]
    return True, event, tmp - start - 1, buffer
