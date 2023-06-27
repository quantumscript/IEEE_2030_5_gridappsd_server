from __future__ import annotations

from threading import Lock
from typing import Optional, List
from uuid import uuid4

from ieee_2030_5.server.exceptions import AlreadyExistsError

__write_lock__: Lock = Lock()


class UUIDHandler:
    handler: UUIDHandler = None
    bag: dict = {}
    uuids: set = set()

    def __new__(cls):
        if UUIDHandler.handler is None:
            UUIDHandler.handler = super().__new__(cls)
        return UUIDHandler.handler

    def add_known(self, uuid: str, obj: object):
        assert isinstance(uuid, str) and obj is not None

        with __write_lock__:
            self.bag[uuid] = obj
            # TODO: Not sure this is correct for id(obj) to be able to determine equality.
            self.bag[id(obj)] = uuid
            self.uuids.add(uuid)

    def add(self, obj) -> str:
        """
        Add an object to the UUIDHandler.  If the object already exists
        in the collection then raise AlreadyExistsError

        :param: obj - The object to store in the handler.
        """
        if obj in self.bag:
            raise AlreadyExistsError(f"obj {obj} already exists in bag")

        new_uuid = self.generate()
        self.add_known(new_uuid, obj)
        return new_uuid

    def get_uuid(self, obj) -> Optional[str]:
        """
        Retrieve a uuid for a matching object.  If match exists the
        function returns the uuid, if not then returns None.

        :param: object An object to match.

        return: A string uuid or None
        """
        return self.bag.get(id(obj))

    def get_obj(self, uuid: str) -> Optional[object]:
        """
        Retrieve an object based on the passed uuid.  If match exists the
        function returns the object, if not then returns None.

        :param: str A uuid to match against.

        return: An object or None
        """
        return self.bag.get(uuid)

    def get_uuids(self) -> List[str]:
        return list(self.uuids.copy())

    def generate(self) -> str:
        new_uuid = str(uuid4())
        while new_uuid in self.uuids:
            new_uuid = str(uuid4())
        return new_uuid
