import pathlib
import tempfile
import unittest
from player_config import DEFAULTS, load, save, validate

class PlayerConfigTests(unittest.TestCase):
    def test_roundtrip_path_with_spaces_and_equals(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / 'userdata/settings.ini'
            values = dict(DEFAULTS, gdi='D:/My Games/Disc = USA.gdi', native_mod='C:/My Mods/test = 1.dll', volume='0', rhythm_offset_ms='-100', key_a='Q')
            save(path, values)
            self.assertEqual(load(path), values)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_rejects_injection_and_ambiguous_bindings(self):
        for change in ({'gdi': 'x\nvolume=0'}, {'key_a': 'X'}, {'pad_a': 'b'}, {'volume': '-1'}, {'volume': '101'}, {'fullscreen': '2'}, {'key_a': 'FakeKey'}, {'unknown': '1'}, {'native_mod': 'relative.dll'}, {'native_mod': 'C:relative.dll'}, {'rhythm_offset_ms': '251'}, {'rhythm_offset_ms': '-251'}, {'rhythm_offset_ms': '1.5'}, {'rhythm_offset_ms': '--1'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(dict(DEFAULTS, **change))

    def test_invalid_save_preserves_existing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / 'settings.ini'
            save(path, DEFAULTS)
            before = path.read_bytes()
            with self.assertRaises(ValueError): save(path, dict(DEFAULTS, volume='broken'))
            self.assertEqual(path.read_bytes(), before)

    def test_missing_and_malformed_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / 'settings.ini'
            self.assertEqual(load(path), DEFAULTS)
            path.write_text('not a setting')
            with self.assertRaises(ValueError): load(path)

if __name__ == '__main__': unittest.main()
