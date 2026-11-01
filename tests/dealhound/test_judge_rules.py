import json

import httpx
import pytest

from dealhound import dedupe, judge


class FakeClient:
    def __init__(self, outcome):
        self.outcome = outcome

    def post(self, *args, **kwargs):
        if self.outcome == 'error':
            raise httpx.TimeoutException('timed out')
        class Response:
            def __init__(self, outcome):
                self.outcome = outcome
            def raise_for_status(self):
                pass
            def json(self):
                return {'choices': [{'message': {'content': json.dumps({'verdict': self.outcome, 'reason': 'test'})}}]}
        return Response(self.outcome)


@pytest.mark.parametrize('outcome,alerts,judged', [('keep', 1, 1), ('drop', 0, 1), ('error', 0, 0)])
def test_judge(outcome, alerts, judged, tmp_path):
    db = dedupe.connect(tmp_path)
    digest = dedupe.insert(db, 'https://example.com/a', 'Deal $10', 10, 'SSD')
    db.close()
    candidate = {'hash': digest, 'matched_item': 'SSD', 'target_price': 20, 'title': 'Deal $10',
                 'link': 'https://example.com/a', 'price': 10, 'feed_source': 'feed'}
    (tmp_path / 'candidates.jsonl').write_text(json.dumps(candidate) + '\n')
    config = {'data_dir': tmp_path, 'clef_base_url': 'http://localhost:1234', 'clef_api_key': 'fake',
              'judge_model': 'fake', 'webhook': ''}
    sent = []
    assert judge.judge(config, client=FakeClient(outcome), send=lambda candidate, webhook: sent.append(candidate)) == judged
    assert len(sent) == alerts
    db = dedupe.connect(tmp_path)
    assert db.execute('SELECT judged FROM deals').fetchone()[0] == judged
    db.close()
    assert len((tmp_path / 'candidates.jsonl').read_text().splitlines()) == 1 - judged
