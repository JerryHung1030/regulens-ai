import json
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
    # Adjust the call to match the new signature: project_id, input_doc_content, ref_doc_content, **scenario_params
    resp = client.compare(
        project_id="test_project",
        input_doc_content={'a': 1},
        ref_doc_content={'b': 2},
        param_in_scenario=3  # This will go into scenario_params
    )

    assert isinstance(resp, CompareResponse)
    payload = json.loads(captured['data'].decode())

    # Verify the new payload structure
    assert payload['project_id'] == "test_project"
    assert payload['input_data']['level1'][0]['text'] == {'a': 1}
    assert payload['input_data']['level1'][0]['sid'] == "input_test_project"
    assert payload['input_data']['level1'][0]['metadata']['project'] == "test_project"

    assert payload['reference_data']['level1'][0]['text'] == {'b': 2}
    assert payload['reference_data']['level1'][0]['sid'] == "ref_test_project"
    assert payload['reference_data']['level1'][0]['metadata']['project'] == "test_project"

    assert payload['scenario'] == {'param_in_scenario': 3}  # Check scenario_params
    assert captured['url'].endswith('/api/v1/rag')  # Check new endpoint
