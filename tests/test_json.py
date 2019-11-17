from fieldmarshal import marshal_json, unmarshal_json


def test_json():
    d = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
    s = marshal_json(d)
    assert s == '{"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}'
    assert unmarshal_json(s, dict) == d
