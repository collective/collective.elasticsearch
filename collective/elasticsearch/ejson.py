try:
    import json
except ImportError:
    import simplejson as json
from datetime import datetime
import re

from DateTime import DateTime
from persistent.dict import PersistentDict
from Persistence.mapping import PersistentMapping as PM1
from persistent.mapping import PersistentMapping as PM2
from persistent.list import PersistentList
from BTrees.OOBTree import OOBTree
from zope.dottedname.resolve import resolve
from ZPublisher.HTTPRequest import record
from Missing import MV

_type_marker = 'type://'
_date_re = re.compile('^[0-9]{4}\-[0-9]{2}\-[0-9]{2}.*$')


class BaseTypeSerializer(object):
    klass = None
    toklass = None

    @classmethod
    def getTypeName(kls):
        return "%s.%s" % (kls.klass.__module__, kls.klass.__name__)

    @classmethod
    def serialize(kls, obj):
        if hasattr(obj, 'aq_base'):
            obj = obj.aq_base
        data = kls._serialize(obj)
        results = {
            'type': kls.getTypeName(),
            'data': data
        }
        return _type_marker + dumps(results)

    @classmethod
    def _serialize(kls, obj):
        return kls.toklass(obj)

    @classmethod
    def deserialize(kls, data):
        return kls._deserialize(data)

    @classmethod
    def _deserialize(kls, data):
        return kls.klass(data)


class PM1Serializer(BaseTypeSerializer):
    klass = PM1
    toklass = dict


class PM2Serializer(PM1Serializer):
    klass = PM2


class PersistentDictSerializer(BaseTypeSerializer):
    klass = PersistentDict
    toklass = dict


class OOBTreeSerializer(BaseTypeSerializer):
    klass = OOBTree
    toklass = dict


class PersistentListSerializer(BaseTypeSerializer):
    klass = PersistentList
    toklass = list


class setSerializer(BaseTypeSerializer):
    klass = set
    toklass = list


class DateTimeSerializer(BaseTypeSerializer):
    klass = DateTime

    @classmethod
    def getTypeName(kls):
        return 'DateTime.DateTime'

    @classmethod
    def _serialize(kls, obj):
        return obj.ISO8601()

    @classmethod
    def _deserialize(kls, data):
        return DateTime(data)


class datetimeSerializer(BaseTypeSerializer):
    klass = datetime

    @classmethod
    def _serialize(kls, obj):
        return obj.isoformat()

    @classmethod
    def _deserialize(kls, data):
        return datetime.strptime(data, '%Y-%m-%dT%H:%M:%S.%f')


class recordSerializer(BaseTypeSerializer):
    klass = record
    toklass = dict

    @classmethod
    def _deserialize(kls, data):
        rec = record()
        for key, value in data.items():
            setattr(rec, key, value)
        return rec


class MVSerializer(BaseTypeSerializer):
    klass = type(MV)

    @classmethod
    def _deserialize(kls, data):
        return MV

    @classmethod
    def _serialize(kls, obj):
        return ''


_serializers = {
    PM1: PM1Serializer,
    PM2: PM2Serializer,
    PersistentDict: PersistentDictSerializer,
    OOBTree: OOBTreeSerializer,
    PersistentList: PersistentListSerializer,
    set: setSerializer,
    DateTime: DateTimeSerializer,
    datetime: datetimeSerializer,
    record: recordSerializer,
    type(MV): MVSerializer
}


class Deferred:
    pass


def customhandler(obj):
    if hasattr(obj, 'aq_base'):
        obj = obj.aq_base
    _type = type(obj)
    if _type.__name__ == 'instance':
        _type = obj.__class__
    if _type in _serializers:
        serializer = _serializers[_type]
        return serializer.serialize(obj)
    else:
        return None
    return obj


def custom_decoder(d):
    if isinstance(d, list):
        pairs = enumerate(d)
    elif isinstance(d, dict):
        pairs = d.items()
    result = []
    for k, v in pairs:
        if isinstance(v, basestring):
            if v.startswith(_type_marker):
                v = v[len(_type_marker):]
                results = loads(v)
                _type = resolve(results['type'])
                try:
                    serializer = _serializers[_type]
                except TypeError:
                    serializer = _serializers[type(_type)]
                v = serializer.deserialize(results['data'])
        elif isinstance(v, (dict, list)):
            v = custom_decoder(v)
        result.append((k, v))
    if isinstance(d, list):
        return [x[1] for x in result]
    elif isinstance(d, dict):
        return dict(result)


def loads(data):
    return json.loads(data, object_hook=custom_decoder)


def dumps(data):
    return json.dumps(data, default=customhandler)
