import pytest
from dealhound import manifest


def test_manifest_load_valid(tmp_path):
    watchlist = tmp_path / 'watchlist.json'
    watchlist.write_text('[{"name": "Item1", "keywords": ["kw"], "urls": ["https://example.com/item"], "target_price": 100, "category": "cat", "currency": "AUD", "enabled": true, "ozbargain_tags": ["tag"]}]', encoding='utf-8')
    items = manifest.load(watchlist)
    assert len(items) == 1
    assert items[0]['name'] == 'Item1'
    assert items[0]['urls'][0]['url'] == 'https://example.com/item'


def test_manifest_load_invalid(tmp_path):
    watchlist = tmp_path / 'watchlist.json'
    watchlist.write_text('{"not": "a list"}', encoding='utf-8')
    with pytest.raises(ValueError):
        manifest.load(watchlist)
