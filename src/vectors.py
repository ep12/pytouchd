import math

class vec(object):
    def __init__(self, coords: tuple):
        assert isinstance(coords, (tuple, list))
        assert len(coords) > 0
        assert all([isinstance(x, (int, float, complex)) for x in coords])
        if isinstance(coords, list):
            self.coordinates = coords
        else:
            self.coordinates = list(coords)
    
    def compatible(self, other, typematch=False):
        if not isinstance(self, vec):
            return False
        if not isinstance(other, (vec, list, tuple)):
            return False
        if not len(self) == len(other):
            return False
        if typematch and not all([type(x) == type(y) for x, y in zip(self, other)]):
            return False
        if typematch and not all([isinstance(x, type(self[0])) for x in self]):
            return False
        return True
        
    def __add__(self, other):
        assert vec.compatible(self, other), '%r and %r are not compatible!' % (self, other)
        return vec([x + y for x, y in zip(list(self), list(other))])
        
    def __radd__(self, other):
        return vec.__add__(self, other)
    
    def __sub__(self, other):
        assert vec.compatible(self, other), '%r and %r are not compatible!' % (self, other)
        return vec([x - y for x, y in zip(list(self), list(other))])
    
    def __rsub__(self, other):
        return vec.__sub__(self, other)
    
    def __mul__(self, other):
        assert isinstance(self, vec)
        assert isinstance(other, (float, int, complex, vec))
        if isinstance(other, vec):
            return sum([x * y for x, y in zip(list(self), list(other))])
        else:
            return vec([x * other for x in self])
    
    def __rmul__(a, b):
        if isinstance(a, vec) and isinstance(b, (int, float, complex)):
            return a.__mul__(b)
        elif isinstance(b, vec) and isinstance(a, (int, float, complex)):
            return b.__mul__(a)
        elif isinstance(a, vec) and isinstance(b, vec):
            return sum([x * y for x, y in zip(list(a), list(b))])
        else:
            raise TypeError('Incompatible types %r and %r' % (type(a), type(b)))
    
    def __pow__(self, other):
        if isinstance(self, vec) and isinstance(other, (int, float, complex)):
            return vec([x ** other for x in self])
        else:
            raise TypeError('Incompatible types %r and %r' % (type(a), type(b)))
        
    def __neg__(self):
        assert isinstance(self, vec)
        return vec([-x for x in self])
    
    def __int__(self):
        assert isinstance(self, (vec, list, tuple)), 'Wrong input type'
        return vec([int(x) for x in self])
    
    def __round__(self):
        assert isinstance(self, (vec, list, tuple)), 'Wrong input type'
        return vec([round(x) for x in self])

    def __eq__(self, other):
        assert vec.compatible(self, other), '%r and %r are not compatible!' % (self, other)
        return all([x == y for x, y in zip(self, other)])
    
    def __ge__(self, other):
        assert vec.compatible(self, other), '%r and %r are not compatible!' % (self, other)
        return vec([x >= y for x, y in zip(self, other)])
        
    def __len__(self):
        assert isinstance(self, vec)
        return len(self.coordinates)
    
    def __iter__(self):
        assert isinstance(self, vec)
        self.itervar = 0
        return self
        
    def __next__(self):
        assert isinstance(self, vec)
        if not hasattr(self,'itervar'):
            raise IndexError
        if self.itervar < len(self.coordinates):
            self.itervar += 1
            return self.coordinates[self.itervar - 1]
        else:
            del(self.itervar)
            # raise IndexError
            raise StopIteration
    
    def __getitem__(self, val):
        assert isinstance(self, vec)
        if isinstance(val, slice):
            raise NotImplemented
        elif isinstance(val, int):
            if val < len(self) and val >= 0:
                return self.coordinates[val]
            else:
                raise IndexError
        else:
            raise IndexError
    
    def __str__(self):
        assert isinstance(self, vec)
        return 'vec%d(%s)' % (len(self), ', '.join([str(x) for x in self]))
        
    def __repr__(self):
        return '<vec%d id="%s" type="%s" length="%s"\n coordinates="%s">' % \
          (len(self), hex(id(self)), type(self[0]), self.length, ', '.join([str(x) for x in self]))

    def __list__(self):
        assert isinstance(self, vec)
        return self.coordinates
    
    @property
    def length(self):
        return sum(self ** 2) ** 0.5
    
    def angle(self, other, *, absmode=False, diffmode=False, todegrees=False):
        '''
        '''
        assert vec.compatible(self, other), '%r and %r are not compatible!' % (self, other)
        a = self * other
        b = self.length * other.length
        if b == 0:
            raise ValueError('null vector!')
        if absmode:
            a = abs(a)
        if diffmode:
            alpha = math.asin(a / b)
        else:
            alpha = math.acos(a / b)
        if todegrees:
            alpha = math.degrees(alpha)
        return alpha
    
    def cross(self, other):
        assert vec.compatible(self, other), '%r and %r are not compatible!' % (self, other)
        vl = len(self)
        tmp = [0 for x in range(vl)]
        for i in range(len(tmp)):
            tmp[i] = self[(i + 1) % vl] * other[(i + 2) % vl] - self[(i + 2) % vl] * other[(i + 1) % vl]
        return vec(tmp)
    
    def dot(self, other):
        return self * other
    
    def area(self, other):
        return self.cross(other).length
 
    @property
    def isNullVector(self):
        return self.length == 0.0
