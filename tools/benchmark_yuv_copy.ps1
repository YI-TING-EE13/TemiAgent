[CmdletBinding()]
param(
    [ValidateRange(1, 100000)]
    [int]$WarmupIterations = 50,

    [ValidateRange(1, 10000)]
    [int]$Samples = 15,

    [ValidateRange(1, 100000)]
    [int]$IterationsPerSample = 20,

    [string]$JavaHomePath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$moduleRoot = Split-Path -Parent $PSScriptRoot
$classesDirectory = Join-Path $moduleRoot 'build\performance-benchmark\classes'
$productionSource = Join-Path $moduleRoot 'app\src\main\java\com\robotemi\agent\camera\Yuv420PlaneCopier.java'
$benchmarkSource = Join-Path $PSScriptRoot 'performance\Yuv420CopyBenchmark.java'

if ($JavaHomePath) {
    $javac = Join-Path $JavaHomePath 'bin\javac.exe'
    $java = Join-Path $JavaHomePath 'bin\java.exe'
} else {
    $javac = (Get-Command javac -ErrorAction Stop).Source
    $java = (Get-Command java -ErrorAction Stop).Source
}

if (-not (Test-Path -LiteralPath $javac) -or -not (Test-Path -LiteralPath $java)) {
    throw "Java compiler or runtime not found. Pass -JavaHomePath with a JDK directory."
}

New-Item -ItemType Directory -Force -Path $classesDirectory | Out-Null
& $javac -encoding UTF-8 -d $classesDirectory $productionSource $benchmarkSource
if ($LASTEXITCODE -ne 0) {
    throw "YUV benchmark compilation failed with exit code $LASTEXITCODE."
}

& $java `
    -cp $classesDirectory `
    com.robotemi.agent.camera.Yuv420CopyBenchmark `
    $WarmupIterations `
    $Samples `
    $IterationsPerSample
if ($LASTEXITCODE -ne 0) {
    throw "YUV benchmark failed with exit code $LASTEXITCODE."
}
