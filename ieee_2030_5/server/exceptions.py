class AlreadyExistsError(Exception):
    """
    The AlreadyExistsError exception should be raise any time an object is attempted to be inserted
    into a collection where replacement is not allowed.
    """
    pass


class NotFoundError(Exception):
    pass
