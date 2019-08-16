# $Id: __init__.py 1405 2014-12-03 16:37:14Z orba6563 $

import codecs
import sys

# check if 'hex' is available
__hex_available = True
try:
    codecs.lookup('hex')
except LookupError:
    __hex_available = False
    
if not __hex_available:
    
    # from python library sources...

    import binascii
    
    ### Codec APIs
    
    def my_hex_encode(input,errors='strict'):
    
        """ Encodes the object input and returns a tuple (output
            object, length consumed).
    
            errors defines the error handling to apply. It defaults to
            'strict' handling which is the only currently supported
            error handling for this codec.
    
        """
        assert errors == 'strict'
        output = binascii.b2a_hex(input)
        return (output, len(input))
    
    def my_hex_decode(input,errors='strict'):
    
        """ Decodes the object input and returns a tuple (output
            object, length consumed).
    
            input must be an object which provides the bf_getreadbuf
            buffer slot. Python strings, buffer objects and memory
            mapped files are examples of objects providing this slot.
    
            errors defines the error handling to apply. It defaults to
            'strict' handling which is the only currently supported
            error handling for this codec.
    
        """
        assert errors == 'strict'
        output = binascii.a2b_hex(input)
        return (output, len(input))
        class Codec(codecs.Codec):
    
        def encode(self, input,errors='strict'):
            return my_hex_encode(input,errors)
        def decode(self, input,errors='strict'):
            return my_hex_decode(input,errors)
    
    class MyHexStreamWriter(Codec,codecs.StreamWriter):
        pass
    
    class MyHexStreamReader(Codec,codecs.StreamReader):
        pass
    
    def find_my_hex(encoding):
        """Return my new codec if 'hex' is seached.
        """
        if encoding == 'hex':
            return (my_hex_encode,my_hex_decode,MyHexStreamReader,MyHexStreamWriter)
        return None   
    # register the search function for my hex
    codecs.register(find_my_hex)
    
    # try to load encoding again to check if 'hex' has been correctly registered
    try:
        codecs.lookup('hex')
        # FIXME: remove logs
        print >> sys.stderr, 'Added hex encoding'
    except LookupError:
        print >> sys.stderr, 'Tried to defined our own hex encoding, by could not loaded it'
        

            

