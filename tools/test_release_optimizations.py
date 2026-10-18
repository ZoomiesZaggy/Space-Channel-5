import unittest
from release_optimizations import HOST_CMAKE_RELEASE, assert_release_cache, ensure_optimized_compile_flags, module_cflags

class ReleaseOptimizationTests(unittest.TestCase):
    def test_host_cache_contract(self):
        self.assertEqual(HOST_CMAKE_RELEASE[0], '-DCMAKE_BUILD_TYPE=Release')
        self.assertIn('-O3', HOST_CMAKE_RELEASE[1])
        self.assertIn('-DNDEBUG', HOST_CMAKE_RELEASE[1])
        self.assertIn('-DNDEBUG', HOST_CMAKE_RELEASE[2])
        cache = '\n'.join([
            'CMAKE_BUILD_TYPE:STRING=Release',
            'CMAKE_C_FLAGS_RELEASE:STRING=-O3 -DNDEBUG',
            'CMAKE_CXX_FLAGS_RELEASE:STRING=-O3 -DNDEBUG',
        ])
        assert_release_cache(cache)

    def test_cache_rejects_debug_and_missing_ndebug(self):
        with self.assertRaises(SystemExit):
            assert_release_cache('CMAKE_BUILD_TYPE:STRING=Debug\n')
        with self.assertRaises(SystemExit):
            assert_release_cache('CMAKE_BUILD_TYPE:STRING=Release\nCMAKE_C_FLAGS_RELEASE:STRING=-O3 -DNDEBUG\n')

    def test_module_flags(self):
        self.assertEqual(module_cflags('2'), ['-O2', '-DNDEBUG'])
        self.assertEqual(module_cflags('1'), ['-O1'])
        self.assertEqual(module_cflags('0'), ['-O0'])
        with self.assertRaises(ValueError):
            module_cflags('3')

    def test_reused_compile_command(self):
        self.assertEqual(ensure_optimized_compile_flags(['-O3', '-DNDEBUG', '-c']), ['-O3', '-DNDEBUG', '-c'])
        self.assertEqual(ensure_optimized_compile_flags(['-O2']), ['-O2', '-DNDEBUG'])
        self.assertEqual(ensure_optimized_compile_flags(['-Wall']), ['-Wall', '-O3', '-DNDEBUG'])
        with self.assertRaises(RuntimeError):
            ensure_optimized_compile_flags(['-O0', '-g'])

if __name__ == '__main__':
    unittest.main()
