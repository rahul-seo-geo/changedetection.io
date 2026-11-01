import json
import logging

import httpx
import requests

from . import dedupe, discord_alert, manifest

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
    content = response.json()['choices'][0]['message']['content'].strip()
    if content.startswith('```'):
        lines = content.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].startswith('```'):
            lines = lines[:-1]
        content = '\n'.join(lines).strip()
    result = json.loads(content)
    if result.get('verdict') not in ('keep', 'drop') or not isinstance(result.get('reason'), str):
        raise ValueError('Invalid judge verdict')
    return result


def judge(config, items=None, client=None, send=None):
    client = client or httpx.Client()
    send = send or discord_alert.alert
    if items is None:
        try:
            items = manifest.load()
        except Exception:
            items = []
    target_prices = {item['name']: item['target_price'] for item in items}

    db = dedupe.connect(config['data_dir'])
    completed = 0
    try:
        rows = db.execute('SELECT hash, link, title, price, matched_item, ts FROM deals WHERE judged=0').fetchall()
        for row in rows:
            digest, link, title, price, matched_item, ts = row
            target_price = target_prices.get(matched_item, 0)
            candidate = {
                'hash': digest,
                'link': link,
                'title': title,
                'price': price,
                'matched_item': matched_item,
                'target_price': target_price,
                'ts': ts
            }
            if not config['clef_base_url'] or not config['clef_api_key']:
                logger.warning('CLEF not configured; retaining candidate unjudged')
                continue
            try:
                result = verdict(candidate, config, client)
            except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError):
                logger.exception('Judge request failed; retaining candidate unjudged')
                continue

            if result['verdict'] == 'keep':
                try:
                    if config['webhook']:
                        success = send({**candidate, 'verdict': 'keep', 'reason': result['reason']}, config['webhook'])
                        if not success:
                            continue
                except (requests.RequestException, Exception):
                    logger.exception('Judged alert delivery failed; retaining unjudged status')
                    continue

            with db:
                db.execute('UPDATE deals SET judged=1 WHERE hash=?', (digest,))
            completed += 1
    finally:
        db.close()
    return completed
