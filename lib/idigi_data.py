try:
    import idigidata
    def send_idigi_data(data, filename, collection=None, secure=True):
        return idigidata.send_to_idigi(data, filename, collection)
except ImportError:
    from _idigi_data import *
