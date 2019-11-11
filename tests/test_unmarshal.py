from typing import Any, List, Tuple, Set, FrozenSet, Dict, Optional

import attr
import pytest
from fieldmarshal import Registry, struct, unmarshal
from pytest import raises as assert_raises


@pytest.mark.parametrize('value', [
    1, 0, 0.1, 0.0, True, False, None,
])
def test_unmarshal_scalar(value):
    assert unmarshal(value, type(value)) is value


@pytest.mark.parametrize('value', [
    1, 0, 0.1, 0.0, True, False, None,
])
def test_unmarshal_scalar(value):
    assert unmarshal(value, Any) is value


@pytest.mark.parametrize('type_hint, result', [
    (list, [1, 2]),
    (List[int], [1, 2]),
    (tuple, (1, 2)),
    (Tuple[int, int], (1, 2)),
    (set, {1, 2}),
    (Set[int], {1, 2}),
    (frozenset, frozenset([1, 2])),
    (FrozenSet[int], frozenset([1, 2])),
])
def test_unmarshal_list(type_hint, result):
    assert unmarshal([1, 2], type_hint) == result


@pytest.mark.parametrize('value, type_hint, result', [
    ({'a': 1}, Dict[str, int], {'a': 1}),
    ({'1': 'a'}, Dict[int, str], {1: 'a'}),
    ({'true': 1, 'false': 0}, Dict[bool, int], {True: 1, False: 0}),
    ({'null': 0}, Dict[type(None), int], {None: 0}),
])
def test_unmarshal_dict(value, type_hint, result):
    assert unmarshal(value, type_hint) == result


def test_unmarshal_struct():
    @struct
    class Foo:
        value: int

    assert unmarshal({'value': 1}, Foo) == Foo(1)


def test_unmarshal_struct_nested():
    @struct
    class Foo:
        @struct
        class Bar:
            value: int
        bar: Bar

    assert unmarshal({'bar': {'value': 2}}, Foo) == Foo(Foo.Bar(2))


def test_unmarshal_class():
    class Foo:
        def __init__(self, value):
            self.value = value

    r = Registry()
    r.add_unmarshal_hook(Foo, lambda d: Foo(value=d['value']))
    assert r.unmarshal({'value': 1}, Foo).value == 1
    assert r.unmarshal({'value': 1}, Optional[Foo]).value == 1


@pytest.mark.parametrize('value', [1, '1', True, .1, None, [1], {'a': 1}])
@pytest.mark.parametrize('type_', [int, str, bool, float, type(None), list, dict])
def test_unmarshal_validate(value, type_):
    if isinstance(value, type_):
        assert unmarshal(value, type_) == value
    else:
        with assert_raises(TypeError):
            unmarshal(value, type_)


def test_unmarshal_validate_typing():
    with assert_raises(TypeError):
        unmarshal(1, List[str])

    with assert_raises(TypeError):
        unmarshal({'a': 1}, List[str, str])
