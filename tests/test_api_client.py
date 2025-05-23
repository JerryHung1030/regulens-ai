import json
from types import SimpleNamespace
from urllib import request

from app.api_client import ApiClient, CompareResponse


def test_compare_payload(monkeypatch):
    captured = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"result":"ok"}'

    def fake_urlopen(req, timeout=30):
        captured['url'] = req.full_url
        captured['data'] = req.data
        return FakeResp()

    monkeypatch.setattr(request, 'urlopen', fake_urlopen)

    client = ApiClient('http://example.com', 'token')
    resp = client.compare({'a': 1}, {'b': 2}, param=3)

    assert isinstance(resp, CompareResponse)
    payload = json.loads(captured['data'].decode())
    assert payload['input'] == {'a': 1}
    assert payload['reference'] == {'b': 2}
    assert payload['param'] == 3
    assert captured['url'].endswith('/v1/compare')
