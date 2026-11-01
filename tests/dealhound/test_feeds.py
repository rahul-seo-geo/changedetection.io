import json

from dealhound import feeds, provision


class Response:
    status_code = 200
    headers = {}

    def __init__(self, data):
        self.data = data
        self.content = data if isinstance(data, bytes) else b''

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class FeedSession:
    def get(self, url, **kwargs):
        return Response(b'<rss><channel><item><title>990 Pro 2TB $199 + $12-$16 Delivered</title><link>https://example.com/deal</link></item></channel></rss>')


def test_prices_and_keywords():
    assert feeds.parse_price('Deal $699 + $12-$16 Delivered') == 699
    assert feeds.parse_price('Now $ 1,299.50') == 1299.50
    assert feeds.parse_price('No price') is None
    assert feeds.matches('Samsung 990 Pro 2TB discounted', ['990 Pro 2TB'])
    assert not feeds.matches('X990 Pro 2TBX', ['990 Pro 2TB'])


def test_synthetic_entry_alert_once(tmp_path):
    item = {'name': 'SSD', 'keywords': ['990 Pro 2TB'], 'enabled': True, 'ozbargain_tags': [], 'target_price': 220}
    config = {'data_dir': tmp_path, 'webhook': 'https://example.com/webhook'}
    alerts = []
    def capture(candidate, webhook):
        alerts.append(candidate)
    assert feeds.ingest([item], config, session=FeedSession(), now=1000, send=capture) == 1
    assert feeds.ingest([item], config, session=FeedSession(), now=1400, send=capture) == 0
    assert len(alerts) == 1
    assert alerts[0]['price'] == 199
    assert len((tmp_path / 'candidates.jsonl').read_text().splitlines()) == 1


class WatchSession:
    def __init__(self):
        self.watches = {}
        self.puts = 0
        self.posts = 0

    def get(self, url, **kwargs):
        if url.endswith('/tag'):
            return Response({'tag-1': {'title': 'dealhound:SSD'}})
        if url.endswith('/watch'):
            return Response(self.watches)
        return Response(self.watches[url.rsplit('/', 1)[-1]])

    def post(self, url, json, **kwargs):
        self.posts += 1
        self.watches['watch-1'] = {**json, 'tags': ['tag-1']}
        return Response({'uuid': 'watch-1'})

    def put(self, url, json, **kwargs):
        self.puts += 1
        self.watches['watch-1'].update(json)
        return Response('OK')


def test_provision_second_run_is_noop():
    session = WatchSession()
    item = {'name': 'SSD', 'enabled': True, 'target_price': 220, 'urls': ['https://example.com/product']}
    config = {'base_url': 'http://localhost:5000', 'api_key': '', 'webhook': ''}
    assert provision.provision([item], config, session=session) == 1
    assert provision.provision([item], config, session=session) == 0
    assert (session.posts, session.puts) == (1, 0)


def test_discord_payload():
    from dealhound import discord_alert
    class Capture:
        def post(self, url, json, **kwargs):
            assert url == 'https://example.com/webhook'
            assert '```json\n' in json['content']
            payload = json_module.loads(json['content'].split('```json\n')[1].split('\n```')[0])
            assert payload['matched_item'] == 'SSD'
            return Response('OK')
    json_module = json
    assert discord_alert.alert({'matched_item': 'SSD', 'price': 19, 'feed_source': 'feed', 'link': 'https://example.com'},
                               'https://example.com/webhook', session=Capture())
