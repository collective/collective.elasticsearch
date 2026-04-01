from zope.interface import implementer
from zope.interface import Interface


class IBlobIndexJobCreated(Interface):
    """Fired after a blob extraction job has been enqueued."""


@implementer(IBlobIndexJobCreated)
class BlobIndexJobCreated:
    """Fired after a blob extraction job has been enqueued.

    Subscribers can use ``event.job`` with RQ's ``depends_on`` to
    chain work that needs the extracted text.
    """

    def __init__(self, uid, job):
        self.uid = uid
        self.job = job
