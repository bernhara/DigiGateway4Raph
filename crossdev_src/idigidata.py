from _idigi_data import *

def send_to_idigi (data, filename, collection, secure=True):
    return send_idigi_xml (data, filename, collection, secure)
        
if __name__ == '__main__':
    pass