#!/usr/bin/python3
import re

def guess(value: str, *, bools=None):
    '''guess(value: str, *, bools=None)
    '''
    if not isinstance(value, str):
        return value
    assert bools is None or isinstance(bools, dict)

    if bools is None:
        bools = {
            'off': False,
            'false': False,
            '0': False,
            'on': True,
            'true': True,
            '1': True
        }
    if value == '':
        return None
    if value.lower() in bools.keys():
        return bools[value.lower()]
    if bool(re.fullmatch('[+-]?[\\d]+', value)):
        return int(value)
    if bool(re.fullmatch('0x[0-9a-fA-F]+', value)):
        return int(value[2:], 16)
    if bool(re.fullmatch('0b[01]+', value)):
        return int(value[2:], 2)
    if bool(re.fullmatch('[+-]?[\\d]+[\\.]?[\\d ]*', value)):
        return float(value)
    return value

def get(value: str, valtype, fallback, valueOnNone=True):
    '''get(value: str, valtype, fallback, valueOnNone)
    '''
    # assert isinstance(value, str) or value is None, 'value must be a string!'
    assert isinstance(valtype, type) or isinstance(valtype, tuple) or valtype is None

    if valtype is None:
        if valueOnNone:
            return value
        else:
            return None

    if not (isinstance(value, str) or value is None):
        if isinstance(value, valtype):
            return value
        else:
            return get(str(value), valtype, fallback, valueOnNone)
    if isinstance(valtype, tuple):
        assert all([isinstance(x, type) or x is None for x in valtype])
    g = guess(value)
    
    if isinstance(g, valtype):
        return g
    if valtype is int and isinstance(g, float) and g == int(g):
        return int(g)
    if valtype is float and isinstance(g, int):
        return float(g)
    if valtype is str and isinstance(g, (int, float)):
        return str
    return fallback
