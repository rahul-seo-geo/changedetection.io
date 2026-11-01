import json

import httpx
import pytest

from dealhound import dedupe, judge


class FakeClient:
    def __init__(self, outcome, markdown_fence=False):
        self.outcome = outcome
        self.markdown_fence = markdown_fence

    def post(self, *args, **kwargs):
        if self.outcome == 'error':
            raise httpx.TimeoutException('timed out')
        class Response:
            def __init__(self, outcome, markdown_fence):
                self.outcome = outcome
                self.markdown_fence = markdown_fence
            def raise_for_status(self):
                pass
            def json(self):
                content = json.dumps({'verdict': self.outcome, 'reason': 'test'})
                if self.markdown_fence:
                    content = f"```json\n{content}\n```"
                return {'choices': [{'message': {'content': content}}]}
        return Response(self.outcome, self.markdown_fence)


@pytest.mark.parametrize('outcome,alerts,judged', [('keep', 1, 1), ('drop', 0, 1), ('error', 0, 0)])
def test_judge(outcome, alerts, judged, tmp_path):
    db = dedupe.connect(tmp_path)
    dedupe.insert(db, 'https://example.com/a', 'Deal $10', 10, 'SSD')
    db.close()
    config = {'data_dir': tmp_path, 'clef_base_url': 'http://localhost:1234', 'clef_api_key': 'fake',
              'judge_model': 'fake', 'webhook': 'https://example.com/webhook' if alerts else ''}
    sent = []
    items = [{'name': 'SSD', 'target_price': 20}]
    assert judge.judge(config, items=items, client=FakeClient(outcome), send=lambda candidate, webhook: (sent.append(candidate), True)[1]) == judged
    assert len(sent) == alerts
    db = dedupe.connect(tmp_path)
    assert db.execute('SELECT judged FROM deals').fetchone()[0] == judged
    db.close()


def test_judge_markdown_fenced_json(tmp_path):
    db = dedupe.connect(tmp_path)
    dedupe.insert(db, 'https://example.com/b', 'Deal $15', 15, 'GPU')
    db.close()
    config = {'data_dir': tmp_path, 'clef_base_url': 'http://localhost:1234', 'clef_api_key': 'fake',
              'judge_model': 'fake', 'webhook': 'https://example.com/webhook'}
    sent = []
    items = [{'name': 'GPU', 'target_price': 500}]
    assert judge.judge(config, items=items, client=FakeClient('keep', markdown_fence=True), send=lambda candidate, webhook: (sent.append(candidate), True)[1]) == 1
    assert len(sent) == 1
    db = dedupe.connect(tmp_path)
    assert db.execute('SELECT judged FROM deals').fetchone()[0] == 1
    db.close()


def test_judge_alert_failure_retains_unjudged(tmp_path):
    db = dedupe.connect(tmp_path)
    dedupe.insert(db, 'https://example.com/c', 'Deal $5', 5, 'SSD')
    db.close()
    config = {'data_dir': tmp_path, 'clef_base_url': 'http://localhost:1234', 'clef_api_key': 'fake',
              'judge_model': 'fake', 'webhook': 'https://example.com/webhook'}
    items = [{'name': 'SSD', 'target_price': 20}]
    # send returns False (alert failure)
    assert judge.judge(config, items=items, client=FakeClient('keep'), send=lambda candidate, webhook: False) == 0
    db = dedupe.connect(tmp_path)
    assert db.execute('SELECT judged FROM deals').fetchone()[0] == 0
    db.close()
