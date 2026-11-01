from urllib.parse import urlparse

import requests


def apprise_url(webhook):
    parsed = urlparse(webhook)
    parts = parsed.path.strip('/').split('/')
    if parsed.scheme != 'https' or parsed.hostname not in ('discord.com', 'discordapp.com') or len(parts) != 4 or parts[0:2] != ['api', 'webhooks'] or not all(parts[2:]):
        raise ValueError('Expected Discord HTTPS webhook URL')
    return f'discord://{parts[2]}/{parts[3]}'


def provision(items, config, session=None):
    session = session or requests.Session()
    base = config['base_url'] + '/api/v1/watch'
    headers = {'x-api-key': config['api_key']}
    response = session.get(base, headers=headers, timeout=20)
    response.raise_for_status()
    watches = response.json()
    tags_response = session.get(config['base_url'] + '/api/v1/tag', headers=headers, timeout=20)
    tags_response.raise_for_status()
    tags = {value['title']: uuid for uuid, value in tags_response.json().items()}
    notification = [apprise_url(config['webhook'])] if config['webhook'] else []
    changed = 0
    for item in items:
        if not item['enabled'] or not item['target_price']:
            continue
        tag = 'dealhound:' + item['name']
        for url in item['urls']:
            matches = [(uuid, watch) for uuid, watch in watches.items() if watch['url'] == url and tag in tags and tags[tag] in watch.get('tags', [])]
            if len(matches) > 1:
                raise ValueError('Duplicate Dealhound watches for ' + item['name'])
            # restock_diff extracts structured product price and applies its native below-price trigger.
            # The include filter is a CSS selector for the displayed price, where available.
            desired = {
                'url': url, 'title': tag, 'tag': tag,
                'processor': 'restock_diff',
                'include_filters': ['[itemprop="price"]'],
                'processor_config_restock_diff': {
                    'in_stock_processing': 'off', 'follow_price_changes': True,
                    'price_change_min': item['target_price'],
                },
                'notification_urls': notification,
                'time_between_check_use_default': False,
                'time_between_check': {'hours': 1},
            }
            if matches:
                uuid, _ = matches[0]
                current = session.get(base + '/' + uuid, headers=headers, timeout=20)
                current.raise_for_status()
                watch = current.json()
                config_matches = all(watch.get('processor_config_restock_diff', {}).get(key) == value
                                     for key, value in desired['processor_config_restock_diff'].items())
                if (config_matches and all(watch.get(key) == value for key, value in desired.items()
                                           if key not in ('tag', 'time_between_check', 'processor_config_restock_diff'))
                        and watch.get('time_between_check', {}).get('hours') == 1):
                    continue
                result = session.put(base + '/' + uuid, json={key: value for key, value in desired.items() if key != 'tag'}, headers=headers, timeout=20)
            else:
                result = session.post(base, json=desired, headers=headers, timeout=20)
            result.raise_for_status()
            changed += 1
    return changed
