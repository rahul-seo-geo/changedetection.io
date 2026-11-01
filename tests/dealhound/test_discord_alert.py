import pytest
import requests
from dealhound import discord_alert


class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if 400 <= self.status_code < 500 and self.status_code != 429:
            raise requests.HTTPError(response=self)
        if 500 <= self.status_code < 600:
            raise requests.HTTPError(response=self)


class FakeSession:
    def __init__(self, statuses):
        self.statuses = statuses
        self.calls = 0

    def post(self, url, json, **kwargs):
        status = self.statuses[min(self.calls, len(self.statuses) - 1)]
        self.calls += 1
        resp = FakeResponse(status)
        if 400 <= status < 500 and status != 429:
            raise requests.HTTPError(response=resp)
        if 500 <= status < 600:
            raise requests.HTTPError(response=resp)
        return resp


def test_discord_alert_success():
    candidate = {'matched_item': 'Item', 'feed_source': 'source', 'link': 'https://example.com', 'price': 10}
    session = FakeSession([200])
    assert discord_alert.alert(candidate, 'https://example.com/webhook', session=session) is True


def test_discord_alert_retry_on_500():
    candidate = {'matched_item': 'Item', 'feed_source': 'source', 'link': 'https://example.com', 'price': 10}
    session = FakeSession([500, 200])
    assert discord_alert.alert(candidate, 'https://example.com/webhook', session=session) is True
    assert session.calls == 2


def test_discord_alert_fail_on_400():
    candidate = {'matched_item': 'Item', 'feed_source': 'source', 'link': 'https://example.com', 'price': 10}
    session = FakeSession([400])
    with pytest.raises(requests.HTTPError):
        discord_alert.alert(candidate, 'https://example.com/webhook', session=session)
