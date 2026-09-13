"""Assemble a personal native build without copying original disc tracks or test data."""
import argparse, hashlib, json, pathlib, shutil

ROOT=pathlib.Path(__file__).resolve().parents[1]
WORK=ROOT/'work'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=pathlib.Path,required=True)
parser.add_argument('--binary-dir',type=pathlib.Path,default=ROOT/'build',help='Validated executable and complete native DLL set')
args=parser.parse_args()
destination=args.output.resolve()
if destination==ROOT or ROOT in destination.parents:
    raise SystemExit('Choose an output directory outside the source project.')
if destination.exists() and any(destination.iterdir()):
    raise SystemExit('Output directory is not empty; existing files were left untouched.')
destination.mkdir(parents=True,exist_ok=True)

def copy(source,relative,allowed_root=ROOT):
    source=source.resolve()
    if not source.is_relative_to(allowed_root.resolve()):
        raise RuntimeError('Source resolves outside its expected directory: '+str(source))
    target=destination/relative
    if not target.resolve().is_relative_to(destination):
        raise RuntimeError('Invalid package-relative path')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)

for name in ['README.md','Start-native-development.cmd','Configure-and-play.cmd']:
    copy(ROOT/name,pathlib.Path(name))
for name in ['DEVELOPMENT.md','README-history.md','DEVELOPMENT-history.md','STEAM-CONTROLLER.md','PERFORMANCE-NOTES.md','PLAYER-GUIDE.md','ROADMAP.md','RELEASE-VALIDATION.md']:
    if (ROOT/name).exists():copy(ROOT/name,pathlib.Path(name))
for name in ['sc5-native-dev.exe','libwinpthread-1.dll','native-diff.dll']+[f'native-diff-round{i}.dll' for i in range(1,5)]:
    copy(args.binary_dir/name,pathlib.Path('build')/name,args.binary_dir)
for name in ['1ST_READ.BIN']+[f'ROUND{i}.BIN' for i in range(1,5)]:
    copy(ROOT/'extracted'/name,pathlib.Path('extracted')/name)
for folder in ['tools','licenses','prototype/Dreamcast-Forge/forge']:
    for source in (ROOT/folder).rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix!='.pyc':
            copy(source,source.relative_to(ROOT))
copy(ROOT/'prototype/Dreamcast-Forge/LICENSE',pathlib.Path('prototype/Dreamcast-Forge/LICENSE'))

evidence=['observed-roots.json','disc.json','flycast-reference.patch',
          'native-final-reference-tests.txt','native-credits-progression-validation.json',
          'native-vmu-persistence-validation.json','native-exact-checkpoint-validation.json',
          'native-inline-clock-validation.json','native-audio-pacing-validation.json',
          'native-inline-helper-validation.json','native-inline-helper-reference-tests.txt',
          'native-static-timing-validation.json','native-static-timing-binding-validation.json',
          'native-static-timing-reference-tests.txt',
          'native-final-performance-validation.json','native-final-checkpoint-validation.json',
          'native-final-round3-long.stdout.txt','native-final-round4-boss.stdout.txt',
          'native-final-round2-audio.stdout.txt','native-final-transition34.stdout.txt',
          *[f'native-final-round{i}-reference-tests.txt' for i in range(1,5)],
          'native-package-vmu-validation.json','native-package-vmu-load.stdout.txt',
          'native-package-vmu-loaded-report4.png','native-package-pause-validation.json',
          'native-package-paused.png','native-package-unpaused.png','native-package-integrity-validation.json',
          'native-unlimited-default.stdout.txt',
          'native-ending-credits.png','native-post-credits-title.png','native-vmu-fresh-load.png']
for name in evidence:
    if (ROOT/'reports'/name).exists():copy(ROOT/'reports'/name,pathlib.Path('reports')/name)
for record_name in ['native-clean-playthrough-validation.json',
                    'native-delivery-clean-validation.json',
                    'native-delivery-failure-flow-validation.json',
                    'native-delivery-controller-validation.json',
                    'native-polish-validation.json', 'native-release-prep-validation.json']:
    record=ROOT/'reports'/record_name
    if not record.exists():continue
    copy(record,pathlib.Path('reports')/record.name)
    for name in json.loads(record.read_text()).get('evidence',[]):
        if pathlib.Path(name).name!=name:raise RuntimeError('Invalid evidence filename')
        copy(ROOT/'reports'/name,pathlib.Path('reports')/name)

reference=WORK/'flycast-reference'
for source in reference.rglob('*'):
    if '.git' in source.parts or not source.is_file():continue
    if source.name.upper().startswith(('LICENSE','COPYING','NOTICE','COPYRIGHT','AUTHORS')) and source.stat().st_size<2000000:
        copy(source,pathlib.Path('licenses/flycast-source')/source.relative_to(reference),reference)
(destination/'SOURCE-PROVENANCE.md').write_text(
    '# Local source provenance\n\n'
    'This personal build uses the original USA GDI at runtime; disc tracks and private VMU test data are not packaged. '
    'The generator, native host sources, extracted executable images, dependency notices, and pinned-source patch are included.\n\n'
    'The pinned upstream Flycast source is reconstructed by `tools/setup_reference.py`; the included patch contains the local reference changes.\n\n'
    'Pinned revision: `eddf2635867f0f16f64bebd3185db151c99c551c`. '
    '`tools/setup_reference.py` records the pinned revision, dependencies, and build configuration. '
    'The original Forge decoder license is retained under `prototype/Dreamcast-Forge`.\n')
manifest={}
for source in destination.rglob('*'):
    if source.is_file():manifest[source.relative_to(destination).as_posix()]={
        'bytes':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(destination/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Packaged {len(manifest)} files in {destination}')
