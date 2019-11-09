from enum import Enum, IntEnum, Flag, IntFlag, auto
from typing import Dict

from fieldmarshal import Registry, marshal, unmarshal


class MyStrEnum(Enum):
    A = 'a'


class MyBoolEnum(Enum):
    A = True


class MyFloatEnum(Enum):
    A = 0.1


class MyIntEnum(IntEnum):
    A = 1


class MyFlag(Flag):
    A = 1
    B = 2
    AB = 3


class MyIntFlag(IntFlag):
    A = auto()
    B = auto()


def test_marshal_enum():
    assert marshal(MyStrEnum.A) == 'a'
    assert marshal(MyBoolEnum.A) is True
    assert marshal(MyFloatEnum.A) == 0.1
    assert marshal(MyIntEnum.A) == 1
    assert marshal(MyFlag.A) == 1
    assert marshal(MyIntFlag.A) == 1


def test_marshal_flag():
    assert marshal(MyFlag.A & MyFlag.B) == 0
    assert marshal(MyFlag.A | MyFlag.B) == 3
    assert unmarshal(0, MyFlag) == MyFlag(0)
    assert unmarshal(3, MyFlag) == MyFlag.AB


def test_unmarshal_enum():
    assert unmarshal('a', MyStrEnum) is MyStrEnum.A
    assert unmarshal(True, MyBoolEnum) is MyBoolEnum.A
    assert unmarshal(0.1, MyFloatEnum) is MyFloatEnum.A
    assert unmarshal(1, MyIntEnum) is MyIntEnum.A
    assert unmarshal(1, MyFlag) is MyFlag.A
    assert unmarshal(1, MyIntFlag) is MyIntFlag.A


def test_marshal_enum_dict_keys():
    assert marshal({MyStrEnum.A: 1}) == {'a': 1}
    assert marshal({MyBoolEnum.A: 1}) == {'true': 1}
    assert marshal({MyFloatEnum.A: 1}) == {'0.1': 1}
    assert marshal({MyIntEnum.A: 1}) == {'1': 1}
    assert marshal({MyFlag.A: 1}) == {'1': 1}
    assert marshal({MyIntFlag.A: 1}) == {'1': 1}


def test_unmarshal_enum_dict_keys():
    assert unmarshal({'a': 1}, Dict[MyStrEnum, int]) == {MyStrEnum.A: 1}
    assert unmarshal({'1': 1}, Dict[MyIntEnum, int]) == {MyIntEnum.A: 1}
    assert unmarshal({'1': 1}, Dict[MyFlag, int]) == {MyFlag.A: 1}
    assert unmarshal({'1': 1}, Dict[MyIntFlag, int]) == {MyIntFlag.A: 1}


def test_unmarshal_enum_hooks():

    def unmarshal_bool_enum(v):
        return MyBoolEnum({'true': True}.get(v, v))

    def unmarshal_float_enum(v):
        return MyFloatEnum(float(v))

    r = Registry()
    r.add_unmarshal_hook(MyBoolEnum, unmarshal_bool_enum)
    r.add_unmarshal_hook(MyFloatEnum, unmarshal_float_enum)

    assert r.unmarshal('true', MyBoolEnum) is MyBoolEnum.A
    assert r.unmarshal({'true': 1}, Dict[MyBoolEnum, int]) == {MyBoolEnum.A: 1}

    assert r.unmarshal('0.1', MyFloatEnum) is MyFloatEnum.A
    assert r.unmarshal({'0.1': 1}, Dict[MyFloatEnum, int]) == {MyFloatEnum.A: 1}
