from enum import Enum
from pytest import raises as assert_raises
from typing import Any, Dict, Union

from fieldmarshal import marshal, unmarshal


class MyEnum(Enum):
    A = 'a'


def test_default():
    with assert_raises(TypeError):
        marshal({(1, 2): '1'})


def test_union():
    # Union[int, str] does not really work as a dict key for JSON
    assert unmarshal({'a': 1}, Dict[Union[int, str], Any]) == {'a': 1}
    assert unmarshal({'1': 1}, Dict[Union[int, str], Any]) == {'1': 1}
    assert unmarshal({'a': 1}, Dict[Union[int, MyEnum], Any]) == {MyEnum.A: 1}


def test_bool_none():
    assert unmarshal({'true': 1}, Dict[bool, int]) == {True: 1}
    assert unmarshal({'null': 1}, Dict[type(None), int]) == {None: 1}

    with assert_raises(ValueError):
        unmarshal({'x': 1}, Dict[bool, int])

    with assert_raises(ValueError):
        unmarshal({'x': 1}, Dict[type(None), int])

