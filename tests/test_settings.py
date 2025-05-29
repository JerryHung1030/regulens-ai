from app.settings import Settings


def test_settings_roundtrip(tmp_path):
    path = tmp_path / 'set.json'
    s = Settings()
    s._path = path  # Override default path for testing
    assert s.get('a') is None
    s.set('a', 1)
    assert s.get('a') == 1

    s2 = Settings()
    s2._path = path # Override default path for testing
    s2._load() # Load data from the specified path
    assert s2.get('a') == 1


def test_settings_invalid_json(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{oops}', encoding='utf-8')
    s = Settings()
    s._path = path # Override default path for testing
    # Ensure _load is called after setting _path, if it wasn't called in __init__ with the new path
    s._load() 
    assert s.get('x') is None
