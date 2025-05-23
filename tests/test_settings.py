from app.settings import Settings


def test_settings_roundtrip(tmp_path):
    path = tmp_path / 'set.json'
    s = Settings(path)
    assert s.get('a') is None
    s.set('a', 1)
    assert s.get('a') == 1

    s2 = Settings(path)
    assert s2.get('a') == 1


def test_settings_invalid_json(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{oops}', encoding='utf-8')
    s = Settings(path)
    assert s.get('x') is None
