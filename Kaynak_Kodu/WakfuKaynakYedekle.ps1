param(
    [string]$Kaynak,
    [string]$HedefKok,
    [int]$SonNYedek = 5,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot=if((Split-Path -Leaf $ToolDir)-eq'Kaynak_Kodu'){Split-Path -Parent $ToolDir}else{$ToolDir}
if (-not $Kaynak) { $Kaynak = $ProjectRoot }

function Resolve-WakfuYedekRoot {
    param([string]$Override)
    if ($Override) { return [IO.Path]::GetFullPath((Join-Path $Override 'Kaynak_Yedek')) }
    $cfg = Join-Path $ProjectRoot 'Ayarlar\wakfu_yedek_hedef.txt'
    if (Test-Path -LiteralPath $cfg) {
        $line = [IO.File]::ReadAllText($cfg, [Text.UTF8Encoding]::new($true)).Trim().Split("`n")[0].Trim()
        if ($line) {
            $root = [IO.Path]::GetFullPath($line)
            if (-not (Test-Path -LiteralPath $root)) {
                New-Item -ItemType Directory -Path $root -Force | Out-Null
            }
            return [IO.Path]::GetFullPath((Join-Path $root 'Kaynak_Yedek'))
        }
    }
    if(Test-Path -LiteralPath (Join-Path $ProjectRoot 'Ceviri_Verileri\wakfu_tr_ceviri.json')){
        return [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'Yedekler\Kaynak_Yedek'))
    }
    # Eski klasör düzeni için geriye dönük bulma.
    $candidates = @()
    foreach ($proj in Get-ChildItem -Path 'D:\' -Directory -Filter 'PROJELER*' -ErrorAction SilentlyContinue) {
        foreach ($w in Get-ChildItem -LiteralPath $proj.FullName -Directory -Filter 'WAKFU*' -ErrorAction SilentlyContinue) {
            $final = Join-Path $w.FullName 'FINAL_KONTROL_RAPORU.txt'
            if (Test-Path -LiteralPath $final) {
                $candidates += $w.FullName
            }
        }
    }
    if ($candidates.Count -eq 1) {
        $pick = $candidates[0]
    } elseif ($candidates.Count -gt 1) {
        $pick = ($candidates | Where-Object { $_ -notmatch 'Ã|Ä' } | Select-Object -First 1)
        if (-not $pick) { $pick = $candidates[0] }
    }
    if ($pick) {
        [IO.File]::WriteAllText($cfg, $pick + [Environment]::NewLine, (New-Object Text.UTF8Encoding $true))
        return [IO.Path]::GetFullPath((Join-Path $pick 'Kaynak_Yedek'))
    }
    throw 'WAKFU ceviri klasoru bulunamadi. wakfu_yedek_hedef.txt olusturun veya -HedefKok verin.'
}

$Kaynak = [IO.Path]::GetFullPath($Kaynak)
$HedefKok = Resolve-WakfuYedekRoot -Override $HedefKok
$DRoot = Split-Path -Parent $HedefKok

if (-not (Test-Path -LiteralPath $Kaynak)) { throw "Kaynak bulunamadi: $Kaynak" }
New-Item -ItemType Directory -Path $HedefKok -Force | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$hedef = Join-Path $HedefKok $stamp
New-Item -ItemType Directory -Path $hedef -Force | Out-Null

$excludeDirs = @(
    'gpu_runtime', '__pycache__', '.git', '.cursor', 'node_modules',
    'terminals', '.venv', 'venv', '.mypy_cache', '.pytest_cache',
    'Yedekler', 'Raporlar', 'Uretilenler', 'Guncel'
)
$excludeDirNames = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($n in $excludeDirs) { [void]$excludeDirNames.Add($n) }

function Test-GitHuge {
    param([string]$Root)
    $git = Join-Path $Root '.git'
    if (-not (Test-Path -LiteralPath $git)) { return $false }
    $bytes = (Get-ChildItem -LiteralPath $git -Recurse -File -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    return ($bytes -gt 50MB)
}

$skipGit = Test-GitHuge -Root $Kaynak
if ($skipGit -and -not $excludeDirNames.Contains('.git')) { [void]$excludeDirNames.Add('.git') }

$dRootTsv = @{}
if (Test-Path -LiteralPath $DRoot) {
    Get-ChildItem -LiteralPath $DRoot -File -Filter '*.tsv' -ErrorAction SilentlyContinue |
        ForEach-Object { $dRootTsv[$_.Name.ToLowerInvariant()] = $_.Length }
}

function Test-SkipDuplicateTsv {
    param([System.IO.FileInfo]$File)
    if ($File.Extension -ne '.tsv') { return $false }
    $key = $File.Name.ToLowerInvariant()
    if (-not $dRootTsv.ContainsKey($key)) { return $false }
    return ($File.Length -eq $dRootTsv[$key])
}

function Test-SkipPath {
    param([string]$FullPath)
    $rel = $FullPath.Substring($Kaynak.Length).TrimStart('\', '/')
    if (-not $rel) { return $false }
    foreach ($part in $rel.Split([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)) {
        if ($excludeDirNames.Contains($part)) { return $true }
        if ($part -match '^(?i)WakfuArac_[0-9a-f]{32}$') { return $true }
    }
    return $false
}

$copied = 0
$skipped = 0
$totalBytes = [int64]0
$manifest = New-Object System.Collections.Generic.List[string]

Get-ChildItem -LiteralPath $Kaynak -Recurse -File -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
        if (Test-SkipPath -FullPath $_.FullName) { $script:skipped++; return }
        if ($_.Extension -eq '.tmp') { $script:skipped++; return }
        if (Test-SkipDuplicateTsv -File $_) { $script:skipped++; return }

        $rel = $_.FullName.Substring($Kaynak.Length).TrimStart('\', '/')
        $destFile = Join-Path $hedef $rel
        $destDir = Split-Path -Parent $destFile
        if (-not (Test-Path -LiteralPath $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        try {
            Copy-Item -LiteralPath $_.FullName -Destination $destFile -Force -ErrorAction Stop
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            [void]$manifest.Add("$hash|$rel|$($_.Length)")
            $script:copied++
            $script:totalBytes += $_.Length
        } catch {
            $script:skipped++
        }
    }

$manifestPath = Join-Path $hedef 'MANIFEST.sha256'
$manifest.ToArray() | Sort-Object | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$ozetPath = Join-Path $hedef 'YEDEK_OZET.txt'
$ozet = @(
    'WAKFU KAYNAK YEDEK OZETI'
    ('Tarih: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    ('Kaynak: ' + $Kaynak)
    ('Hedef: ' + $hedef)
    ('Dosya sayisi: ' + $copied)
    ('Atlanan: ' + $skipped)
    ('Toplam boyut (MB): ' + [math]::Round($totalBytes / 1MB, 2))
    ('SHA256 manifest: MANIFEST.sha256')
    ''
    'Haric tutulan:'
    '  gpu_runtime, __pycache__, terminal gecici klasorleri'
    if ($skipGit) { '  .git (buyuk)' } else { '  .git yok veya kucuk' }
    '  D kokundeki ayni boyutlu .tsv kopyalari'
    ''
    'Dahil:'
    '  .py .ps1 .cs .json .bat .txt .jar .ttf staging kalite_kontrol orijinal_yedek font_patch'
)
$ozet | Set-Content -LiteralPath $ozetPath -Encoding UTF8

$latestLink = Join-Path $HedefKok 'latest'
if (Test-Path -LiteralPath $latestLink) {
    Remove-Item -LiteralPath $latestLink -Recurse -Force -ErrorAction SilentlyContinue
}
try {
    cmd /c "mklink /J `"$latestLink`" `"$hedef`"" | Out-Null
} catch {
    Copy-Item -LiteralPath $hedef -Destination $latestLink -Recurse -Force
}

$allBackups = Get-ChildItem -LiteralPath $HedefKok -Directory |
    Where-Object { $_.Name -match '^\d{8}_\d{6}$' } |
    Sort-Object Name -Descending
if ($allBackups.Count -gt $SonNYedek) {
    $allBackups | Select-Object -Skip $SonNYedek | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
}

$result = "OK|$hedef|$copied|$([math]::Round($totalBytes/1MB,2))MB|$ozetPath"
if (-not $Quiet) { Write-Output $result }
$result
