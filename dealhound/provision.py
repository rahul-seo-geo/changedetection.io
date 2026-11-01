import requests


def provision(items, config, session=None):
    session = session or requests.Session()
    base = config['base_url'] + '/api/v1/watch'
    headers = {'x-api-key': config['api_key']}
    response = session.get(base, headers=headers, timeout=20)
    response.raise_for_status()
    watches = response.json()
    tags_response = session.get(config['base_url'] + '/api/v1/tags', headers=headers, timeout=20)
    tags_response.raise_for_status()
    tags = {value['title']: uuid for uuid, value in tags_response.json().items()}
    changed = 0
    for item in items:
        if not item['enabled'] or not item['target_price']:
            continue
        tag = 'dealhound:' + item['name']
        for url_entry in item['urls']:
            url = url_entry if isinstance(url_entry, str) else url_entry['url']
            if isinstance(url_entry, dict):
                if 'css' in url_entry:
                    filters = [url_entry['css']] if isinstance(url_entry['css'], str) else url_entry['css']
                elif 'xpath' in url_entry:
                    filters = [url_entry['xpath']] if isinstance(url_entry['xpath'], str) else url_entry['xpath']
                elif 'json_path' in url_entry:
                    filters = [url_entry['json_path']] if isinstance(url_entry['json_path'], str) else url_entry['json_path']
                else:
                    filters = ['.a-price .a-offscreen']
            else:
                filters = ['.a-price .a-offscreen']

            matches = [(uuid, watch) for uuid, watch in watches.items() if watch['url'] == url and tag in tags and tags[tag] in watch.get('tags', [])]
            if len(matches) > 1:
                raise ValueError('Duplicate Dealhound watches for ' + item['name'])
            desired = {
                'url': url, 'title': tag, 'tag': tag,
                'processor': 'text_json_diff',
                'include_filters': filters,
                'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                            'Accept-Language': 'en-AU,en;q=0.9'},
                'time_between_check_use_default': False,
                'time_between_check': {'hours': 1},
            }
            if matches:
                uuid, _ = matches[0]
                current = session.get(base + '/' + uuid, headers=headers, timeout=20)
                current.raise_for_status()
                watch = current.json()
                if all(watch.get(key) == value for key, value in desired.items()
                       if key not in ('tag', 'time_between_check')) \
                        and watch.get('time_between_check', {}).get('hours') == 1:
                    continue
                result = session.put(base + '/' + uuid, json={key: value for key, value in desired.items() if key != 'tag'}, headers=headers, timeout=20)
            else:
                result = session.post(base, json=desired, headers=headers, timeout=20)
            result.raise_for_status()
            changed += 1
    return changed
