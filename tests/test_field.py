from fieldmarshal import Registry, struct, field, marshal, unmarshal
from pytest import raises as assert_raises


def test_rename_field():
    @struct
    class Foo:
        my_field: int = field('my-field')

    assert marshal(Foo(my_field=1)) == {'my-field': 1}
    assert unmarshal({'my-field': 1}, Foo) == Foo(my_field=1)


def test_omit_fields():
    @struct(auto_attribs=False)
    class Foo:
        a = field(omit_if_none=True)
        b = field(omit=True, default=None)

    assert marshal(Foo(a=1, b=2)) == {'a': 1}
    assert marshal(Foo(a=None, b=2)) == {}
    assert unmarshal({'a': 1, 'b': 2}, Foo) == Foo(a=1, b=None)


def test_missing_default():
    @struct
    class Foo:
        a: int
        b: int = 2

    assert unmarshal({'a': 1}, Foo) == Foo(1, 2)

    with assert_raises(KeyError):
        assert unmarshal({'b': 1}, Foo)


def test_field_hooks():
    @struct
    class Foo:
        a: str = field(
            marshal=lambda s: '<%s>' % s,
            unmarshal=lambda s: s.strip('<>'),
        )

    assert marshal(Foo('x')) == {'a': '<x>'}
    assert unmarshal({'a': '<x>'}, Foo) == Foo('x')


def test_field_hooks_override_registry_hooks():
    class MyString(str): pass

    @struct
    class Foo:
        a: MyString = field(
            marshal=lambda s: '<%s>' % s,
            unmarshal=lambda s: s.strip('<>'),
        )

    r = Registry()
    r.add_marshal_hook(MyString, lambda s: '[%s]' % s)
    r.add_unmarshal_hook(MyString, lambda s: s.strip('[]'))

    assert r.marshal(Foo(MyString('x'))) == {'a': '<x>'}
    assert r.unmarshal({'a': '<x>'}, Foo) == Foo('x')
