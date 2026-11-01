import json
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / 'watchlist' / 'dealhound.watchlist.json'


def load(path=DEFAULT_MANIFEST):
    items = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(items, list):
        raise ValueError('Watchlist must be an array')
    names = set()
    for item in items:
        if not isinstance(item, dict) or not {'name', 'keywords', 'urls', 'target_price', 'category', 'currency', 'enabled', 'ozbargain_tags'} <= item.keys():
            raise ValueError('Watchlist item missing required fields')
        if not isinstance(item['name'], str) or not item['name'] or item['name'] in names:
            raise ValueError('Watchlist names must be unique and nonempty')
        names.add(item['name'])
        for field in ('keywords', 'urls', 'ozbargain_tags'):
            if not isinstance(item[field], list) or not all(isinstance(x, str) and x for x in item[field]):
                raise ValueError(f'{field} must be a list of strings')
        if (not isinstance(item['target_price'], (int, float)) or isinstance(item['target_price'], bool)
                or item['target_price'] < 0 or item['currency'] != 'AUD'
                or not isinstance(item['enabled'], bool) or not isinstance(item['category'], str)):
            raise ValueError('Invalid watchlist item configuration')
        if any(not url.startswith('https://') for url in item['urls']):
            raise ValueError('Product URLs must use HTTPS')
    return items
