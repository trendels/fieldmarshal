import json
from enum import Enum, Flag, IntEnum, IntFlag
from functools import partial, singledispatch, wraps
from typing import Any, List, Tuple, Set, FrozenSet, Dict, Union

import attr

__version__ = '0.0.1'

__all__ = [
    'field',
    'marshal',
    'marshal_json',
    'struct',
    'unmarshal',
    'unmarshal_json'

    'Hook',
    'Options',
    'Registry',

    'DEFAULT_OPTIONS',
    'DEFAULT_REGISTRY',
]


struct = partial(attr.s, slots=True, auto_attribs=True)


@struct
class Options:
    """
    Field options control how a field is marshalled/unmarshalled.

    `name`
    :   Rename the field when marshalling/unmarshalling. Useful for example
    :   for JSON attribute names that are not valid Python identifiers.

    `omit`
    :   Ignore the field for the purpose of marshalling/unmarshalling. The
    :   field value will neither be read nor written to. The field should
    :   also have a default value for the class to support unmarshalling.

    `omit_if_none`
    :   Omit the field when marshalling if it's value is `None`. When
    :   unmarshalling, the field will be read as normal.

    `marshal`
    :   A function to call to marshal the contents of this field. The function
    :   will be passed the field value as its only argument. This hook
    :   overrides other marshal hooks registered for the field's type.

    `unmarshal`
    :   A function to call to unmarshal data for this field. The function
    :   will be passed the data being unmarshalled as its only argument. This
    :   hook overrides other unmarshal hooks registered for the field's type.
    """
    name: str = None
    omit: bool = False
    omit_if_none: bool = False
    marshal: Any = None
    unmarshal: Any = None


def field(name=None, omit=False, omit_if_none=False, marshal=None, unmarshal=None, **kw):
    """
    Wrapper around `attr.ib` that accepts additional arguments.

    Arguments that control marshalling are saved as an `Options` object
    in the fields metadata under the 'fieldmarshal' key.
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
SCALAR_TYPES = (int, bool, float, str, NONE_TYPE)


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
    if type_ in (int, float):
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


def _unmarshal_union(obj, type_hint, registry):
    cls = obj.__class__
    union_types = type_hint.__args__
    # Special-case Optional[]
    if NONE_TYPE in union_types:
        if obj is None:
            return None
        else:
            not_none = tuple(t for t in union_types if t is not NONE_TYPE)
            return registry.unmarshal(obj, Union[not_none])
    # TODO this is expensive and should be cached.
    if cls in union_types and not any([
            t for t in union_types
            if registry.lookup_unmarshal_impl(cls, t) in registry._unmarshal_hooks
        ]):
        return obj
    candidates = [t for t in union_types if t not in SCALAR_TYPES]
    if len(candidates) == 1:
        type_ = candidates[0]
        if registry.lookup_unmarshal_impl(cls, type_) not in registry._unmarshal_hooks:
            return registry.unmarshal(obj, type_)

    raise TypeError("Can't unmarshal to %s: %r" % (type_hint, obj))

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
    # in Python 3.6, List[int].__origin__ is List, etc.
    elif type_hint.__origin__ in {list, List}:
        return _unmarshal_list
    elif type_hint.__origin__ in {tuple, Tuple}:
        return _unmarshal_tuple
    elif type_hint.__origin__ in {set, Set, frozenset, FrozenSet}:
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



@struct
class Hook:
    """
    Container for marshal or unmarshal hooks.

    Can be used to specify that the hook accepts additional arguments other
    than the object being marshalled/unmarshalled.

    When `takes_args` is True (the default), additional arguments will be
    passed to the hook. The type of arguments depends on the type of hook. See
    `Registry.add_marshal_hook` and `Registry.add_unmarshal_hook` for details.
    """
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

        The resulting data structure contains only objects of type
        `list`, `dict` (with string keys), `int`, `float`, `str`, `bool` or
        `NoneType` and can be converted to JSON without further modifications.

        The reverse operation is `unmarshal`.
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

        Like `marshal`, but converts the result to JSON.
        """
        return json.dumps(self.marshal(obj))

    def add_marshal_hook(self, type_, fn):
        """
        Add a custom marshal implementation for a type.

        The hook can either be a function that takes one argument (the object
        being marshalled), or a `Hook` object, which can be used to opt-in to
        receive the registry instance as an additional argument.

        The hook should return a JSON-compatible object. The hook will be
        called when an object of the specified type is encountered when
        marshalling. If `type_` is a class, the hook will also be used
        for instances of subclasses of `type_`, unless a more specific
        hook can be found.
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
        Return the marshal implementation that would be used for `cls`.
        """
        impl = self._marshal_impl_dispatch.dispatch(cls)
        if impl is _marshal_default and attr.has(cls):
            return _marshal_attrs
        return impl

    def unmarshal(self, obj, type_hint):
        """
        Unmarshal an object from a JSON-compatible data structure.

        The data structure must contain only objects of type `list`, `dict`
        (with string keys), `int`, `float`, `str`, `bool` or `NoneType`, such
        as returned by `marshal`.

        `type_hint` specifies the type of object to create. This can be a class
        or a concrete type from the `typing` module, such as `List[int]`.

        The reverse operation is `marshal`.
        """
        key = (obj.__class__, type_hint)
        try:
            impl = self._unmarshal_impl_cache[key]
        except KeyError:
            impl = self.lookup_unmarshal_impl(*key)
            self._unmarshal_impl_cache[key] = impl
        if impl is IDENTITY:
            return obj
        else:
            return impl(obj, type_hint, self)

    def unmarshal_json(self, data, type_hint):
        """
        Unmarshal an object from a JSON string.

        Like `unmarshal`, but accepts a data in JSON format.
        """
        return self.unmarshal(json.loads(data), type_hint)

    def add_unmarshal_hook(self, type_, fn):
        """
        Add a custom unmarshal implementation for a type.

        `type_` can be a class or a concrete type from the `typing` module,
        such as `Union[list, str]`. The hook can either be a function that
        takes one argument (the object being unmarshalled), or a `Hook` object,
        which can be used to opt-in to receive the type the object is being
        unmarshalled to and the registry instance as additional arguments. The
        type passed this way is not necessarily the type the hook was
        registered for (it could be a subclass, for example).

        The hook will be called when data needs to be marshalled to an object
        of the specified type. If `type_` is a class, the hook will also be
        used for instances of subclasses of `type_`, unless a more specific
        hook can be found.
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
        Return the unmarshal implementation that would be used for
        unmarshalling data of type `cls` to an object of type `type_hint`.
        """
        if type_hint is Any:
            return IDENTITY
        # TODO find impl for Type here if type_hint is Optional[Type]?
        if type_hint in self._unmarshal_hook_impl:
            return self._unmarshal_hook_impl[type_hint]
        elif getattr(type_hint, '__mro__', None) is not None:
            lookup = self._unmarshal_lookup_dispatch.dispatch(type_hint)
            impl = lookup(cls, type_hint, self)
            if impl is _unmarshal_default and attr.has(type_hint):
                return _unmarshal_attrs
            return impl
        else:
            #print('*** %s does not have mro' % type_hint)
            origin = getattr(type_hint, '__origin__', None)
            if origin is not None:
                if origin is Union:
                    return _unmarshal_union
                if getattr(origin, '__mro__', None) is not None:
                    lookup = self._unmarshal_lookup_dispatch.dispatch(origin)
                    impl = lookup(cls, type_hint, self)
                    return impl

        return _unmarshal_default

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


DEFAULT_REGISTRY = Registry()

marshal = DEFAULT_REGISTRY.marshal
marshal_json = DEFAULT_REGISTRY.marshal_json
unmarshal = DEFAULT_REGISTRY.unmarshal
unmarshal_json = DEFAULT_REGISTRY.unmarshal_json
