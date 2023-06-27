"""
Provides a key/value store interface for setting retrieving points from a datastore.

This implementation just uses pickledb for loading a json datastore.  After
each set the data will be written to disk.
"""
import atexit
from pathlib import Path

from simplekv.fs import FilesystemStore

db = FilesystemStore(Path("~/.ieee_2030_5_data").expanduser().resolve())


def set_point(key: str, value: bytes):
    """
    Set a point into the key/value store.  Both key and value must be hashable types.

    Example:
        set_point("_e55a4c7a-c006-4596-b658-e23bc771b5cb.angle", -156.38295096513662)
        set_point("known_mrids": ["_4da919f1-762f-4755-b674-5faccf3faec6"])
    """
    k = key.replace('/', '^^^^')
    db.put(k, value)


def get_point(key):
    """
    Retrieve a point from the key/value store.  If the key doesn't exist returns None.
    """
    k = key.replace('/', '^^^^')
    return db.get(k)


def get_hrefs():
    return db.keys()


if __name__ == '__main__':

    set_point("foo", b"bar")
    set_point("bim", b"baf")
    # print(get_point("foo"))
    get_hrefs()
