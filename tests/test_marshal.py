from typing import List

import attr
import pytest
from fieldmarshal import Registry, struct, marshal
from pytest import raises as assert_raises


def test_marshal_default():
    with assert_raises(TypeError):
        marshal(object())


@pytest.mark.parametrize('value', [
    1, 0, 0.1, 0.0, True, False, None,
])
def test_marshal_scalar(value):
    assert marshal(value) is value


@pytest.mark.parametrize('value', [
    [1, 2, 3],
    (1, 2, 3),
    set([1, 2, 3]),
    frozenset([1, 2, 3]),
])
def test_marshal_list_tuple_set(value):
    assert marshal(value) == [1, 2, 3]


@pytest.mark.parametrize('value, result', [
    ({'a': 1}, {'a': 1}),
    ({1: 'a'}, {'1': 'a'}),
    ({True: 1, False: 0}, {'true': 1, 'false': 0}),
    ({None: 0}, {'null': 0}),
])
def test_marshal_dict(value, result):
    assert marshal(value) == result


@pytest.mark.skip
@pytest.mark.parametrize('value, type_hint', [
    ([1], List[int]),
    (['a'], List[str]),
    ([0.0], List[float]),
    ([True], List[bool]),
    ([None], List[type(None)]),
])
def test_marshal_list_type_hint(value, type_hint):
    assert marshal(value, type_hint) is value


def test_marshal_struct():
    @struct
    class Foo:
        value: int

    assert marshal(Foo(1)) == {'value': 1}


def test_marshal_struct_nested():
    @struct
    class Foo:
        @struct
        class Bar:
            value: int
        bar: Bar

    assert marshal(Foo(Foo.Bar(2))) == {'bar': {'value':2}}


def test_marshal_class():
    class Foo:
        def __init__(self, value):
            self.value = value

    r = Registry()
    r.add_marshal_hook(Foo, lambda f: {'value': f.value})
    assert r.marshal(Foo(1)) == {'value': 1}
