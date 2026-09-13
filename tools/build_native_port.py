"""Build the game-data-free native frontend directly with CMake on desktop hosts."""
import argparse
import os
import pathlib
import subprocess
from build_paths import ROOT, WORK

REVISION = 'eddf2635867f0f16f64bebd3185db151c99c551c'

def run(*command):
    subprocess.run([str(item) for item in command], check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    source = WORK / 'native-port-reference'
    build = WORK / 'native-port-build'
    WORK.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        run('git', 'clone', '--no-checkout', 'https://github.com/flyinghead/flycast.git', source)
        run('git', '-C', source, 'checkout', REVISION)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise RuntimeError('Unexpected reference revision')
    deps = ['SDL', 'libchdr', 'googletest', 'asio', 'xbyak', 'libjuice', 'websocketpp',
            'tinygettext', 'rcheevos', 'DreamPicoPort-API', 'freetype']
    run('git', '-C', source, 'submodule', 'update', '--init', '--depth', '1',
        *('core/deps/' + item for item in deps))
    for dep in ['tinygettext', 'DreamPicoPort-API']:
        run('git', '-C', source / 'core/deps' / dep, 'submodule', 'update', '--init', '--recursive', '--depth', '1')
    marker = source / '.sc5-native-host-setup'
    if not marker.exists():
        run('git', '-C', source, 'apply', ROOT / 'reports/flycast-reference.patch')
        tests = source / 'tests/CMakeLists.txt'
        tests.write_text('''# Standalone native entry point; no reference CPU test execution.
target_sources(${PROJECT_NAME} PRIVATE "${SC5_HOST_TOOLS}/native_app_main.cpp" "${SC5_HOST_TOOLS}/native_platform.cpp")
set_target_properties(${PROJECT_NAME} PROPERTIES OUTPUT_NAME sc5-native-dev MACOSX_BUNDLE FALSE WIN32_EXECUTABLE FALSE)
''')
        cmake = source / 'CMakeLists.txt'
        text = cmake.read_text()
        # The native host supplies its own event loop, write-fault watch and platform hooks.
        text = text.replace('core/linux/common.cpp', '')
        text = text.replace('elseif(APPLE)\n\t\tstring(TIMESTAMP YEAR', 'elseif(APPLE AND NOT SC5_HOST_TOOLS)\n\t\tstring(TIMESTAMP YEAR')
        text += '''
if(APPLE AND SC5_HOST_TOOLS)
  target_sources(${PROJECT_NAME} PRIVATE shell/apple/common/http_client.mm)
  target_link_libraries(${PROJECT_NAME} PRIVATE "-framework Foundation")
endif()
'''
        cmake.write_text(text)
        marker.write_text('1\n')
    run('cmake', '-S', source, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
        '-DENABLE_CTEST=ON', '-DBUILD_TESTING=ON', f'-DSC5_HOST_TOOLS={ROOT / "tools"}',
        '-DUSE_VULKAN=OFF', '-DUSE_DX9=OFF', '-DUSE_DX11=OFF', '-DUSE_BREAKPAD=OFF',
        '-DUSE_LUA=OFF', '-DUSE_OPENMP=OFF', '-DUSE_HOST_SDL=OFF', '-DUSE_HOST_LIBZIP=OFF',
        '-DCMAKE_POLICY_VERSION_MINIMUM=3.5')
    run('cmake', '--build', build, '--target', 'flycast', '--parallel', args.jobs)
    run(build / ('sc5-native-dev.exe' if os.name == 'nt' else 'sc5-native-dev'), '--help')

if __name__ == '__main__':
    main()
