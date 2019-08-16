from common.types.boolean import *

class OnOff(Boolean):
    def __init__(self, val):
        Boolean.__init__(self, val, STYLE_ONOFF)

class OneZero(Boolean):
    def __init__(self, val):
        Boolean.__init__(self, val, STYLE_ONEZERO)

class YesNo(Boolean):
    def __init__(self, val):
        Boolean.__init__(self, val, STYLE_YESNO)

class HighLow(Boolean):
    def __init__(self, val):
        if isinstance(val, str):
            val = val.lower()
            if val == "high":
                val = True
        Boolean.__init__(self, val, STYLE_ONOFF)

    def __repr__(self):
        if self._Boolean__value:
            return "High"
        else:
            return "Low"

    __str__ = __repr__

class OpenClosed(Boolean):
    def __init__(self, val):
        if isinstance(val, str):
            val = val.lower()
            if val == "closed":
                val = True
        Boolean.__init__(self, val, STYLE_ONOFF)

    def __repr__(self):
        if self._Boolean__value:
            return "Closed"
        else:
            return "Open"

    __str__ = __repr__

class SinkSourceTristate:
    def __init__(self, val):
        if isinstance(val, str):
            val = val.lower()
            if val == "sink"[:len(val)]:
                val = 0
            elif val == "source"[:len(val)]:
                val = 1
            elif val == "tristate"[:len(val)]:
                val = 2
        self.__value = val

    def __repr__(self):
        if self.__value == 0:
            return "Sink"
        elif self.__value == 1:
            return "Source"
        elif self.__value == 2:
            return "Tristate"

    __str__ = __repr__

    def __int__(self):
        return self.__value

    def __coerce__(self, other):
        if type(other) == int:
            return (self.__value, other)
        elif type(other) == float:
            return (float(self.__value), other)

class gpioFloat:
    def __init__(self, value):
        try:
            self.value = float(value)
        except:
            self.value = 0.0

    def __float__(self):
        return self.value

    def range_check(self, low, high):
        if self.value < low:
            self.value = low
            return -1
        if self.value > high:
            self.value = high
            return 1
        return 0


    def __repr__(self):
        return '%g' % self.value

    __str__ = __repr__
