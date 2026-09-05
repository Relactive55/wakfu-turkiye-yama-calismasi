param([switch]$SkipJarBuild)
$ErrorActionPreference='Stop'

# Windows PowerShell 5.1, BOM bulunmayan UTF-8 betikleri sistem ANSI kod
# sayfasıyla açar. Bu dosyadaki kullanıcıya gösterilen Türkçe sabitleri yazmadan
# önce özgün UTF-8 biçimine geri çevirerek dağıtım metinlerinde mojibake oluşmasını
# engelle.
function Restore-Utf8Literal([string]$text){
    # Yalnız tipik UTF-8/ANSI çakışma ön ekleri varsa onar. Desen ASCII kaçış
    # kullandığı için betiğin kendisi hangi kodlamayla açılırsa açılsın bozulmaz.
    if($text-notmatch'[\u00C2-\u00C5\u00E2]'){return $text}
    return [Text.Encoding]::UTF8.GetString([Text.Encoding]::Default.GetBytes($text))
}
$sourceDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot=if((Split-Path -Leaf $sourceDir)-eq'Kaynak_Kodu'){Split-Path -Parent $sourceDir}else{$sourceDir}
$main=Join-Path $sourceDir 'WakfuTurkceCeviri.ps1'
$versionMatch=[regex]::Match((Get-Content -LiteralPath $main -Raw -Encoding UTF8),'\$AppVersion\s*=\s*''([^'']+)''')
if(-not$versionMatch.Success){throw 'Dağıtım sürümü okunamadı.'}
$distributionVersion=$versionMatch.Groups[1].Value

if(-not$SkipJarBuild){
    $buildOutput=@(& powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File $main -BuildOnly 2>&1)
    if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath (Join-Path $projectRoot 'Uretilenler\i18n.jar'))){throw ($buildOutput-join"`n")}
}

$setupOutput=Join-Path $projectRoot 'Wakfu_Turkce_Yama_Setup.exe'
$setupResult=@(& (Join-Path $sourceDir 'WakfuSetupOlustur.ps1') -OutputPath $setupOutput 2>&1)
if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $setupOutput)){throw ($setupResult-join"`n")}

$toolOutput=Join-Path $projectRoot 'Wakfu_Turkce_Ceviri_Araci.exe'
$toolResult=@(& (Join-Path $sourceDir 'WakfuAracExeOlustur.ps1') -OutputPath $toolOutput 2>&1)
if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $toolOutput)){throw ($toolResult-join"`n")}

$verifyScript=Join-Path $sourceDir 'WakfuDagitimDogrula.ps1'
$verifyResult=@(& $verifyScript -SetupExe $setupOutput -ProgramExe $toolOutput -FullInstallSimulation 2>&1)
if($LASTEXITCODE-ne0-or@($verifyResult|Where-Object{[string]$_-like'OK|*'}).Count-eq0){throw ($verifyResult-join"`n")}

$rarExe='C:\Program Files\WinRAR\Rar.exe'
if(-not(Test-Path -LiteralPath $rarExe)){throw 'Kaynak paketi için WinRAR bulunamadı.'}
$sourceArchive=Join-Path $projectRoot 'Wakfu_Turkce_Ceviri_Araci_Kaynak.rar'
$tempArchive=Join-Path $env:TEMP ('WakfuKaynak_'+[Guid]::NewGuid().ToString('N')+'.rar')
try{
    # Arşiv açıldığında proje klasör yapısı birebir korunmalıdır. Tam yolları
    # -ep1 ile eklemek Fontlar/i18n.jar gibi öğelerin üst dizinini düşürüyordu.
    $items=@(
        'Kaynak_Kodu',
        'Ceviri_Verileri',
        'Ayarlar',
        'Belgeler',
        'Oyun_Kaynaklari\Fontlar',
        'Oyun_Kaynaklari\Yamalar\almanax_bgU.class',
        'Oyun_Kaynaklari\Yamalar\bgU.java',
        'Oyun_Kaynaklari\Orijinal_Yedek\i18n_en.jar',
        'Uretilenler\i18n.jar'
    )
    $arguments=@('a','-ma5','-m5','-r','-idq','-x*\__pycache__','-x*\__pycache__\*','-x*.pyc','-x*.tmp',$tempArchive)+$items
    Push-Location -LiteralPath $projectRoot
    try{$rarResult=@(& $rarExe $arguments 2>&1)}finally{Pop-Location}
    if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $tempArchive)){throw ($rarResult-join"`n")}
    Move-Item -LiteralPath $tempArchive -Destination $sourceArchive -Force
}finally{
    if(Test-Path -LiteralPath $tempArchive){Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue}
}

$summary=@(
    "PROGRAM|$toolOutput|$((Get-FileHash -LiteralPath $toolOutput -Algorithm SHA256).Hash)",
    "SETUP|$setupOutput|$((Get-FileHash -LiteralPath $setupOutput -Algorithm SHA256).Hash)",
    "SOURCE|$sourceArchive|$((Get-FileHash -LiteralPath $sourceArchive -Algorithm SHA256).Hash)"
)
$distributionRoot=Join-Path $projectRoot 'Dagitim'
$distributionDir=Join-Path $distributionRoot 'Wakfu_Turkce_Yama'
$resolvedRoot=[IO.Path]::GetFullPath($distributionRoot).TrimEnd('\')
$resolvedDir=[IO.Path]::GetFullPath($distributionDir).TrimEnd('\')
if(-not$resolvedDir.StartsWith($resolvedRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Geçersiz dağıtım hedefi: $resolvedDir"}
New-Item -ItemType Directory -Path $distributionRoot -Force|Out-Null
foreach($oldDir in @(Get-ChildItem -LiteralPath $resolvedRoot -Directory -ErrorAction SilentlyContinue|Where-Object{$_.Name-like'*-Portable'-and-not[String]::Equals($_.FullName.TrimEnd('\'),$resolvedDir,[StringComparison]::OrdinalIgnoreCase)})){
    $oldResolved=[IO.Path]::GetFullPath($oldDir.FullName).TrimEnd('\');if((Split-Path -Parent $oldResolved).TrimEnd('\')-ne$resolvedRoot-or(Split-Path -Leaf $oldResolved)-notlike'*-Portable'){throw "Geçersiz eski dağıtım hedefi: $oldResolved"};Remove-Item -LiteralPath $oldResolved -Recurse -Force
}
New-Item -ItemType Directory -Path $distributionDir -Force|Out-Null
Get-ChildItem -LiteralPath $resolvedDir -Force|Remove-Item -Recurse -Force
$publicSetup=Join-Path $resolvedDir 'Wakfu_Turkce_Yama_Setup.exe'
Copy-Item -LiteralPath $setupOutput -Destination $publicSetup -Force
$publicFiles=@(Get-ChildItem -LiteralPath $resolvedDir -File)
if($publicFiles.Count-ne1-or-not(Test-Path -LiteralPath $publicSetup)){throw 'Genel dağıtım klasörü yalnızca Türkçe yama kurulum EXE dosyasını içermelidir.'}
$summary+="DISTRIBUTION|$resolvedDir|$distributionVersion"
$summary+="PUBLIC_SETUP|$publicSetup|$((Get-FileHash -LiteralPath $publicSetup -Algorithm SHA256).Hash)"
$summary
