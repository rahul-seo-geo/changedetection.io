from dealhound import dedupe


def test_insert_once(tmp_path):
    db = dedupe.connect(tmp_path)
    first = dedupe.insert(db, 'https://example.com/a', 'Sale', 19.0, 'Example')
    assert first
    assert dedupe.insert(db, 'https://example.com/a', 'Sale', 19.0, 'Example') is None
    assert db.execute('SELECT count(*) FROM deals').fetchone()[0] == 1
    db.close()
