"""Optimization contract for binaries that ship to players.

Shipping hosts use a Release CMake build with an explicit ``-O3 -DNDEBUG``
compile line. Shipping native modules use ``-O2 -DNDEBUG``. Link-time
optimization is not enabled: the modules are large, the Windows execution
profile was collected at ``-O2`` without LTO, and LTO of the full host was
not validated here.
"""

HOST_CMAKE_RELEASE = (
    '-DCMAKE_BUILD_TYPE=Release',
    '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG',
    '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG',
)

_UNOPTIMIZED = {'-o0', '-og', '/od'}
_OPTIMIZED = {'-o2', '-o3', '/o2', '/ox'}


def module_cflags(opt):
    """C flags for one AOT module translation unit."""
    if opt not in {'0', '1', '2'}:
        raise ValueError('unsupported optimization level')
    flags = ['-O' + opt]
    # Only the shipping level strips assert(). Lower levels stay diagnosable.
    if opt == '2':
        flags.append('-DNDEBUG')
    return flags


def ensure_optimized_compile_flags(flags):
    """Keep a reused compiler command from dropping Release optimization.

    Returns the same list, appending ``-O3`` or ``-DNDEBUG`` when the command
    recorded by the reference build does not already contain them. A command
    that explicitly disables optimization is refused, because the rest of that
    build would be unoptimized too.
    """
    folded = {flag.lower() for flag in flags}
    if folded & _UNOPTIMIZED:
        raise RuntimeError('Compile command disables optimization. Configure the reference build as Release before linking the native host.')
    if not (folded & _OPTIMIZED):
        flags.append('-O3')
    if '-DNDEBUG' not in flags and '/DNDEBUG' not in flags:
        flags.append('-DNDEBUG')
    return flags


def assert_release_cache(text):
    """Refuse to package a host whose CMake cache is not the shipping Release contract."""
    lines = set(text.splitlines())
    required = (
        'CMAKE_BUILD_TYPE:STRING=Release',
        'CMAKE_C_FLAGS_RELEASE:STRING=-O3 -DNDEBUG',
        'CMAKE_CXX_FLAGS_RELEASE:STRING=-O3 -DNDEBUG',
    )
    missing = [line for line in required if line not in lines]
    if missing:
        raise SystemExit('Refusing to package a host that is not an optimized Release build: ' + ', '.join(missing))
