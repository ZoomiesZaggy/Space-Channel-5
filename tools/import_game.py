"""Import only required executables from the player's disc; never compile code."""
import hashlib
import os
from pathlib import Path
import shlex
import struct
import tempfile
from inspect_disc import Track

EXPECTED = {
    '1ST_READ.BIN': '4bf74525eb2e4922c732c8b708d7a542a3a8f33693afa62019abf241df56dfe5',
    'ROUND1.BIN': 'dce16d49c0943f5c96fdc8e7bbe18359997c52c241fc471a0bc0e81b555b8bd6',
    'ROUND2.BIN': 'd93dc9a12a79c87d507d6e733e7076c2df0b7316a015ee721b0251f03bebb901',
    'ROUND3.BIN': '41cf241037a6de36d5c72ae3620216482df0c418c10f5e18e8ae986e6beb7dd8',
    'ROUND4.BIN': '46893e0912b903271d3331830e137b22e26f71001f9b8b74ccd4bc7ad06de22f',
}

def installed(root):
    try:
        return all(hashlib.sha256((Path(root) / 'extracted' / name).read_bytes()).hexdigest() == digest
                   for name, digest in EXPECTED.items())
    except OSError:
        return False

def import_game(gdi, root):
    gdi, root = Path(gdi).resolve(), Path(root).resolve()
    lines = [line for line in gdi.read_text().splitlines() if line.strip()]
    if not lines or int(lines[0]) != len(lines) - 1:
        raise ValueError('Invalid GDI track count')
    tracks = []
    for line in lines[1:]:
        fields = shlex.split(line)
        if len(fields) != 6:
            raise ValueError('Invalid GDI track entry')
        number, lba, kind, sector, name, offset = fields
        if Path(name).name != name or any(c in name for c in '/\\:'):
            raise ValueError('Track files must be beside the GDI')
        path = gdi.parent / name
        if not path.is_file():
            raise ValueError('Missing disc track: ' + name)
        tracks.append((int(lba), int(kind), int(sector), path, int(offset)))
    candidates = [item for item in tracks if item[0] == 45000 and item[1:3] == (4, 2352)]
    if len(candidates) != 1:
        raise ValueError('Select the supported original USA GDI with 2352-byte data sectors')
    lba, _, _, path, offset = candidates[0]
    if offset < 0 or offset > path.stat().st_size or (path.stat().st_size-offset) % 2352:
        raise ValueError('Invalid data track size or offset')
    track = Track(path, lba, offset)
    try:
        pvd = track.read(lba+16, 2048)
        if pvd[:7] != b'\x01CD001\x01' or struct.unpack_from('<H', pvd, 128)[0] != 2048:
            raise ValueError('Unsupported disc filesystem')
        extent, size = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
        if size > 1024*1024:
            raise ValueError('Invalid disc directory size')
        directory = track.read(extent, size)
        files = {}
        position = 0
        while position < len(directory):
            length = directory[position]
            if not length:
                position = (position//2048+1)*2048
                continue
            record = directory[position:position+length]
            if length < 34 or len(record) != length or 33+record[32] > length:
                raise ValueError('Invalid disc directory record')
            position += length
            name = record[33:33+record[32]].decode('ascii').split(';')[0]
            if name not in EXPECTED:
                continue
            if name in files or record[25] & 130:
                raise ValueError('Ambiguous executable entry')
            file_lba, file_size = struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]
            if file_size != (0x260000 if name == '1ST_READ.BIN' else 0x80000):
                raise ValueError('Unsupported executable size: ' + name)
            data = track.read(file_lba, file_size)
            if hashlib.sha256(data).hexdigest() != EXPECTED[name]:
                raise ValueError('Unsupported game revision or damaged disc: ' + name)
            files[name] = data
        if set(files) != set(EXPECTED):
            raise ValueError('Required game executables were not found')
    finally:
        track.f.close()
    # Validate the entire import before replacing any installed executable.
    destination = root / 'extracted'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.import-', dir=destination) as temporary:
        for name, data in files.items():
            (Path(temporary) / name).write_bytes(data)
        for name in files:
            os.replace(Path(temporary) / name, destination / name)
    return len(files)
