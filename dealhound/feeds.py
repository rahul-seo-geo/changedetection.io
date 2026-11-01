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
DELIVERY_KEYWORDS = re.compile(r'\b(delivery|delivered|shipping|ship|postage|post|freight|deliv)\b', re.IGNORECASE)
BASE_FEED = 'https://www.ozbargain.com.au/deals/feed'
USER_AGENT = 'dealhound/0.1 (+personal price watcher)'


def parse_price(title):
    matches = list(PRICE.finditer(title))
    if not matches:
        return None
    prices_info = []
    for m in matches:
        val_str = m.group().replace('$', '').replace(',', '').strip()
        try:
            val = float(val_str)
        except ValueError:
            continue
        start, end = m.span()
        context_start = max(0, start - 15)
        context_end = min(len(title), end + 15)
        context = title[context_start:context_end]
        has_delivery = bool(DELIVERY_KEYWORDS.search(context))
        prices_info.append((val, has_delivery))
    if not prices_info:
        return None
    for val, has_delivery in prices_info:
        if not has_delivery:
            return val
    return prices_info[0][0]


def matches(title, keywords):
    for word in keywords:
        end_is_digit = word[-1].isdigit()
        suffix = r'(?!\d)\w*' if end_is_digit else r'\w*'
        pattern = r'(?<!\w)' + re.escape(word) + suffix + r'(?!\w)'
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False


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
        # Re-send unalerted rows on each cycle (at-least-once)
        unalerted = db.execute('SELECT hash, link, title, price, matched_item FROM deals WHERE alerted=0').fetchall()
        for row in unalerted:
            digest, link, title, price, matched_item = row
            candidate = {'hash': digest, 'link': link, 'title': title, 'price': price,
                         'matched_item': matched_item, 'target_price': 0, 'feed_source': 'retry', 'ts': now}
            try:
                if not config['webhook'] or send(candidate, config['webhook']):
                    with db:
                        db.execute('UPDATE deals SET alerted=1 WHERE hash=?', (digest,))
            except requests.RequestException:
                logger.exception('Unalerted deal redelivery failed')

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
                        created += 1
                        try:
                            if not config['webhook'] or send(candidate, config['webhook']):
                                # Mark alerted=1 ONLY after successful alert send (H1)
                                # Crash between send and mark = possible duplicate alert — acceptable
                                with db:
                                    db.execute('UPDATE deals SET alerted=1 WHERE hash=?', (digest,))
                        except requests.RequestException:
                            logger.exception('Discord delivery failed; leaving unalerted for retry')
            except requests.RequestException:
                logger.exception('Feed polling failed')
    finally:
        db.close()
    return created
