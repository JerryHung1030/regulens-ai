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


def test_theme_setting(tmp_path):
    path = tmp_path / "theme_settings.json"
    
    # Test with first instance
    s1 = Settings()
    s1._path = path # Override path
    s1._data = {} # Ensure starting fresh for this test, overriding potential init load from default path
    s1._load() # Attempt to load from 'path', which shouldn't exist or be empty

    # Test default value
    assert s1.get('theme') == 'system' # Default from our updated get()
    assert s1.get('theme', 'light') == 'system' # Default should override provided default for 'theme'

    # Test setting and getting
    s1.set('theme', 'dark')
    assert s1.get('theme') == 'dark'

    s1.set('theme', 'light')
    assert s1.get('theme') == 'light'

    s1.set('theme', 'system')
    assert s1.get('theme') == 'system'

    # Test persistence with a new instance
    s2 = Settings()
    s2._path = path # Point to the same file
    s2._load() # Load the persisted data
    assert s2.get('theme') == 'system' # Should be 'system' as it was last set by s1

    # Test setting a different theme and checking with another new instance
    s2.set('theme', 'dark')
    
    s3 = Settings()
    s3._path = path
    s3._load()
    assert s3.get('theme') == 'dark'
