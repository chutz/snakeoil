# Copyright: 2005-2011 Brian Harring <ferringb@gmail.com>
# License: BSD/GPL2

"""
Miscellanious mapping related classes and functionality


"""

__all__ = ("autoconvert_py3k_methods_metaclass", "DictMixin", "LazyValDict",
    "LazyFullValLoadDict", "ProtectedDict", "ImmutableDict", "IndeterminantDict",
    "OrderedDict", "defaultdict", "defaultdictkey", "AttrAccessible", "StackedDict",
    "make_SlottedDict_kls")

from collections import deque
from itertools import imap, chain, ifilterfalse, izip
import operator
import sys

from snakeoil.klass import get, contains, steal_docs, alias_method
from snakeoil import compatibility
cmp = compatibility.cmp

class autoconvert_py3k_methods_metaclass(type):

    """
    metaclass designed to transform a py2k target mapping into a py3k compliant mapping

    Specifically, it'll drop the iter* prefix on relevant methods, and remove has_key

    To use this, just `set __metaclass__ = autoconvert_py3k_methods_metaclass`.  At runtime,
    the metaclass will rewrite the class if needed for py3k compatibility.

    If you need to disable this behaviour, set `disable_py3k_rewriting=True` in the class
    namespace- this is primarily useful if your derivative class handles the py2k/py3k difference
    itself.
    """
    if compatibility.is_py3k:
        # only do these modifications if we're running py3k.

        def __new__(cls, name, bases, d):
            d["__metaclass__"] = autoconvert_py3k_methods_metaclass
            if not d.pop("disable_py3k_rewriting", False):
                for var in ("keys", "values", "items", "has_key"):
                    d.pop(var, None)
                for var in ("keys", "values", "items"):
                    itervar = 'iter%s' % var
                    if itervar in d:
                        d[var] = d.pop(itervar)
                # ensure that the __metaclass__ attribute hangs around for usage by introspection
            return super(autoconvert_py3k_methods_metaclass, cls).__new__(cls, name, bases, d)


class DictMixin(object):
    """
    new style class replacement for :py:func:`UserDict.DictMixin`
    designed around iter* methods rather then forcing lists as DictMixin does

    To use this mixin, you need to define the following methods:

    * __delitem__
    * __setitem__
    * __getitem__
    * iterkeys

    It's suggested for performance reasons, it might be worth defining an
    `itervalues` and `iteritems` in addition.

    Note that this class utilizes the metaclass :py:class:`autoconver_py3k_methods_metaclass`
    to automatically at class creation time rewrite a py2k targeted class to a py3k
    mapping class- this is done so that derivatives classes can just write their methods
    as iterkeys, iteritems, etc, without worrying if they'll be running py2k or py3k-
    if it's py3k, it'll force a rename of the methods to the py3k layout.

    If for whatever reason, you do *not* want this renaming, set `disable_py3k_rewriting=True`
    in a derivative class.
    """

    __slots__ = ()
    __externally_mutable__ = True
    __metaclass__ = autoconvert_py3k_methods_metaclass

    disable_py3k_rewriting = True

    def __init__(self, iterable=None, **kwargs):
        """
        instantiate a new instance

        :param iterables: optional, an iterable of (key, value) to initialize this
            instance with
        :param kwargs: optional, key=value form of specifying the keys value tuples to
            store in this instance.
        """
        if iterable is not None:
            self.update(iterable)

        if kwargs:
            self.update(kwargs.iteritems())

    @steal_docs(dict)
    def __iter__(self):
        return self.iterkeys()

    def iteritems(self):
        for k in self:
            yield k, self[k]

    # change our base method definitions dependant
    # on if it's py2k or py3k; note that the
    # autoconvert_py3k_methods_metaclass will move around
    # methods as needed to match the py3k method layout,
    # shifting iterkeys to keys for example
    # note the only reason we do this if/else instead of
    # relying on autoconvert_py3k_methods_metaclass is because
    # for this base class, we need to steal the docs off of
    # dictionary instances.

    if not compatibility.is_py3k:
        iteritems.__doc__ = dict.__doc__

        @steal_docs(dict)
        def keys(self):
            return list(self.iterkeys())

        @steal_docs(dict)
        def values(self):
            return list(self.itervalues())

        @steal_docs(dict)
        def items(self):
            return list(self.iteritems())

        @steal_docs(dict, True)
        def has_key(self, key):
            return key in self

        @steal_docs(dict)
        def iterkeys(self):
            raise NotImplementedError(self, "iterkeys")

        @steal_docs(dict)
        def itervalues(self):
            return imap(self.__getitem__, self)

        iteritems = steal_docs(dict)(iteritems)

    else:
        items = iteritems
        items.__name__ = 'items'
        items.__doc__ = dict.items.__doc__
        del iteritems

        @steal_docs(dict)
        def keys(self):
            raise NotImplementedError(self, "iterkeys")

        @steal_docs(dict)
        def values(self):
            return imap(self.__getitem__, self)

    @steal_docs(dict)
    def update(self, iterable):
        for k, v in iterable:
            self[k] = v

    get = get
    __contains__ = contains

    # default cmp actually operates based on key len comparison, oddly enough
    def __cmp__(self, other):
        for k1, k2 in izip(sorted(self), sorted(other)):
            c = cmp(k1, k2)
            if c != 0:
                return c
            c = cmp(self[k1], other[k2])
            if c != 0:
                return c
        c = cmp(len(self), len(other))
        return c

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    @steal_docs(dict)
    def pop(self, key, default=None):
        if not self.__externally_mutable__:
            raise AttributeError(self, "pop")
        try:
            val = self[key]
            del self[key]
        except KeyError:
            if default is not None:
                return default
            raise
        return val

    @steal_docs(dict)
    def setdefault(self, key, default=None):
        if not self.__externally_mutable__:
            raise AttributeError(self, "setdefault")
        if key in self:
            return self[key]
        self[key] = default
        return default

    def __getitem__(self, key):
        raise NotImplementedError(self, "__getitem__")

    def __setitem__(self, key, val):
        if not self.__externally_mutable__:
            raise AttributeError(self, "__setitem__")
        raise NotImplementedError(self, "__setitem__")

    def __delitem__(self, key):
        if not self.__externally_mutable__:
            raise AttributeError(self, "__delitem__")
        raise NotImplementedError(self, "__delitem__")

    @steal_docs(dict)
    def clear(self):
        if not self.__externally_mutable__:
            raise AttributeError(self, "clear")

        # yes, a bit ugly, but this works and is py3k compatible
        # post conversion
        df = self.__delitem__
        for key in self.keys():
            df(key)

    def __len__(self):
        c = 0
        for x in self:
            c += 1
        return c

    def __nonzero__(self):
        for x in self:
            return True
        return False

    @steal_docs(dict)
    def popitem(self):
        if not self.__externally_mutable__:
            raise AttributeError(self, "popitem")
        # do it this way so python handles the stopiteration; faster
        for key, val in self.iteritems():
            del self[key]
            return key, val
        raise KeyError("container is empty")


class LazyValDict(DictMixin):

    """
    Mapping that loads values via a callable

    given a function to get keys, and to look up the val for those keys, it'll
    lazily load key definitions and values as requested
    """
    __slots__ = ("_keys", "_keys_func", "_vals", "_val_func")
    __externally_mutable__ = False

    def __init__(self, get_keys_func, get_val_func):
        """
        :param get_keys_func: either a container, or func to call to get keys.
        :param get_val_func: a callable that is JIT called
            with the key requested.
        """
        if not callable(get_val_func):
            raise TypeError("get_val_func isn't a callable")
        if hasattr(get_keys_func, "__iter__"):
            self._keys = get_keys_func
            self._keys_func = None
        else:
            if not callable(get_keys_func):
                raise TypeError(
                    "get_keys_func isn't iterable or callable")
            self._keys_func = get_keys_func
        self._val_func = get_val_func
        self._vals = {}

    def __getitem__(self, key):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        if key in self._vals:
            return self._vals[key]
        if key in self._keys:
            v = self._vals[key] = self._val_func(key)
            return v
        raise KeyError(key)

    def keys(self):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return list(self._keys)

    def iterkeys(self):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return iter(self._keys)

    def itervalues(self):
        return imap(self.__getitem__, self.iterkeys())

    def iteritems(self):
        return ((k, self[k]) for k in self.iterkeys())

    def __contains__(self, key):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return key in self._keys

    def __len__(self):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        return len(self._keys)


class LazyFullValLoadDict(LazyValDict):

    """
    Lazily load all keys for this mapping in a single load

    This is essentially the same thing as :py:class:`LazyValDict`, just that the
    load function must return all keys in a single request.

    The val function must still return values one by one per key.
    """
    __slots__ = ()

    def __getitem__(self, key):
        if self._keys_func is not None:
            self._keys = set(self._keys_func())
            self._keys_func = None
        if key in self._vals:
            return self._vals[key]
        if key in self._keys:
            if self._val_func is not None:
                self._vals.update(self._val_func(self._keys))
                return self._vals[key]
        raise KeyError(key)


class ProtectedDict(DictMixin):

    """
    Mapping wrapper storing changes to a dict without modifying the original.

    Changes are stored in a secondary dict, protecting the underlying
    mapping from changes.
    """

    __slots__ = ("orig", "new", "blacklist")

    def __init__(self, orig):
        """
        :param orig: original dictionary to wrap
        """
        self.orig = orig
        self.new = {}
        self.blacklist = {}

    def __setitem__(self, key, val):
        self.new[key] = val
        if key in self.blacklist:
            del self.blacklist[key]

    def __getitem__(self, key):
        if key in self.new:
            return self.new[key]
        if key in self.blacklist:
            raise KeyError(key)
        return self.orig[key]

    def __delitem__(self, key):
        if key in self.new:
            del self.new[key]
            self.blacklist[key] = True
            return
        elif key in self.orig:
            if key not in self.blacklist:
                self.blacklist[key] = True
                return
        raise KeyError(key)

    def iterkeys(self):
        for k in self.new.iterkeys():
            yield k
        for k in self.orig.iterkeys():
            if k not in self.blacklist and k not in self.new:
                yield k

    def __contains__(self, key):
        return key in self.new or (key not in self.blacklist and
                                   key in self.orig)


class ImmutableDict(dict):

    """
    Immutable Dict, unchangeable after instantiating

    Because this is immutable, it's hashable.
    """

    _hash_key_grabber = operator.itemgetter(0)

    def __delitem__(self, *args):
        raise TypeError("unmodifiable")

    __setitem__ = clear = update = pop = popitem = setdefault = __delitem__

    def __hash__(self):
        k = self.items()
        k.sort(key=self._hash_key_grabber)
        return hash(tuple(k))

    __delattr__ = __setitem__
    __setattr__ = __setitem__


class IndeterminantDict(object):

    """
    A wrapped dict with constant defaults, and a function for other keys.

    The primary use for this class is to make a JIT loaded mapping- for instance, a
    mapping representing the filesystem that loads keys/values as it goes.
    """

    __slots__ = ("__initial", "__pull")

    def __init__(self, pull_func, starter_dict=None):
        object.__init__(self)
        if starter_dict is None:
            self.__initial = {}
        else:
            self.__initial = starter_dict
        self.__pull = pull_func

    def __getitem__(self, key):
        if key in self.__initial:
            return self.__initial[key]
        else:
            return self.__pull(key)

    def get(self, key, val=None):
        try:
            return self[key]
        except KeyError:
            return val

    def __hash__(self):
        raise TypeError("unhashable")

    def __delitem__(self, *args):
        raise TypeError("unmodifiable")

    pop = get

    clear = update = popitem = setdefault = __setitem__ = __delitem__
    __iter__ = keys = values = items = __len__ = __delitem__
    iteritems = iterkeys = itervalues = __delitem__


class StackedDict(DictMixin):

    """An unmodifiable dict that makes multiple dicts appear as one"""

    def __init__(self, *dicts):
        self._dicts = dicts

    def __getitem__(self, key):
        for x in self._dicts:
            if key in x:
                return x[key]
        raise KeyError(key)

    def iterkeys(self):
        s = set()
        for k in ifilterfalse(s.__contains__, chain(*map(iter, self._dicts))):
            s.add(k)
            yield k

    def __contains__(self, key):
        for x in self._dicts:
            if key in x:
                return True
        return False

    def __setitem__(self, *a):
        raise TypeError("unmodifiable")

    __delitem__ = clear = __setitem__


class OrderedDict(DictMixin):

    """Dict that preserves insertion ordering which is used for iteration ops"""

    __slots__ = ("_data", "_order")

    def __init__(self, iterable=()):
        self._order = deque()
        self._data = {}
        for k, v in iterable:
            self[k] = v

    def __setitem__(self, key, val):
        if key not in self:
            self._order.append(key)
        self._data[key] = val

    def __delitem__(self, key):
        del self._data[key]

        for idx, o in enumerate(self._order):
            if o == key:
                del self._order[idx]
                break
        else:
            raise AssertionError("orderdict lost its internal ordering")

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._order)

    def iterkeys(self):
        return iter(self._order)

    def clear(self):
        self._order = deque()
        self._data = {}

    def __contains__(self, key):
        return key in self._data


class PreservingFoldingDict(DictMixin):

    """dict that uses a 'folder' function when looking up keys.

    The most common use for this is to implement a dict with
    case-insensitive key values (by using ``str.lower`` as folder
    function).

    This version returns the original 'unfolded' key.
    """

    def __init__(self, folder, sourcedict=None):
        self._folder = folder
        # dict mapping folded keys to (original key, value)
        self._dict = {}
        if sourcedict is not None:
            self.update(sourcedict)

    def copy(self):
        return PreservingFoldingDict(self._folder, self.iteritems())

    def refold(self, folder=None):
        """Use the remembered original keys to update to a new folder.

        If folder is None, keep the current folding function (this
        is useful if the folding function uses external data and that
        data changed).
        """
        if folder is not None:
            self._folder = folder
        oldDict = self._dict
        self._dict = {}
        for key, value in oldDict.itervalues():
            self._dict[self._folder(key)] = (key, value)

    def __getitem__(self, key):
        return self._dict[self._folder(key)][1]

    def __setitem__(self, key, value):
        self._dict[self._folder(key)] = (key, value)

    def __delitem__(self, key):
        del self._dict[self._folder(key)]

    def iteritems(self):
        return self._dict.itervalues()

    def iterkeys(self):
        for val in self._dict.itervalues():
            yield val[0]

    def itervalues(self):
        for val in self._dict.itervalues():
            yield val[1]

    def __contains__(self, key):
        return self._folder(key) in self._dict

    def __len__(self):
        return len(self._dict)

    def clear(self):
        self._dict = {}


class NonPreservingFoldingDict(DictMixin):

    """dict that uses a 'folder' function when looking up keys.

    The most common use for this is to implement a dict with
    case-insensitive key values (by using ``str.lower`` as folder
    function).

    This version returns the 'folded' key.
    """

    def __init__(self, folder, sourcedict=None):
        self._folder = folder
        # dict mapping folded keys to values.
        self._dict = {}
        if sourcedict is not None:
            self.update(sourcedict)

    def copy(self):
        return NonPreservingFoldingDict(self._folder, self.iteritems())

    def __getitem__(self, key):
        return self._dict[self._folder(key)]

    def __setitem__(self, key, value):
        self._dict[self._folder(key)] = value

    def __delitem__(self, key):
        del self._dict[self._folder(key)]

    def iterkeys(self):
        return iter(self._dict)

    def itervalues(self):
        return self._dict.itervalues()

    def iteritems(self):
        return self._dict.iteritems()

    def __contains__(self, key):
        return self._folder(key) in self._dict

    def __len__(self):
        return len(self._dict)

    def clear(self):
        self._dict = {}


from collections import defaultdict

class defaultdictkey(defaultdict):

    """
    :py:class:`defaultdict` derivative that automatically stores any missing key/value pairs.

    Specifically, if instance[missing_key] is accessed, the `__missing__` method automatically
    store self[missing_key] = self.default_factory(key).
    """
    def __init__(self, default_factory):
        # we have our own init to explicitly force via prototype
        # that a default_factory is required
        defaultdict.__init__(self, default_factory)

    @steal_docs(defaultdict)
    def __missing__(self, key):
        obj = self[key] = self.default_factory(key)
        return obj


def _KeyError_to_Attr(functor):
    def inner(self, *args):
        try:
            return functor(self, *args)
        except KeyError:
            raise AttributeError(args[0])
    inner.__name__ = functor.__name__
    inner.__doc__ = functor.__doc__
    return inner


def inject_getitem_as_getattr(scope):
    """modify a given class scope proxying attr access to dict access

    If the given scope already has __getattr__, __setattr__, or __delattr__,
    the pre-existing method will not be overriden.

    Example usage:

    >>> class my_options(dict):
    ...    inject_getitem_as_getattr(locals())
    >>>
    >>> d = my_options(asdf=1)
    >>> print d.asdf
    1
    >>> d.asdf = 2
    >>> print d.asdf
    2
    >>> del d.asdf
    >>> print 'asdf' in d
    False
    >>> print hasattr(d, 'asdf')
    False

    :param scope: the scope of a class to modify, adding methods as needed
    """

    scope.setdefault('__getattr__',
        _KeyError_to_Attr(operator.__getitem__))
    scope.setdefault('__delattr__',
        _KeyError_to_Attr(operator.__delitem__))
    scope.setdefault('__setattr__',
        _KeyError_to_Attr(operator.__setitem__))


class AttrAccessible(dict):

    """simple dict class allowing instance.x and instance['x'] access"""

    __slots__ = ()

    inject_getitem_as_getattr(locals())


def native_attr_getitem(self, key):
    try:
        return getattr(self, key)
    except AttributeError:
        raise KeyError(key)

def native_attr_update(self, iterable):
    for k, v in iterable:
        setattr(self, k, v)

def native_attr_contains(self, key):
     return hasattr(self, key)

# python issue 7604; depending on the python version, delattr'ing an empty slot
# doesn't throw AttributeError; we vary our implementation for efficiency
# dependant on a onetime runtime test of that.

class foo(object):
    __slots__ = ("slot",)

# track which is required since if we can use extensions, we'll have
# to chose which to import; cpy side exports both, leaving it to us
# to decide which to use (via runtime check, it means we don't have to
# be recompiled for minor bumps when the fix is in place- it just switches
# on).
_use_slow_delitem = True
try:
    del foo().slot
except AttributeError:
    # properly throws an exception; thus we do a single lookup.
    _use_slow_delitem = False
    def native_attr_delitem(self, key):
        try:
            delattr(self, key)
        except AttributeError:
            raise KeyError(key)
else:
    # doesn't throw the exception; double lookup, getattr, than delattr.
    def native_attr_delitem(self, key):
         # Python does not raise anything if you delattr an
         # unset slot (works ok if __slots__ is not involved).
         try:
             getattr(self, key)
         except AttributeError:
             raise KeyError(key)
         delattr(self, key)

# cleanup the test class.
del foo

_sentinel = object()
def native_attr_pop(self, key, *a):
    # faster then the exception form...
    l = len(a)
    if l > 1:
        raise TypeError("pop accepts 1 or 2 args only")
    o = getattr(self, key, _sentinel)
    if o is not _sentinel:
        object.__delattr__(self, key)
    elif l:
        o = a[0]
    else:
        raise KeyError(key)
    return o

def native_attr_get(self, key, default=None):
    return getattr(self, key, default)

try:
    from snakeoil._klass import (attr_getitem, attr_setitem,
        attr_update, attr_contains, attr_pop, attr_get)
    if _use_slow_delitem:
        from snakeoil._klass import attr_delitem_slow as attr_delitem
    else:
        from snakeoil._klass import attr_delitem_fast as attr_delitem
except ImportError:
    attr_getitem = native_attr_getitem
    attr_setitem = object.__setattr__
    attr_delitem = native_attr_delitem
    attr_update = native_attr_update
    attr_contains = native_attr_contains
    attr_pop = native_attr_pop
    attr_get = native_attr_get


slotted_dict_cache = {}
def make_SlottedDict_kls(keys):
    """
    Create a space efficient mapping class with a limited set of keys

    Specifically, this function returns a class with it's __slots__ locked
    to the passed in keys- this eliminates the allocation of a dict for the
    instance thus avoiding the wasted memory common to dictionary overallocation-
    for small mappings that waste is roughly 75%, for 100 item mappings it's roughly
    95%, and for 1000 items it's roughly 84%.  Point is, it's sizable, consistantly so.

    The constraint of this is that the resultant mapping has a locked set of
    keys- you cannot add a key that wasn't allowed up front.

    This functionality is primarily useful when you'll be generating many
    dict instances, all with a common set of allowed keys.

    :param keys: iterable/sequence of keys to allow in the resultant mapping

    Example usage:

    >>> from snakeoil.obj import make_SlottedDict_kls
    >>> import sys
    >>> my_kls = make_SlottedDict_kls(["key1", "key2", "key3"])
    >>> items = (("key1", 1), ("key2", 2), ("key3",3))
    >>> inst = dict(items)
    >>> slotted_inst = my_kls(items)
    >>> print sys.getsizeof(inst) # note this is python2.6 functionality
    280
    >>> print sys.getsizeof(slotted_inst)
    72
    >>> # and now for an extreme example:
    >>> raw = dict(("attribute%i" % (x,), x) for x in xrange(1000))
    >>> skls = make_SlottedDict_kls(raw.keys())
    >>> print sys.getsizeof(raw)
    49432
    >>> sraw = skls(raw.iteritems())
    >>> print sys.getsizeof(sraw)
    8048
    >>> print sraw["attribute2"], sraw["attribute3"]
    2 3

    Note that those stats are for a 64bit python 2.6.5 VM.  The stats may
    differ for other python implementations or versions, although for cpython
    the stats above should hold +/- a couple of bites.

    Finally, it's worth noting that the stats above are the minimal savings-
    via a side affect of the __slots__ the keys are automatically interned.

    This means that if you have 100 instances floating around, for dict's
    that costs you sizeof(key) * 100, for slotted dict instances you pay
    sizeof(key) due to the interning.
    """

    new_keys = tuple(sorted(keys))
    o = slotted_dict_cache.get(new_keys, None)
    if o is None:
        class SlottedDict(DictMixin):
            __slots__ = new_keys
            __externally_mutable__ = True

            def __init__(self, iterables=()):
                if iterables:
                    self.update(iterables)

            __setitem__ = attr_setitem
            __getitem__ = attr_getitem
            __delitem__ = attr_delitem
            __contains__ = attr_contains
            update = attr_update
            pop = attr_pop
            get = attr_get

            def __iter__(self):
                for k in self.__slots__:
                    if hasattr(self, k):
                        yield k

            def iterkeys(self):
                return iter(self)

            def itervalues(self):
                for k in self:
                    yield self[k]

            def clear(self):
                for k in self:
                    del self[k]

            def __len__(self):
                return len(self.keys())


        o = SlottedDict
        slotted_dict_cache[new_keys] = o
    return o
