param(
    [string]$Gdi = $env:SC5_GDI,
    [uint64]$InstructionBudget = 50000000,
    [switch]$Render
)
$ErrorActionPreference = 'Stop'
$sc5Project = (Resolve-Path "$PSScriptRoot\..").Path
$sc5Workspace = $sc5Project
$sc5Compiler = (Get-ChildItem "$sc5Workspace\work\toolchain\*\bin\clang.exe").FullName
$sc5Reference = "$sc5Workspace\work\flycast-build\flycast.exe"
$env:PATH = (Split-Path $sc5Compiler) + ';' + $env:PATH
& "$sc5Workspace\work\build-tools\cmake\data\bin\cmake.exe" --build "$sc5Workspace\work\flycast-build" --parallel 6
if ($LASTEXITCODE) { throw 'Reference device/test build failed' }
python "$sc5Project\tools\boot_probe.py" --recorded-roots
if ($LASTEXITCODE) { throw 'AOT generation failed' }
& $sc5Compiler -O2 -std=c99 -shared -I "$sc5Project\build" "$sc5Project\tools\native_diff_exports.c" -o "$sc5Project\build\native-diff.dll"
if ($LASTEXITCODE) { throw 'Native DLL compilation failed' }
$env:SC5_NATIVE_DLL = "$sc5Project\build\native-diff.dll"
$env:SC5_IMAGE = "$sc5Project\extracted\1ST_READ.BIN"
$env:SC5_GDI = (Resolve-Path -LiteralPath $Gdi).Path
New-Item -ItemType Directory -Force "$sc5Workspace\work\native-runtime-data" | Out-Null
$env:SC5_RUNTIME_DATA = "$sc5Workspace\work\native-runtime-data\"
$env:SC5_INSTRUCTION_BUDGET = "$InstructionBudget"
$env:SC5_RAM_DUMP = "$sc5Project\build\native-last-ram.bin"
if ($Render) { $env:SC5_FRAME_OUTPUT = "$sc5Project\build\native-frame.ppm" } else { $env:SC5_FRAME_OUTPUT = $null }
$env:SC5_REFERENCE_TRACE = $null
& $sc5Reference '--gtest_filter=Sc5NativeDifferential.*' *> "$sc5Project\reports\reference-differential.txt"
$sc5TestResult = $LASTEXITCODE
Get-Content "$sc5Project\reports\reference-differential.txt"
if ($sc5TestResult) { throw "Reference checks failed: $sc5TestResult" }
