import json
import unittest
from collections import deque
from contextlib import contextmanager
from itertools import cycle
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class MockResponse:
    def __init__(self, *, status_code=200, payload=None, lines=None):
        self.status_code = status_code
        self._payload = payload
        self._lines = lines
        self.closed = False

    async def read(self):
        if self._payload is None:
            return b""
        return json.dumps(self._payload).encode("utf-8")

    async def aiter_lines(self):
        if self._lines is None:
            raise AssertionError("aiter_lines was called but no stream data was provided")
        for line in self._lines:
            yield line

    async def aclose(self):
        self.closed = True


@contextmanager
def mock_async_client(responses):
    response_queue = deque(responses)

    class _MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def build_request(self, *args, **kwargs):
            return {}

        async def send(self, request, stream=True):
            if not response_queue:
                raise AssertionError("No more mock responses available")
            return response_queue.popleft()

    with patch("main.httpx.AsyncClient", _MockAsyncClient):
        yield


class ProxyAPITestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        main.key_iterator = cycle(main.NETMIND_KEY_POOL)
        self.headers = {"Authorization": f"Bearer {main.MY_ACCESS_TOKEN}"}

    def test_missing_token_returns_401(self):
        response = self.client.post(
            "/v1/chat/completions",
            json={"model": "gpt-3.5-turbo", "messages": []}
        )
        self.assertEqual(response.status_code, 401)

    def test_non_stream_response_appends_advertisement(self):
        upstream_payload = {
            "choices": [
                {"message": {"content": "Original content"}}
            ]
        }
        with mock_async_client([MockResponse(payload=upstream_payload)]):
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False
                },
                headers=self.headers
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        self.assertTrue(content.endswith(main.AD_SUFFIX))

    def test_stream_response_injects_advertisement_before_done(self):
        upstream_lines = [
            'data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": null}]}',
            "",
            "data: [DONE]"
        ]

        with mock_async_client([MockResponse(lines=upstream_lines)]):
            with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True
                },
                headers=self.headers
            ) as response:
                streamed_lines = []
                for raw_line in response.iter_lines():
                    text_line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not text_line.strip():
                        continue
                    streamed_lines.append(text_line)

        ad_packet = json.dumps({
            "choices": [{
                "index": 0,
                "delta": {"content": main.AD_SUFFIX},
                "finish_reason": None
            }]
        })
        expected_ad_line = f"data: {ad_packet}"

        self.assertIn(expected_ad_line, streamed_lines)
        self.assertIn("data: [DONE]", streamed_lines)
        self.assertLess(
            streamed_lines.index(expected_ad_line),
            streamed_lines.index("data: [DONE]")
        )

    def test_retries_with_next_key_after_401(self):
        failure_response = MockResponse(status_code=401)
        success_payload = {
            "choices": [
                {"message": {"content": "Recovered"}}
            ]
        }

        with mock_async_client([failure_response, MockResponse(payload=success_payload)]):
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "测试"}],
                    "stream": False
                },
                headers=self.headers
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["choices"][0]["message"]["content"].endswith(main.AD_SUFFIX))


if __name__ == "__main__":
    unittest.main()
