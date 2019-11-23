import attr
from fieldmarshal import Options, struct, field


def test_struct():
    @struct
    class Foo:
        value: int

    assert attr.has(Foo)
    assert attr.fields(Foo).value.type == int
    assert 'value' in Foo.__slots__


def test_field():
    @struct
    class Foo:
        value: int = field('v')

    assert attr.fields(Foo).value.metadata['fieldmarshal'] == Options(name='v')
