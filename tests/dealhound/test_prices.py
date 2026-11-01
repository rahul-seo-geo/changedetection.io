from dealhound import prices


class Response:
    def __init__(self, data, text=''):
        self.data = data
        self.text = text

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class PriceSession:
    def __init__(self, watches, versions):
        self.watches = watches
        self.versions = versions

    def get(self, url, **kwargs):
        if url.endswith('/api/v1/watch'):
            return Response(self.watches)
        if url.endswith('/history'):
            uuid = url.split('/')[-2]
            return Response([str(ts) for ts in self.versions[uuid]])
        parts = url.split('/')
        return Response(None, text=self.versions[parts[-3]][int(parts[-1])])


def make_config(tmp_path):
    return {'base_url': 'http://localhost:5000', 'api_key': 'k',
            'webhook': 'https://example.com/webhook', 'data_dir': str(tmp_path)}


def capture(sent):
    def send(candidate, webhook):
        sent.append(candidate)
        return True
    return send


def fail(candidate, webhook):
    return False


SSD_WATCH = {'title': 'dealhound:SSD', 'url': 'https://example.com/p', 'tags': []}
SSD_ITEM = {'name': 'SSD', 'target_price': 600, 'enabled': True, 'keywords': [], 'urls': [], 'ozbargain_tags': []}


def test_above_target_price_does_not_alert(tmp_path):
    session = PriceSession({'watch-1': SSD_WATCH}, {'watch-1': {1690000000: '$591.23'}})
    sent = []
    item = dict(SSD_ITEM, target_price=500)
    assert prices.check(make_config(tmp_path), [item], session=session, send=capture(sent)) == 0
    assert sent == []


def test_target_hit_alerts_once(tmp_path):
    session = PriceSession({'watch-1': SSD_WATCH}, {'watch-1': {1690000000: '$591.23'}})
    sent = []
    send = capture(sent)
    config = make_config(tmp_path)
    assert prices.check(config, [SSD_ITEM], session=session, send=send) == 1
    assert prices.check(config, [SSD_ITEM], session=session, send=send) == 0
    assert len(sent) == 1
    assert sent[0]['matched_item'] == 'SSD'
    assert sent[0]['price'] == 591.23
    assert sent[0]['target_price'] == 600
    assert sent[0]['source'] == 'price-watch'


def test_price_drop_alerts_again(tmp_path):
    session = PriceSession({'watch-1': SSD_WATCH}, {'watch-1': {1690000000: '$591.23'}})
    sent = []
    config = make_config(tmp_path)
    assert prices.check(config, [SSD_ITEM], session=session, send=capture(sent)) == 1
    session.versions['watch-1'][1690100000] = '$549.00'
    assert prices.check(config, [SSD_ITEM], session=session, send=capture(sent)) == 1
    assert [candidate['price'] for candidate in sent] == [591.23, 549.00]


def test_failed_send_leaves_state_clear(tmp_path):
    session = PriceSession({'watch-1': SSD_WATCH}, {'watch-1': {1690000000: '$591.23'}})
    sent = []
    config = make_config(tmp_path)
    assert prices.check(config, [SSD_ITEM], session=session, send=fail) == 0
    assert prices.check(config, [SSD_ITEM], session=session, send=capture(sent)) == 1
    assert len(sent) == 1


def test_target_from_tag(tmp_path):
    watch = {'title': '990 Pro chat-added', 'url': 'https://example.com/990', 'tags': ['dealhound-target:600']}
    session = PriceSession({'watch-9': watch}, {'watch-9': {1690000000: '$579.99'}})
    sent = []
    assert prices.check(make_config(tmp_path), [], session=session, send=capture(sent)) == 1
    assert sent[0]['matched_item'] == 'https://example.com/990'
    assert sent[0]['target_price'] == 600
