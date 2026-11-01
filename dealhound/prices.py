import logging
import re

import requests

from . import dedupe, discord_alert

logger = logging.getLogger(__name__)

PRICE = re.compile(r'\$\s?\d[\d,]*(?:\.\d{1,2})?')
TARGET_TAG = re.compile(r'^dealhound-target:(\d+(?:\.\d+)?)$')


def parse_price(text):
    match = PRICE.search(text or '')
    if not match:
        return None
    return float(match.group(0).replace('$', '').replace(',', '').strip())


def target_for(watch, target_prices, tag_titles=None):
    title = str(watch.get('title') or '')
    if title.startswith('dealhound:'):
        name = title[len('dealhound:'):]
        if name in target_prices and target_prices[name]:
            return target_prices[name]
    for tag in watch.get('tags') or []:
        match = TARGET_TAG.match((tag_titles or {}).get(str(tag), str(tag)))
        if match:
            return float(match.group(1))
    return None


def latest_content(session, base, headers, uuid):
    history = session.get(f'{base}/api/v1/watch/{uuid}/history', headers=headers, timeout=20)
    history.raise_for_status()
    versions = history.json()
    if not versions:
        return None
    timestamp = sorted(versions)[-1]
    content = session.get(f'{base}/api/v1/watch/{uuid}/history/{timestamp}', headers=headers, timeout=20)
    content.raise_for_status()
    return content.text


def check(config, items=None, session=None, send=None):
    session = session or requests.Session()
    send = send or discord_alert.alert
    if not config['webhook']:
        logger.warning('Discord webhook not configured; skipping price check')
        return 0
    if items is None:
        from . import manifest
        try:
            items = manifest.load()
        except Exception:
            items = []
    target_prices = {item['name']: item['target_price'] for item in items}

    base = config['base_url']
    headers = {'x-api-key': config['api_key']}
    listing = session.get(base + '/api/v1/watch', headers=headers, timeout=20)
    listing.raise_for_status()
    tags_response = session.get(base + '/api/v1/tags', headers=headers, timeout=20)
    tags_response.raise_for_status()
    tag_titles = {uuid: value.get('title') for uuid, value in tags_response.json().items()}
    watches = {uuid: watch for uuid, watch in listing.json().items()
               if str(watch.get('title') or '').startswith('dealhound:')
               or any(TARGET_TAG.match(tag_titles.get(str(t), str(t))) for t in (watch.get('tags') or []))}

    db = dedupe.connect(config['data_dir'])
    alerted = 0
    try:
        for uuid, watch in watches.items():
            target = target_for(watch, target_prices, tag_titles)
            if not target:
                continue
            try:
                content = latest_content(session, base, headers, uuid)
            except requests.RequestException:
                logger.exception('Price history fetch failed for %s', uuid)
                continue
            price = parse_price(content) if content else None
            if price is None or price > target:
                continue
            row = db.execute('SELECT last_alerted FROM price_state WHERE watch_uuid=?', (uuid,)).fetchone()
            if row and row[0] == price:
                continue
            candidate = {
                'watch_uuid': uuid,
                'matched_item': str(watch.get('title'))[len('dealhound:'):] if str(watch.get('title')).startswith('dealhound:') else watch.get('url'),
                'source': 'price-watch',
                'link': watch.get('url'),
                'price': price,
                'target_price': target,
                'content_excerpt': (content or '')[:80],
            }
            try:
                if not send(candidate, config['webhook']):
                    continue
            except Exception:
                logger.exception('Price alert delivery failed for %s', uuid)
                continue
            with db:
                db.execute('INSERT INTO price_state (watch_uuid, last_alerted) VALUES (?, ?) '
                           'ON CONFLICT(watch_uuid) DO UPDATE SET last_alerted=excluded.last_alerted', (uuid, price))
            alerted += 1
    finally:
        db.close()
    return alerted
