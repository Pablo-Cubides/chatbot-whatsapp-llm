import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient

from fixed_server import app

client = TestClient(app)


def test_root_status():
    resp = client.get('/')
    assert resp.status_code == 200
    assert resp.json().get('status') == 'ok'


def test_test_endpoints_guarded():
    # When TEST_MODE not set, endpoints should be 404
    resp = client.post('/api/test/inject-message', json={'from': '+1', 'message': 'hi'})
    assert resp.status_code in (404, 422)

    resp = client.get('/api/test/messages')
    assert resp.status_code in (404, 422)


def test_test_endpoints_with_env(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    resp = client.post('/api/test/inject-message', json={'from': '+15551234567', 'message': 'E2E test ping'})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('status') == 'ok'

    resp2 = client.get('/api/test/messages')
    assert resp2.status_code == 200
    js = resp2.json()
    assert 'messages' in js
    assert isinstance(js['messages'], list)
