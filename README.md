# fieldmarshal – marshal/unmarshal attrs-based data classes to and from JSON

[![Build Status](https://travis-ci.org/trendels/fieldmarshal.svg?branch=master)](https://travis-ci.org/trendels/fieldmarshal)

**Note: This is module is still in development - APIs might change in
backwards-incompatible ways.**

## Example

~~~python
>>> from fieldmarshal import struct, field, marshal, unmarshal
>>> from typing import List, Set
>>> @struct
... class Post:
...     title: str
...     tags: Set[str]
... 
>>> @struct
... class User:
...     id: int
...     name: str
...     posts: List[Post]
...     is_admin: bool = field("is-admin", default=False)
... 
>>> fred = User(1, "fred", [Post("hello world!", tags={"a", "b"})])
>>> data = marshal(fred)
>>> data
{'id': 1, 'name': 'fred', 'posts': [{'title': 'hello world!', 'tags': ['a', 'b']}], 'is-admin': False}
>>> assert unmarshal(data, User) == fred
>>>
~~~

The `struct` and `field` helpers are just convenience wrappers around `attr.s`
and `attr.ib`. The equivalent code with `attrs` is:

~~~python
>>> import attr
>>> from fieldmarshal import Options
>>> @attr.s(slots=True, auto_attribs=True)
... class User:
...     # ...
...     is_admin: bool = attr.ib(
...         default=False,
...         metadata={'fieldmarshal': Options(name="is-admin")},
...     )
>>>
~~~

This module provides marshalling/unmarshalling (or
serialization/deserialization) of [attrs][1]-based "data classes" to and from JSON.

The main goal is to make it easy to quickly build useful (partial) class
representations for real-world JSON data, such as those received from HTTP APIs
(See the `examples` subdirectory), and to allow efficient
marshalling/unmarshalling to and from JSON.

Features:

-   Support for renaming fields (see Example above).
-   Unknown/extra JSON keys are ignored by default.
-   Hook system to customize marshalling/unmarshalling of custom or complex
    types (e.g. `Union`s)
-   Built-in handling of common cases, such as `Enums`, simple `Union`s.
-   Limited support for non-string dict keys (bool, int, float, Enum).
-   Tries to be unobtrusive: Does not require subclassing and can work with
    plain `attr`s-based classes.

The API is inspired by Go's [`json.Marshal/json.Unmarshal`][2] and [cattrs][3].

[1]: https://www.attrs.org/
[2]: https://golang.org/pkg/encoding/json/
[3]: https://pypi.org/project/cattrs/
