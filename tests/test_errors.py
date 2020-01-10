from typing import List, Tuple

import pytest
from pytest import raises as assert_raises
from fieldmarshal import MarshalError, UnmarshalError, struct, marshal, unmarshal


@struct
class Foo:
    id: int


@pytest.mark.parametrize('data, type_hint, match', [
    (1, str, r"Can't unmarshal to .*str"),
    ({}, Foo, r'missing key: .*id'),
    ({'id': 'a'}, Foo, r"Can't unmarshal to .*int"),
    ([1], List[str], r"Can't unmarshal to .*str"),
    ([1], Tuple[int, int], r'Wrong number of elements'),
    ([1, 2, 3], Tuple[int, int], r'Wrong number of elements'),
])
def test_unmarshal_errors(data, type_hint, match):
    with assert_raises(UnmarshalError, match=match):
        unmarshal(data, type_hint)


@pytest.mark.parametrize('obj, match', [
    (object(), "Can't marshal .*object"),
    ({(1, 2): 1}, "Can't marshal dict key"),
])
def test_marshal_errors(obj, match):
    with assert_raises(MarshalError, match=match):
        marshal(obj)
