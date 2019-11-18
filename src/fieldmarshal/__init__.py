import sys
import json
from enum import Enum, Flag, IntEnum, IntFlag
from functools import partial, singledispatch, wraps
from typing import Any, List, Tuple, Set, FrozenSet, Dict, Union

import attr

__version__ = '0.0.2'

__all__ = [
    'field',
    'marshal',
    'marshal_json',
    'struct',
    'unmarshal',
    'unmarshal_json',

    'Hook',
    'Options',
    'Registry',

    'DEFAULT_OPTIONS',
    'DEFAULT_REGISTRY',
]


PY36 = sys.version_info[:2] == (3, 6)


struct = partial(attr.s, slots=True, auto_attribs=True)


@struct
class Options:
    """
    Field options control how a field is marshalled/unmarshalled.

    :param str name: Rename the field when marshalling/unmarshalling. Useful
        for example for JSON attribute names that are not valid Python
        identifiers.
    :param bool omit: Ignore the field for the purpose of
        marshalling/unmarshalling. The field value will neither be read nor
        written to. The field should also have a default value for the class to
        support unmarshalling.
    :param bool omit_if_none: Omit the field when marshalling if it's value is
        ``None``. When unmarshalling, the field will be read as normal.
    :param callable marshal: A function to call to marshal the contents of this
        field. The function will be passed the field value as its only
        argument. This hook overrides other marshal hooks registered for the
        field's type.
    :param callable unmarshal: A function to call to unmarshal data for this
        field. The function will be passed the data being unmarshalled as its
        only argument. This hook overrides other unmarshal hooks registered for
        the field's type.

    For ``fieldmarshal`` to recognize these options, put the object into the
    field's ``metadata`` dict under the "fieldmarshal" key, or use the
    :func:`field` helper in place of ``attr.s``.
    """
    name: str = None
    omit: bool = False
    omit_if_none: bool = False
    marshal: Any = None
    unmarshal: Any = None


def field(name=None, omit=False, omit_if_none=False, marshal=None, unmarshal=None, **kw):
    """
    Wrapper around ``attr.ib`` that accepts additional arguments.

    Arguments that control marshalling are saved as an :class:`Options` object
    in the fields metadata under the "fieldmarshal" key. See
    :class:`Options` for the meaning of these parameters.
    """
    metadata = kw.setdefault('metadata', {})
    metadata['fieldmarshal'] = Options(
        name,
        omit=omit,
        omit_if_none=omit_if_none,
        marshal=marshal,
        unmarshal=unmarshal,
    )
    return attr.ib(**kw)


DEFAULT_OPTIONS  = Options()

IDENTITY = object()

NONE_TYPE = type(None)
SCALAR_TYPES = {int, bool, float, str, NONE_TYPE}


def _marshal_default(obj, registry):
    raise TypeError("Can't marshal %r" % obj)


def _marshal_attrs(obj, registry):
    data = {}
    cls = obj.__class__
    for field in cls.__attrs_attrs__:
        key = (cls, field.name)
        try:
            options = registry._field_options_cache[key]
        except KeyError:
            options = field.metadata.get('fieldmarshal', DEFAULT_OPTIONS)
            registry._field_options_cache[key] = options
        if not options.omit:
            name = field.name if options.name is None else options.name
            value = getattr(obj, field.name)
            if not (value is None and options.omit_if_none):
                if options.marshal is not None:
                    data[name] = options.marshal(value)
                else:
                    data[name] = registry.marshal(value)
    return data


def _marshal_list(obj, registry):
    return [registry.marshal(item) for item in obj]


def _marshal_set(obj, registry):
    return sorted([registry.marshal(item) for item in obj])


def _marshal_dict_key(key, registry):
    obj = registry.marshal(key)

    # Rendering of True, False, None, object() as dict keys:
    #   stdlib json: "true", "false", "null", TypeError
    #   ujson:       "True", "False", "None", "<object object at …>"
    #   rapidjson:   TypeError (all)

    if obj is True:
        return 'true'
    elif obj is False:
        return 'false'
    elif obj is None:
        return 'null'
    elif isinstance(obj, str):
        return obj
    elif isinstance(obj, (int, float)):
        return str(obj)
    else:
        raise TypeError("Can't marshal dict key: %r" % key)


def _marshal_dict(obj, registry):
    return {_marshal_dict_key(k, registry): registry.marshal(v)
            for k, v in obj.items()}


def _marshal_enum(obj, registry):
    return obj.value


def _unmarshal_default(obj, type_hint, registry):
    raise TypeError("Can't unmarshal to %s: %r" % (type_hint, obj))


def _unmarshal_attrs(obj, type_hint, registry):
    kw = {}
    for field in type_hint.__attrs_attrs__:
        key = (type_hint, field.name)
        try:
            options = registry._field_options_cache[key]
        except KeyError:
            options = field.metadata.get('fieldmarshal', DEFAULT_OPTIONS)
            registry._field_options_cache[key] = options
        if not options.omit:
            name = field.name if options.name is None else options.name
            try:
                value = obj[name]
            except KeyError:
                if field.default is not attr.NOTHING:
                    value = field.default
                else:
                    raise
            if options.unmarshal is not None:
                kw[field.name] = options.unmarshal(value)
            else:
                kw[field.name] = registry.unmarshal(value, field.type or Any)
    return type_hint(**kw)


def _unmarshal_dict_key(key, type_, registry):
    if type_ in {int, float}:
        obj = type_(key)
    elif type_ is bool:
        try:
            obj = {'true': True, 'false': False}[key]
        except KeyError:
            raise ValueError(
                "Error converting dict key to bool. Expected 'true' or 'false', got %r" % key
            ) from None
    elif type_ is NONE_TYPE:
        try:
            obj = {'null': None}[key]
        except KeyError:
            raise ValueError(
                "Error converting dict key to NoneType. Expected 'null', got %r" % key
            ) from None
    elif getattr(type_, '__mro__', None) is not None and issubclass(type_, (Flag, IntEnum, IntFlag)):
        obj = int(key)
    else:
        obj = key

    return registry.unmarshal(obj, type_)


# Lookup functions are called with the type of object being unmarshalled (cls),
# the type to unmarshal to (type_hint) and the registry as arguments.
# The job of the lookup function is to *validate* cls, which is a JSON-
# compatible type, against type_hint, and return an unmarshal impl suitable
# for the specific combination of (cls, type_hint), or _unmarshal_default.
# Returning _unmarshal_default instead of raising TypeError means the
# function can be used to speculatively lookup impls that might not exist.
# Type_hint is the type or class the lookup was registered for, or a subclass
# thereof.

def require(*classes):
    def decorator(fn):
        @wraps(fn)
        def wrapper(cls, type_hint, registry):
            if cls not in classes:
                return _unmarshal_default
            return fn(cls, type_hint, registry)
        return wrapper
    return decorator


def _unmarshal_lookup_default(cls, type_hint, registry):
    return _unmarshal_default


@require(*SCALAR_TYPES)
def _unmarshal_lookup_scalar(cls, type_hint, registry):
    if not issubclass(cls, type_hint):
        return _unmarshal_default
    return IDENTITY


def _unmarshal_list(obj, type_hint, registry):
    item_type, = type_hint.__args__
    return [registry.unmarshal(item, item_type) for item in obj]


def _unmarshal_tuple(obj, type_hint, registry):
    item_types = type_hint.__args__
    return tuple([registry.unmarshal(item, type_)
        for item, type_ in zip(obj, item_types)])


def _unmarshal_set_frozenset(obj, type_hint, registry):
    type_ = type_hint.__origin__
    if PY36:
        if type_ is Set:
            type_ = set
        elif type_ is FrozenSet:
            type_ = frozenset
    item_type, = type_hint.__args__
    return type_([registry.unmarshal(item, item_type) for item in obj])


def _unmarshal_dict(obj, type_hint, registry):
    key_type, value_type = type_hint.__args__
    return {_unmarshal_dict_key(k, key_type, registry):
                registry.unmarshal(v, value_type)
            for k, v in obj.items()}


# type_hint: any of (list, tuple, set, frozenset), or their typing equivalents
# (List[…], Tuple[…], etc.)
@require(list)
def _unmarshal_lookup_list(cls, type_hint, registry):
    if type_hint is list:
        return IDENTITY
    elif type_hint in {tuple, set, frozenset}:
        return lambda obj, type_, __: type_(obj)

    type_ = type_hint.__origin__
    if PY36:
        type_ = {List: list, Tuple: tuple, Set: set, FrozenSet: frozenset}[type_]

    if type_ is list:
        return _unmarshal_list
    elif type_ is tuple:
        return _unmarshal_tuple
    elif type_ in {set, frozenset}:
        return _unmarshal_set_frozenset

    raise TypeError("Can't unmarshal %s to %s" % (cls, type_hint))


# type_hint: dict or Dict[…]
@require(dict)
def _unmarshal_lookup_dict(cls, type_hint, registry):
    if type_hint is dict:
        return IDENTITY
    else:
        return _unmarshal_dict


@require(*SCALAR_TYPES)
def _unmarshal_lookup_enum(cls, type_hint, registry):
    return lambda obj, type_, _: type_(obj)


@require(int)
def _unmarshal_lookup_int_enum(cls, type_hint, registry):
    return lambda obj, type_, _: type_(obj)


def _resolve_union(cls, type_hint, registry):
    union_types = type_hint.__args__

    # Optional[…]
    if NONE_TYPE in union_types:
        if cls is NONE_TYPE:
            return IDENTITY, NONE_TYPE
        else:
            non_optional = tuple(t for t in union_types if t is not NONE_TYPE)
            type_ = Union[non_optional]
            return registry.lookup_unmarshal_impl(cls, type_)

    # Bail if an unmarshal hook exists for any member of the union, since
    # we can't know what type of input it accepts.
    if any(t for t in union_types if registry._hook_exists_for(cls, t)):
        raise TypeError(
            "Can't resolve unmarshal implementation for %s to %s. "
            "To resolve this, add an unmarshal hook for %s to the registry."
            % (cls, type_hint, type_hint)
        )

    # cls is a member of the union
    if cls in union_types:
        return IDENTITY, cls

    # If cls is not a scalar type, try to reduce the union by removing non
    # scalar-types.
    if cls not in union_types and cls not in SCALAR_TYPES:
        union_types = tuple(t for t in union_types if t not in SCALAR_TYPES)
        type_ = Union[union_types]
        if type_ != type_hint:
            return registry.lookup_unmarshal_impl(cls, type_)

    # As a last resort, see if there is exactly one non-scalar type in the
    # Union, and try that (even if cls is a scalar type, because it could be
    # the value of an Enum).
    candidates = [t for t in union_types if t not in SCALAR_TYPES]
    if len(candidates) == 1:
        return registry.lookup_unmarshal_impl(cls, candidates[0])

    raise TypeError(
        "Can't resolve unmarshal implementation for %s to %s. "
        "To resolve this, add an unmarshal hook for %s to the registry."
        % (cls, type_hint, type_hint)
    )


@struct
class Hook:
    """
    Container for marshal or unmarshal hooks.

    :param callable fn: Marshal hook
    :param bool takes_args: Whether or not *fn* takes additional arguments

    When `takes_args` is ``True`` (the default), additional arguments will be
    passed to the hook. The type of arguments depends on the type of hook. See
    :meth:`Registry.add_marshal_hook` and :meth:`Registry.add_unmarshal_hook`
    for details. """
    fn: Any
    takes_args: bool = True


# TODO rename "lookup" -> "resolve"?


class Registry:
    def __init__(self):
        """
        Create a registry instance.

        A registry is used for marshalling and unmarshalling objects, and
        for registering hooks for types that are not handled natively.
        """
        self._marshal_impl_cache = {}
        self._unmarshal_impl_cache = {}
        self._marshal_impl_dispatch = singledispatch(_marshal_default)
        self._unmarshal_lookup_dispatch = singledispatch(_unmarshal_lookup_default)
        self._unmarshal_hook_impl = {}
        self._unmarshal_hooks = set()
        self._field_options_cache = {}

        for type_ in SCALAR_TYPES:
            self._marshal_impl_dispatch.register(type_, IDENTITY)

        self._marshal_impl_dispatch.register(list, _marshal_list)
        self._marshal_impl_dispatch.register(tuple, _marshal_list)
        self._marshal_impl_dispatch.register(set, _marshal_set)
        self._marshal_impl_dispatch.register(frozenset, _marshal_set)
        self._marshal_impl_dispatch.register(dict, _marshal_dict)
        self._marshal_impl_dispatch.register(Enum, _marshal_enum)
        self._marshal_impl_dispatch.register(IntEnum, _marshal_enum)
        self._marshal_impl_dispatch.register(IntFlag, _marshal_enum)

        for type_ in SCALAR_TYPES:
            self._unmarshal_lookup_dispatch.register(type_, _unmarshal_lookup_scalar)

        for type_ in (list, tuple, set, frozenset):
            self._unmarshal_lookup_dispatch.register(type_, _unmarshal_lookup_list)

        self._unmarshal_lookup_dispatch.register(dict, _unmarshal_lookup_dict)
        self._unmarshal_lookup_dispatch.register(Enum, _unmarshal_lookup_enum)

        for type_ in (Flag, IntEnum, IntFlag):
            self._unmarshal_lookup_dispatch.register(type_, _unmarshal_lookup_int_enum)


    def marshal(self, obj):
        """
        Marshal an object to a JSON-compatible data structure.

        The resulting data structure contains only objects of type ``list``,
        ``dict`` (with string keys), ``int``, ``float``, ``str``, ``bool`` or
        ``NoneType`` and can be converted to JSON without further
        modifications.

        The reverse operation is :meth:`unmarshal`.
        """
        key = obj.__class__
        try:
            impl = self._marshal_impl_cache[key]
        except KeyError:
            impl = self.lookup_marshal_impl(key)
            self._marshal_impl_cache[key] = impl
        if impl is IDENTITY:
            return obj
        else:
            return impl(obj, self)

    def marshal_json(self, obj):
        """
        Marshal an object to a JSON string.

        Like :meth:`marshal`, but converts the result to JSON.
        """
        return json.dumps(self.marshal(obj))

    def add_marshal_hook(self, type_, fn):
        """
        Add a custom marshal implementation for a type.

        The hook can either be a function that takes one argument (the object
        being marshalled), or a :class:`Hook` object, which can be used to
        opt-in to receive the registry instance as an additional argument.

        The hook should return a JSON-compatible object. The hook will be
        called when an object of type *type_* is encountered when marshalling.
        The hook will also be used for instances of subclasses of *type_*,
        unless a more specific hook can be found.
        """
        hook = fn if isinstance(fn, Hook) else Hook(fn, False)
        if hook.takes_args:
            hook_impl = hook.fn
        else:
            hook_impl = lambda obj, _: hook.fn(obj)
        self._marshal_impl_dispatch.register(type_, hook_impl)
        self._marshal_impl_cache.clear()

    def lookup_marshal_impl(self, cls):
        """
        Return the marshal implementation objects of type *cls*.
        """
        impl = self._marshal_impl_dispatch.dispatch(cls)
        if impl is _marshal_default and attr.has(cls):
            return _marshal_attrs
        return impl

    def unmarshal(self, obj, type_hint):
        """
        Unmarshal an object from a JSON-compatible data structure.

        The data structure must contain only objects of type ``list``, ``dict``
        (with ``str`` keys), ``int``, ``float``, ``str``, ``bool`` or
        ``NoneType``, such as returned by :meth:`marshal`.

        *type_hint* specifies the type of object to create. This can be a class
        or a concrete type from the :mod:`typing` module, such as
        ``List[int]``.

        The reverse operation is :meth:`marshal`.
        """
        key = (obj.__class__, type_hint)
        try:
            impl, type_ = self._unmarshal_impl_cache[key]
        except KeyError:
            impl, type_ = self.lookup_unmarshal_impl(*key)
            self._unmarshal_impl_cache[key] = impl, type_
        if impl is IDENTITY:
            return obj
        else:
            return impl(obj, type_, self)

    def unmarshal_json(self, data, type_hint):
        """
        Unmarshal an object from a JSON string.

        Like :meth:`unmarshal`, but accepts a data in JSON format.
        """
        return self.unmarshal(json.loads(data), type_hint)

    def add_unmarshal_hook(self, type_, fn):
        """
        Add a custom unmarshal implementation for a type.

        *type_* can be a class or a concrete type from the :mod:`typing` module,
        such as ``Union[list, str]``. The hook can either be a function that
        takes one argument (the object being unmarshalled), or a :class:`Hook`
        object, which can be used to opt-in to receive the type the object is
        being unmarshalled to and the registry instance as additional
        arguments. The type passed this way is not necessarily the type the
        hook was registered for (it could be a subclass, for example).

        The hook will be called when data needs to be marshalled to an object
        of type *type_*. If *type_* is a class, the hook will also be used for
        unmarshalling to subclasses of *type_*, unless a more specific hook
        can be found.
        """
        hook = fn if isinstance(fn, Hook) else Hook(fn, False)
        if hook.takes_args:
            hook_impl = hook.fn
        else:
            hook_impl = lambda obj, _, __: hook.fn(obj)
        self._unmarshal_hook_impl[type_] = hook_impl
        self._unmarshal_hooks.add(hook_impl)
        if getattr(type_, '__mro__', None) is not None:
            lookup = lambda _, __, ___: hook_impl
            self._unmarshal_lookup_dispatch.register(type_, lookup)
            self._unmarshal_impl_cache.clear()

    def lookup_unmarshal_impl(self, cls, type_hint):
        """
        Return the implementation and resolved type for unmarshalling data of
        type *cls* to an object of type *type_int*.

        The resolved type is the same as *type_hint*, except for union types,
        where it is one of the members of the union.
        """
        if type_hint is Any:
            return IDENTITY, type_hint
        elif type_hint in self._unmarshal_hook_impl:
            return self._unmarshal_hook_impl[type_hint], type_hint
        elif getattr(type_hint, '__mro__', None) is not None:
            lookup = self._unmarshal_lookup_dispatch.dispatch(type_hint)
            impl = lookup(cls, type_hint, self)
            if impl is _unmarshal_default and attr.has(type_hint):
                return _unmarshal_attrs, type_hint
            return impl, type_hint
        else:
            origin = getattr(type_hint, '__origin__', None)
            if origin is Union:
                return _resolve_union(cls, type_hint, self)
            if origin is not None:
                if getattr(origin, '__mro__', None) is not None:
                    lookup = self._unmarshal_lookup_dispatch.dispatch(origin)
                    impl = lookup(cls, type_hint, self)
                    return impl, type_hint

        return _unmarshal_default, type_hint

    def clear_cache(self):
        """
        Clear all caches of the registry.

        This should not be necessary unless classes are modified at runtime.
        """
        self._marshal_impl_cache.clear()
        self._unmarshal_impl_cache.clear()
        self._marshal_impl_dispatch._clear_cache()
        self._unmarshal_lookup_dispatch._clear_cache()
        self._field_options_cache.clear()

    def _hook_exists_for(self, cls, type_hint):
        impl, _ = self.lookup_unmarshal_impl(cls, type_hint)
        return impl in self._unmarshal_hooks


DEFAULT_REGISTRY = Registry()

marshal = DEFAULT_REGISTRY.marshal
marshal_json = DEFAULT_REGISTRY.marshal_json
unmarshal = DEFAULT_REGISTRY.unmarshal
unmarshal_json = DEFAULT_REGISTRY.unmarshal_json
