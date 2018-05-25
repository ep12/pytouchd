import re
from os import curdir
from os.path import realpath, isfile, join
from collections import namedtuple

from .typehelper import guess, get
# from configparser import ConfigParser as cp
#
item = namedtuple('item', ['indentwidth', 'type', 'name', 'value', 'ilcomment'])  # TODO continuation

class Configuration(object):
    def __init__(self, filepath=None, *,
          lineends='\n',
          allowSpaces=True,
          assignChars=':=',
          commentChars='#;',
          allowInlineComments=True,
          allowContinuation=True
          ):
        self.path = filepath
        self.lineends = lineends
        self.allowSpaces = allowSpaces
        self.assignChars = assignChars
        self.commentChars = commentChars
        self.allowInlineComments = allowInlineComments
        self.allowContinuation = allowContinuation
        self.struct = []
        self.data = {
            'default': {}
        }

    def read(self):
        assert isfile(self.path), '%r is not a file!' % self.path

        sRE = self.sectionRE
        nRE = self.nameRE
        aRE = self.assignRE
        vRE = self.valueRE

        lineRE = nRE + aRE + vRE
        
        with open(self.path) as f:
            data = f.read()
        lines = data.split(self.lineends)
        name, value = None, None
        section = 'default'
        for l in lines:
            llstrip = l.lstrip()
            indentw = len(l) - len(llstrip)
            lcont = l.endswith('\\') and self.allowContinuation
            iscomment = any([llstrip.startswith(x) for x in self.commentChars])
            if iscomment:
                self.struct.append(item(indentw, 'comment', llstrip, None, None))
                continue
            
            sect = re.fullmatch(sRE, llstrip)
            value = re.fullmatch(lineRE, llstrip)

            if bool(sect):
                d = sect.groupdict()
                section = d['name']
                if section not in self.data.keys():
                    self.data[section] = {}
                self.struct.append(item(indentw, 'section', section, None, d.get('r', '')))
            elif bool(value):
                d = value.groupdict()
                name = d['name']
                val = d['value']
                if self.allowInlineComments:
                    indexes = [val.find(x) for x in self.commentChars]
                    i = min([[x, len(l)][x is -1] for x in indexes])
                    if i == len(l):
                        # no comment
                        val, comment = val, None
                    else:
                        val, comment = val[:i].rstrip(), val[i + 1:]
                else:
                    val, comment = val, None
                self.struct.append(item(indentw, 'value', name, val, comment))
                self.data[section][name] = guess(val)
    
    @property
    def sectionRE(self):
        return '\[(?P<name>[^\]]+)\](?P<r>.*)'

    @property
    def nameRE(self):
        return '(?P<name>[\\w' + ' ' * self.allowSpaces + ']+)'

    @property
    def assignRE(self):
        return ' ' * self.allowSpaces + '[%s]' % self.assignChars + ' ' * self.allowSpaces

    @property
    def valueRE(self):
        return '(?P<value>.*)'
                
    def hasValue(self, value):
        for s in self.data.keys():
            if value in self.data[s].keys():
                return True
        return False

    def get(self, value, fallback='', *, vtype=None, section=None):
        # TODO a more forgiving version searching for unique names
        if section is not None:
            return self.getv(value, section=section, vtype=vtype, fallback=fallback)
        v, count = None, 0
        for s in self.data.keys():
            if value in self.data[s].keys():
                v = self.getv(value, section=s, vtype=vtype, fallback=fallback)
                count += 1
        if count is 1:
            return v
        elif count is 0:
            return fallback
        else:
            raise IndexError('%r exists in %d sections!' % (value, count))


    def getv(self, value, *, section='default', vtype=None, fallback=''):
        if value in self.data[section].keys():
            return get(self.data[section][value], vtype, fallback)
        return fallback

    def setv(self, name, value, section='default'):
        if section not in self.data.keys():
            self.data[section] = {}
        self.data[section][name] = value

    def __str__(self):
        l = ['<Configuration id=%r path=%r>' % (hex(id(self)), self.path)]

        for s in self.data.keys():
            l.append('    Section %r:' % s)
            for p in self.data[s].items():
                l.append('        %r = %r' % p)

        return '\n'.join(l)
    
    def __getitem__(self, s):
        if isinstance(s, slice):
            start, stop, step = s.start, s.stop, s.step
            if stop is None:
                return self.get(start)
            else:
                return self.getv(stop, section=start)
        else:
            return self.get(s)

    def __setitem__(self, s, value):
        if isinstance(s, slice):
            start, stop, step = s.start, s.stop, s.step
            if stop is None:
                self.setv(start, value)
            else:
                self.setv(stop, value, section=start)
        else:
            self.setv(s, value)

def readConfig(basepath, filename):
    cwd = realpath(curdir)

    fp = join(cwd, filename)
    if not isfile(fp):
        fp = join(basepath, filename)
        if not isfile(fp):
            print('Could not read config!')
            return fp, {}
    # TODO
    cfg = Configuration(fp)

    # defaults / fallback
    cfg.setv('devW', '16cm')
    cfg.setv('devH', '9cm')
    cfg.setv('dragDist', 30)
    cfg.setv('enhSglClick', False)
    cfg.setv('enhDblClick', False)
    cfg.setv('holdForRightClick', False)
    cfg.setv('pinchToZoom', False)
    cfg.setv('sglClickTime', 0.2)
    cfg.setv('dblClickTime', 0.4)
    cfg.setv('rightClickDelay', 0.4)
    cfg.setv('pinchScale', 1.0)
    cfg.setv('live', False) 
    cfg.read()
    
    return fp, cfg

def writeConfig(filepath, config):
    pass
