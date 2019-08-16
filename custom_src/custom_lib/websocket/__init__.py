# $Id: __init__.py 1398 2014-12-03 15:48:54Z orba6563 $

import codecs
import sys

# check if 'utf-8' is available
__utf8_available = True
try:
    codecs.lookup('utf-8')
except LookupError:
    __utf8_available = False
    
if not __utf8_available:
    
    # from python library sources...
    
    my_utf8_encode = codecs.utf_8_encode
    
    def my_utf8_decode(input, errors='strict'):
        print 'my_utf8_encode'
        return codecs.utf_8_decode(input, errors, True)    

    class MyUtf8StreamWriter(codecs.StreamWriter):
        encode = codecs.utf_8_encode
    
    class MyUtf8StreamReader(codecs.StreamReader):
        decode = codecs.utf_8_decode
        
    def find_my_utf8(encoding):
        """Return my new codec if 'utf-8' is seached.
        """
        if encoding == 'utf-8':
            return (my_utf8_encode,my_utf8_decode,MyUtf8StreamReader,MyUtf8StreamWriter)
        return None   

    # register the search fonction for my utf-8
    codecs.register(find_my_utf8)

    # try to load encoding again to check if 'utf-8' has been correctly registered
    try:
        codecs.lookup('utf-8')
        # FIXME: remove logs
        print >> sys.stderr, 'Added utf-8 encoding'
    except LookupError:
        print >> sys.stderr, 'Tried to defind our own utf-8 encoding, by could not loaded it'

