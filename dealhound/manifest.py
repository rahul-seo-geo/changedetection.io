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
        for field in ('keywords', 'ozbargain_tags'):
            if not isinstance(item[field], list) or not all(isinstance(x, str) and x for x in item[field]):
                raise ValueError(f'{field} must be a list of strings')
        if not isinstance(item['urls'], list):
            raise ValueError('urls must be a list')
        normalized_urls = []
        for url_entry in item['urls']:
            if isinstance(url_entry, str):
                if not url_entry.startswith('https://'):
                    raise ValueError('Product URLs must use HTTPS')
                normalized_urls.append({'url': url_entry})
            elif isinstance(url_entry, dict):
                u = url_entry.get('url')
                if not isinstance(u, str) or not u.startswith('https://'):
                    raise ValueError('Product URLs must use HTTPS')
                for opt in ('css', 'xpath', 'json_path'):
                    if opt in url_entry and not isinstance(url_entry[opt], str):
                        raise ValueError(f'{opt} must be a string')
                normalized_urls.append(url_entry)
            else:
                raise ValueError('url entry must be a string or object')
        item['urls'] = normalized_urls
        if (not isinstance(item['target_price'], (int, float)) or isinstance(item['target_price'], bool)
                or item['target_price'] < 0 or item['currency'] != 'AUD'
                or not isinstance(item['enabled'], bool) or not isinstance(item['category'], str)):
            raise ValueError('Invalid watchlist item configuration')
    return items
