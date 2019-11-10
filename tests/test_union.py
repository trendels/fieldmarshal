from typing import Optional, Union

from fieldmarshal import Registry, Hook, struct, unmarshal
from pytest import raises as assert_raises


def test_unmarshal_union():
    assert unmarshal(1, Union[int, str]) == 1
    assert unmarshal('x', Union[int, str]) == 'x'


def test_unmarshal_optional():
    assert unmarshal(1, Optional[int]) == 1
    assert unmarshal(None, Optional[int]) is None


def test_unmarshal_union_no_hooks():
    @struct
    class Foo:
        value: int

    @struct
    class Bar:
        name: str

    assert unmarshal(1, Union[int, Foo]) == 1
    assert unmarshal(1, Union[int, Foo, Bar]) == 1
    assert unmarshal({'value': 1}, Union[int, Foo]) == Foo(1)

    with assert_raises(TypeError):
        unmarshal({'value': 1}, Union[Foo, Bar])

    assert unmarshal(None, Optional[Union[int, Foo]]) is None
    assert unmarshal(None, Optional[Union[Foo, Bar]]) is None


def test_resolve_union():
    @struct
    class Foo:
        value: int

    @struct
    class Bar:
        name: str

    def unmarshal_union_foo_bar(obj, type_hint, registry):
        if 'value' in obj:
            return registry.unmarshal(obj, Foo)
        return registry.unmarshal(obj, Bar)

    r = Registry()
    r.add_unmarshal_hook(Union[Foo, Bar], Hook(unmarshal_union_foo_bar))

    assert r.unmarshal({'value': 1}, Union[Foo, Bar]) == Foo(1)
    assert r.unmarshal({'name': 'x'}, Union[Foo, Bar]) == Bar('x')
    assert r.unmarshal({'value': 1}, Union[Bar, Foo]) == Foo(1)
    assert r.unmarshal({'name': 'x'}, Union[Bar, Foo]) == Bar('x')

    assert r.unmarshal(None, Optional[Union[Foo, Bar]]) is None
    assert r.unmarshal({'name': 'x'}, Union[Foo, Bar]) == Bar('x')
    assert r.unmarshal({'name': 'x'}, Optional[Union[Foo, Bar]]) == Bar('x')

    assert r.unmarshal(1, Union[int, Foo, Bar]) == 1
    assert r.unmarshal({'value': 1}, Union[int, Foo, Bar]) == Foo(1)

    @struct
    class Quux:
        value: str

    with assert_raises(TypeError):
        r.unmarshal(1 , Union[Foo, Bar, Quux])


def test_cant_unmarshal_union_types_having_hook():
    @struct
    class Foo:
        value: int

    class FooSubclass(Foo): pass

    r = Registry()
    r.add_unmarshal_hook(Foo, lambda v: Foo(v))

    assert r.unmarshal(1, Foo) == Foo(1)

    with assert_raises(TypeError):
        r.unmarshal(1, Union[int, Foo])

    with assert_raises(TypeError):
        r.unmarshal(1, Union[int, FooSubclass])

    assert r.unmarshal(None, Optional[Union[int, Foo]]) is None
    assert r.unmarshal(None, Optional[Union[int, FooSubclass]]) is None
