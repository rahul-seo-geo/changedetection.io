import json
import logging
import re
import time
from urllib.parse import quote

import feedparser
import requests

from . import dedupe, discord_alert

logger = logging.getLogger(__name__)
PRICE = re.compile(r'\$\s?\d[\d,]*(?:\.\d{1,2})?')
BASE_FEED = 'https://www.ozbargain.com.au/deals/feed'
USER_AGENT = 'dealhound/0.1 (+personal price watcher)'


def parse_price(title):
    match = PRICE.search(title)
    return float(match.group().replace('$', '').replace(',', '').strip()) if match else None


def matches(title, keywords):
    return any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', title, re.IGNORECASE) for word in keywords)


def feed_urls(items):
    tags = {tag for item in items if item['enabled'] for tag in item['ozbargain_tags']}
    return [BASE_FEED] + [f'https://www.ozbargain.com.au/tag/{quote(tag, safe="")}/feed' for tag in sorted(tags)]


def ingest(items, config, session=None, now=None, send=None):
    session = session or requests.Session()
    send = send or discord_alert.alert
    now = time.time() if now is None else now
    db = dedupe.connect(config['data_dir'])
    created = 0
    try:
        for url in feed_urls(items):
            row = db.execute('SELECT etag, modified, checked FROM feeds WHERE url=?', (url,)).fetchone()
            if row and now - row[2] < 300:
                continue
            headers = {'User-Agent': USER_AGENT}
            if row and row[0]:
                headers['If-None-Match'] = row[0]
            if row and row[1]:
                headers['If-Modified-Since'] = row[1]
            try:
                response = session.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                with db:
                    db.execute('INSERT OR REPLACE INTO feeds VALUES (?, ?, ?, ?)',
                               (url, response.headers.get('ETag', row[0] if row else None),
                                response.headers.get('Last-Modified', row[1] if row else None), now))
                if response.status_code == 304:
                    continue
                entries = feedparser.parse(response.content).entries
                for entry in entries:
                    title, link = entry.get('title', ''), entry.get('link', '')
                    if not link:
                        continue
                    for item in items:
                        if not item['enabled'] or not matches(title, item['keywords']):
                            continue
                        price = parse_price(title)
                        digest = dedupe.insert(db, link, title, price, item['name'])
                        if not digest:
                            continue
                        candidate = {'hash': digest, 'link': link, 'title': title, 'price': price,
                                     'matched_item': item['name'], 'target_price': item['target_price'],
                                     'feed_source': url, 'ts': now}
                        with (config['data_dir'] / 'candidates.jsonl').open('a', encoding='utf-8') as out:
                            out.write(json.dumps(candidate, ensure_ascii=False) + '\n')
                        created += 1
                        try:
                            send(candidate, config['webhook'])
                        except requests.RequestException:
                            logger.exception('Discord delivery failed')
            except requests.RequestException:
                logger.exception('Feed polling failed')
    finally:
        db.close()
    return created
