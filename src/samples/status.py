############################################################################
#                                                                          #
# Copyright (c)2011 Digi International (Digi). All Rights Reserved.        #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. ContactProduct Management, Digi International, Inc., 11001 Bren    #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""\
Status to assign to a data sample.
"""

# imports
import types
import sample

# constants
# lowest 8 bits define 'BadData' - generally hardware errors, disabled etc
# such data is probably meaningless; for example a '0' reading of a broken
# sensor doesn't mean it is zero (0) degrees outside
STS_NOSUPPORTED =     0x00000000 # no support, value is meaningless

STS_MASK_DISABLE =    0x00000001 # source is disabled
STS_MASK_FAULT =      0x00000002 # some low-level HW fault; device specfic
STS_MASK_OFFLINE =    0x00000004 # source is unavailable (timeout - offline, etc)
STS_MASK_OVERRANGE =  0x00000010 # source is above permitted range-of-operation
STS_MASK_UNDERRANGE = 0x00000020 # source is below permitted range-of-operation
STS_MASK_NOT_INIT =   0x00000040 # the data has never been set
STS_MASK_RES_BD =     0x000000C8 # (reserved)
STS_MASK_BADDATA =    0x000000FF # these are internal data alarms

STS_MASK_QUAL_UNK =   0x00000100 # data is of unknown quality - ex: last poll timed out
STS_MASK_QUAL_LOW =   0x00000200 # data is of known low quality - ex: indirectly cal'd
STS_MASK_MANUAL =     0x00000400 # at least 1 input is in Manual mode when Auto is preferred
STS_MASK_CLAMPHIGH =  0x00001000 # data was forced high due to system fault
STS_MASK_CLAMPLOW =   0x00002000 # data was forced low due to system fault
STS_MASK_RES_QA =     0x0000C800 # (reserved)
STS_MASK_SOSODATA  =  0x0000FF00 # these are internal process 'conditions'

STS_MASK_DIGITAL =    0x00010000 # digital NOT in desired state
STS_MASK_RES_AL =     0x00020000 # (reserved)
STS_MASK_LO =         0x00040000 # normal/expected low alarm (warning)
STS_MASK_LOLO =       0x00080000 # abnormal/unexpected too-low alarm (error/alarm)
STS_MASK_ROC_NOR =    0x00100000 # normal/expected rate-of-change alarm  (warning)
STS_MASK_ROC_AB =     0x00200000 # abnormal/unexpected rate-of-change alarm (error/alarm)
STS_MASK_HI =         0x00400000 # normal/expected high alarm (warning)
STS_MASK_HIHI =       0x00800000 # abnormal/unexpected too-high alarm (error/alarm)
STS_MASK_ALARMS =     0x00FF0000 # These are External Process Alarms

STS_MASK_ABNORM =     0x01000000 # first sample after go to alarm
STS_MASK_RTNORM =     0x02000000 # first sample after a return to normal of any alarm
STS_MASK_VALID =      0x80000000 # status field is valid/upsupported if 1
STS_MASK_RES_EV =     0xF8000000 # (reserved)

QUALITY_GOOD = STS_MASK_VALID
QUALITY_BAD = STS_MASK_BADDATA
   
# exception classes

def DataStatus_clr_bits(sam, bits):
    """using bit-mask, clear bits"""
    if isinstance(sam, sample.Sample):
        sam.status &= ~bits
        sam.status |= STS_MASK_VALID
        return sam.status
    # else assume is an int
    sam &= ~bits
    sam |= STS_MASK_VALID
    return sam

def DataStatus_set_bits(sam, bits):
    """using bit-mask, set bits"""
    if isinstance(sam, sample.Sample):
        sam.status |= (bits | STS_MASK_VALID)
        return sam.status
    # else assume is an int
    sam |= (bits | STS_MASK_VALID)
    return sam
        
def DataStatus_set(sam, bits):
    """completely set/replace value"""
    if isinstance(sam, sample.Sample):
        sam.status = (bits | STS_MASK_VALID)
        return sam.status
    # else assume is an int
    sam = (bits | STS_MASK_VALID)
    return sam

def DataStatus_is_valid(sam):
    """return if bits indicate status is supported"""
    if isinstance(sam, sample.Sample):
        return bool(sam.status & STS_MASK_VALID)
    # else assume is an int
    return bool(sam & STS_MASK_VALID)

def DataStatus_mark_valid(sam):
    if isinstance(sam, sample.Sample):
        sam.status |= STS_MASK_VALID
        return sam.status
    # else assume is an int
    sam |= STS_MASK_VALID
    return sam

# classes
class DataStatus(object):

    # Using slots saves memory by keeping __dict__ undefined.
    __slots__ = ["status"]

    def __init__(self, status=STS_NOSUPPORTED):
        self.status = status

    def __repr__(self):
        return "Status=0x%08X" % self.status

    def __int__(self):
        """return as int"""
        return int(self.status)

    def clr_bits(self, bits):
        """using bit-mask, clear bits"""
        self.status &= ~bits
        self.status |= STS_MASK_VALID

    def set_bits(self, bits):
        """using bit-mask, set bits"""
        self.status |= (bits | STS_MASK_VALID)

    def set(self, bits):
        """completely set/replace value"""
        self.status = (bits | STS_MASK_VALID)

    def is_valid(self):
        """return if bits indicate status is supported"""
        return bool(self.status & STS_MASK_VALID)

    def mark_valid(self):
        """set the is_valid bit"""
        self.status |= STS_MASK_VALID
        
class DataQuality(DataStatus):
 
    STS_SHORTNAME = { \
        STS_MASK_DISABLE:'dis', STS_MASK_FAULT:'flt', STS_MASK_OFFLINE:'ofl', 
        STS_MASK_OVERRANGE:'ovr', STS_MASK_UNDERRANGE:'udr', STS_MASK_NOT_INIT:'N/A',
        STS_MASK_QUAL_UNK:'unq', STS_MASK_QUAL_LOW:'loq', 
        STS_MASK_MANUAL:'man', STS_MASK_CLAMPHIGH:'clh',
        STS_MASK_CLAMPLOW:'cll', STS_MASK_DIGITAL:'dig', 
        STS_MASK_LO:'low', STS_MASK_LOLO:'llo',
        STS_MASK_ROC_NOR:'roc', STS_MASK_ROC_AB:'rab',
        STS_MASK_HI:'hig', STS_MASK_HIHI:'hhi',
        STS_MASK_ABNORM:'abn', STS_MASK_RTNORM:'rtn',
        STS_MASK_VALID:'val',
        }

    STS_FULLNAME = { \
        STS_MASK_DISABLE:'disabled', STS_MASK_FAULT:'fault', 
        STS_MASK_OFFLINE:'offline', STS_MASK_NOT_INIT:'not-initialized',
        STS_MASK_OVERRANGE:'over-range', STS_MASK_UNDERRANGE:'under-range',
        STS_MASK_QUAL_UNK:'unknown-quality', STS_MASK_QUAL_LOW:'low-quality', 
        STS_MASK_MANUAL:'manual', STS_MASK_CLAMPHIGH:'clamp-high',
        STS_MASK_CLAMPLOW:'clamp-low', STS_MASK_DIGITAL:'digital', 
        STS_MASK_LO:'low', STS_MASK_LOLO:'low-low',
        STS_MASK_ROC_NOR:'rate-of-change', STS_MASK_ROC_AB:'rate-of-change-abnorm',
        STS_MASK_HI:'high', STS_MASK_HIHI:'high-high',
        STS_MASK_ABNORM:'go-abnormal', STS_MASK_RTNORM:'return-to-normal',
        STS_MASK_VALID:'status-valid',
        }

    def __init__(self, status=STS_MASK_VALID):
        DataStatus.__init__(self, status)

    def __repr__(self):
        return "Status=0x%08X" % self.status

    def one_bit_to_tag(self, bit):
        """Given a single bit-mask, return the tag/mnemonic"""
        return self.STS_SHORTNAME.get( bit, None)

    def one_bit_to_name(self, bit):
        """Given a single bit-mask, return the long name"""
        return self.STS_FULLNAME.get( bit, None)

    def all_bits_to_tag(self, bits, long_name=False):
        """Cycle through all bits, returning a tag/mnemonic string"""
        if not (bits & STS_MASK_VALID):
            return "unsupported"
            
        if bits == STS_MASK_VALID:
            return "ok"
        
        # else at least one bit is true, so continue
        st = []
        n = 1
        bFirst = True
        while n != 0x80000000:
            if bits & n:
                # then this bit is true, so add the tag
                if long_name:
                    tag = self.one_bit_to_name(n)
                else:
                    tag = self.one_bit_to_tag(n)
                if tag is not None:
                    if bFirst:
                        bFirst = False
                    else:
                        st.append( ',')
                    st.append(tag)
            # cycle through all the bits
            n <<= 1
        return "".join(st)
        
    def clr_tags(self, tag):
        """use the 3-ch tags to clear some bits"""
        if isinstance(tag, types.StringType):
            tag = tag.split(',')
        # else hope is list of tags
        bits = 0
        for tg in tag:
            bits |= self.tag_to_one_bit(tg)
        self.clr_bits(bits)

    def set_tags(self, tag):
        """use the 3-ch tags to set some bits"""
        if isinstance(tag, types.StringType):
            tag = tag.split(',')
        # else hope is list of tags
        bits = 0
        for tg in tag:
            bits |= self.tag_to_one_bit(tg)
        self.set_bits(bits)

    def set(self, tag):
        """return as int"""
        bits = tag
        if isinstance(tag, types.StringType):
            tag = tag.split(',')
            # else hope is list of tags
            bits = 0
            for tg in tag:
                bits |= self.tag_to_one_bit(tg)
        DataStatus.set(self, bits)
        
    def tag_to_one_bit(self, tag):
        """Given string name, return alarm mask"""
        tag = tag.lower()
        if(tag == 'good'):
            return 0
        for k,v in self.STS_SHORTNAME.items():
            # first loop and look for a custom name
            if v == tag:
                return k
        # if no custom name, use defaults
        return None

# internal functions & classes
