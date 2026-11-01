import json
import logging

import httpx
import requests

from . import dedupe, discord_alert

logger = logging.getLogger(__name__)


def verdict(candidate, config, client):
    prompt = ("Given item name, target price and deal title/link/parsed price, decide relevance and deduplication. "
              "Return ONLY JSON with verdict 'keep' or 'drop' and a one-line reason. "
              "The parsed title price is an unverified signal, not a confirmed final price.\n"
              + json.dumps({key: candidate[key] for key in ('matched_item', 'target_price', 'title', 'link', 'price')}))
    response = client.post(config['clef_base_url'] + '/chat/completions',
                           headers={'Authorization': 'Bearer ' + config['clef_api_key']},
                           json={'model': config['judge_model'], 'messages': [{'role': 'user', 'content': prompt}],
                                 'response_format': {'type': 'json_object'}}, timeout=30)
    response.raise_for_status()
    result = json.loads(response.json()['choices'][0]['message']['content'])
    if result.get('verdict') not in ('keep', 'drop') or not isinstance(result.get('reason'), str):
        raise ValueError('Invalid judge verdict')
    return result


def judge(config, client=None, send=None):
    client = client or httpx.Client()
    send = send or discord_alert.alert
    path = config['data_dir'] / 'candidates.jsonl'
    if not path.exists():
        return 0
    db = dedupe.connect(config['data_dir'])
    completed = 0
    remaining = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            candidate = json.loads(line)
            row = db.execute('SELECT judged FROM deals WHERE hash=?', (candidate['hash'],)).fetchone()
            if not row or row[0]:
                continue
            if not config['clef_base_url'] or not config['clef_api_key']:
                logger.warning('CLEF not configured; retaining candidate')
                remaining.append(line)
                continue
            try:
                result = verdict(candidate, config, client)
            except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError):
                logger.exception('Judge request failed; retaining candidate')
                remaining.append(line)
                continue
            if result['verdict'] == 'keep':
                try:
                    send({**candidate, 'verdict': 'keep', 'reason': result['reason']}, config['webhook'])
                except requests.RequestException:
                    logger.exception('Judged alert delivery failed')
            with db:
                db.execute('UPDATE deals SET judged=1 WHERE hash=?', (candidate['hash'],))
            completed += 1
        path.write_text(''.join(line + '\n' for line in remaining), encoding='utf-8')
    finally:
        db.close()
    return completed
