"""Validated, atomic player settings shared by the launcher and tests."""
import os
import pathlib

ACTIONS = ('start', 'up', 'down', 'left', 'right', 'a', 'b', 'x', 'y')
KEYS = ('Return', 'Up', 'Down', 'Left', 'Right', 'Space', 'Backspace', 'Tab', 'Left Shift', 'Right Shift') + tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + tuple('0123456789')
PADS = ('start', 'back', 'a', 'b', 'x', 'y', 'dpup', 'dpdown', 'dpleft', 'dpright', 'leftshoulder', 'rightshoulder', 'leftstick', 'rightstick')
DEFAULTS = dict(gdi='', volume='100', audio_buffer_ms='64', texture_packs='0', fullscreen='0', window_scale='1', vsync='0')
DEFAULTS.update(zip(('key_' + a for a in ACTIONS), ('Return', 'Up', 'Down', 'Left', 'Right', 'Z', 'X', 'A', 'S')))
DEFAULTS.update(zip(('pad_' + a for a in ACTIONS), ('start', 'dpup', 'dpdown', 'dpleft', 'dpright', 'a', 'b', 'x', 'y')))

def validate(values):
    unknown = set(values) - set(DEFAULTS)
    if unknown:
        raise ValueError('Unknown settings: ' + ', '.join(sorted(unknown)))
    result = dict(DEFAULTS, **{k: str(v) for k, v in values.items()})
    for key, value in result.items():
        if any(c in value for c in '\r\n\0'):
            raise ValueError('Invalid characters in ' + key)
    for key, low, high in (('volume', 0, 100), ('audio_buffer_ms', 32, 128), ('texture_packs', 0, 1), ('fullscreen', 0, 1), ('window_scale', 1, 4), ('vsync', 0, 1)):
        if not result[key].isdigit() or not low <= int(result[key]) <= high:
            raise ValueError('Invalid ' + key)
    for prefix, allowed in (('key_', KEYS), ('pad_', PADS)):
        bindings = [result[prefix + a] for a in ACTIONS]
        if any(b not in allowed for b in bindings):
            raise ValueError('Invalid ' + prefix + 'binding')
        if len(set(bindings)) != len(bindings):
            raise ValueError('Each action needs a different ' + ('key' if prefix == 'key_' else 'controller button'))
    return result

def load(path):
    path = pathlib.Path(path)
    if not path.exists():
        return dict(DEFAULTS)
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            raise ValueError('Malformed settings line')
        values[key.strip()] = value.strip()
    return validate(values)

def save(path, values):
    values = validate(values)
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as output:
        output.write('# Space Channel 5 player settings\n')
        for key, value in values.items():
            output.write(f'{key}={value}\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
