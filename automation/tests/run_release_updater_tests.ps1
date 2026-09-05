$ErrorActionPreference='Stop'
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if(-not(Test-Path -LiteralPath $csc)){$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'}
if(-not(Test-Path -LiteralPath $csc)){throw 'C# compiler was not found.'}
$out=Join-Path $env:TEMP ('WakfuReleaseUpdaterTests_'+[Guid]::NewGuid().ToString('N')+'.exe')
try {
    $result=@(& $csc /nologo /define:WAKFU_TESTS /target:exe /main:ReleaseUpdaterTests /out:$out /reference:System.dll /reference:System.Core.dll /reference:System.Web.Extensions.dll /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll (Join-Path $root 'Kaynak_Kodu\WakfuReleaseUpdater.cs') (Join-Path $root 'Kaynak_Kodu\WakfuSetupApp.cs') (Join-Path $PSScriptRoot 'ReleaseUpdaterTests.cs') 2>&1)
    if($LASTEXITCODE-ne0){throw ($result-join"`n")}
    & $out
    if($LASTEXITCODE-ne0){throw 'Release updater tests failed.'}
} finally { Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue }
