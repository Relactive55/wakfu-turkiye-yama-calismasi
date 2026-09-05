param([string]$OutputPath='')
$ErrorActionPreference='Stop'
$sourceDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot=if((Split-Path -Leaf $sourceDir)-eq'Kaynak_Kodu'){Split-Path -Parent $sourceDir}else{$sourceDir}
$output=if([string]::IsNullOrWhiteSpace($OutputPath)){Join-Path $projectRoot 'Wakfu_Turkce_Yama_Setup.exe'}else{[IO.Path]::GetFullPath($OutputPath)}
$outputDir=Split-Path -Parent $output
if(-not(Test-Path -LiteralPath $outputDir)){New-Item -ItemType Directory -Path $outputDir -Force|Out-Null}

$sourceCode=Join-Path $sourceDir 'WakfuSetupApp.cs'
$releaseUpdaterSource=Join-Path $sourceDir 'WakfuReleaseUpdater.cs'
$i18nJar=Join-Path $projectRoot 'Uretilenler\i18n.jar'
$translations=Join-Path $projectRoot 'Ceviri_Verileri\wakfu_tr_ceviri.json'
$terms=Join-Path $projectRoot 'Ceviri_Verileri\terim_duzeltmeleri.json'
$manual=Join-Path $projectRoot 'Ceviri_Verileri\manual_repairs_v23.json'
$baseJar=Join-Path $projectRoot 'Oyun_Kaynaklari\Orijinal_Yedek\i18n_en.jar'
$almanaxPatch=Join-Path $projectRoot 'Oyun_Kaynaklari\Yamalar\almanax_bgU.class'
$fontDir=Join-Path $projectRoot 'Oyun_Kaynaklari\Fontlar'
$fontNames=@('asul.ttf','asulb.ttf','bagnard.ttf','coprgtb.ttf','coprgtl.ttf','droidsansfallbackfull.ttf','fzlibian.ttf','londrina.ttf','lucidacally.ttf')
foreach($required in @($sourceCode,$i18nJar,$translations,$terms,$manual,$baseJar,$almanaxPatch)){if(-not(Test-Path -LiteralPath $required)){throw "Kurulum bileşeni eksik: $required"}}
foreach($font in $fontNames){if(-not(Test-Path -LiteralPath (Join-Path $fontDir $font))){throw "Kurulum fontu eksik: $font"}}

$staging=Join-Path $env:TEMP ('WakfuSetup_'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging|Out-Null
try{
    Copy-Item -LiteralPath $sourceCode -Destination (Join-Path $staging 'WakfuSetupApp.cs')
    Copy-Item -LiteralPath $releaseUpdaterSource -Destination (Join-Path $staging 'WakfuReleaseUpdater.cs')
    Copy-Item -LiteralPath $i18nJar -Destination (Join-Path $staging 'i18n.jar')
    Copy-Item -LiteralPath $baseJar -Destination (Join-Path $staging 'i18n_en.jar')
    Copy-Item -LiteralPath $translations -Destination (Join-Path $staging 'wakfu_tr_ceviri.json')
    Copy-Item -LiteralPath $terms -Destination (Join-Path $staging 'terim_duzeltmeleri.json')
    Copy-Item -LiteralPath $manual -Destination (Join-Path $staging 'manual_repairs_v23.json')
    Copy-Item -LiteralPath $almanaxPatch -Destination (Join-Path $staging 'almanax_bgU.class')
    foreach($font in $fontNames){Copy-Item -LiteralPath (Join-Path $fontDir $font) -Destination (Join-Path $staging $font)}

    $mainScript=Join-Path $sourceDir 'WakfuTurkceCeviri.ps1'
    $versionMatch=[regex]::Match((Get-Content -LiteralPath $mainScript -Raw -Encoding UTF8),'\$AppVersion\s*=\s*''([^'']+)''')
    if(-not$versionMatch.Success){throw 'Dağıtım sürümü ana programdan okunamadı.'}
    $resourceFiles=[ordered]@{
        'i18n.jar'=(Join-Path $staging 'i18n.jar');'base_i18n.jar'=(Join-Path $staging 'i18n_en.jar')
        'translations.json'=(Join-Path $staging 'wakfu_tr_ceviri.json');'terms.json'=(Join-Path $staging 'terim_duzeltmeleri.json')
        'manual.json'=(Join-Path $staging 'manual_repairs_v23.json');'almanax_bgU.class'=(Join-Path $staging 'almanax_bgU.class')
    }
    foreach($font in $fontNames){$resourceFiles[$font]=Join-Path $staging $font}
    $resourceHashes=[ordered]@{};foreach($item in $resourceFiles.GetEnumerator()){$resourceHashes[$item.Key]=(Get-FileHash -LiteralPath $item.Value -Algorithm SHA256).Hash}
    $distribution=[ordered]@{version=$versionMatch.Groups[1].Value;created=(Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK');resources=$resourceHashes;installMode='staged-verified-rollback'}
    $distributionPath=Join-Path $staging 'distribution_manifest.json'
    [IO.File]::WriteAllText($distributionPath,($distribution|ConvertTo-Json -Depth 5 -Compress),(New-Object Text.UTF8Encoding($false)))

    $manifest=Join-Path $staging 'setup.manifest'
    [IO.File]::WriteAllText($manifest,'<?xml version="1.0" encoding="utf-8"?><assembly manifestVersion="1.0" xmlns="urn:schemas-microsoft-com:asm.v1"><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="requireAdministrator" uiAccess="false" /></requestedPrivileges></security></trustInfo></assembly>',[Text.Encoding]::UTF8)
    $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if(-not(Test-Path -LiteralPath $csc)){$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'}
    if(-not(Test-Path -LiteralPath $csc)){throw '.NET Framework C# derleyicisi bulunamadı.'}
    $tempExe=Join-Path $staging 'Wakfu_Turkce_Yama_Setup.exe'
    $response=@('/nologo','/target:winexe','/optimize+','/platform:anycpu',('/out:"'+$tempExe+'"'),('/win32manifest:"'+$manifest+'"'),'/reference:System.dll','/reference:System.Core.dll','/reference:System.Web.Extensions.dll','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',('/resource:"'+(Join-Path $staging 'i18n.jar')+'",WakfuPatch.i18n.jar'),('/resource:"'+(Join-Path $staging 'i18n_en.jar')+'",WakfuPatch.base_i18n.jar'),('/resource:"'+(Join-Path $staging 'wakfu_tr_ceviri.json')+'",WakfuPatch.translations.json'),('/resource:"'+(Join-Path $staging 'terim_duzeltmeleri.json')+'",WakfuPatch.terms.json'),('/resource:"'+(Join-Path $staging 'manual_repairs_v23.json')+'",WakfuPatch.manual.json'),('/resource:"'+(Join-Path $staging 'almanax_bgU.class')+'",WakfuPatch.almanax_bgU.class'),('/resource:"'+$distributionPath+'",WakfuPatch.distribution_manifest.json'))
    foreach($font in $fontNames){$response+='/resource:"'+(Join-Path $staging $font)+'",WakfuPatch.'+$font}
    $response+='"'+(Join-Path $staging 'WakfuReleaseUpdater.cs')+'"'
    $response+='"'+(Join-Path $staging 'WakfuSetupApp.cs')+'"'
    $rsp=Join-Path $staging 'compile.rsp'
    [IO.File]::WriteAllLines($rsp,$response,(New-Object Text.UTF8Encoding($true)))
    $compilerOutput=@(& $csc ('@'+$rsp) 2>&1)
    if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $tempExe)){throw ($compilerOutput-join"`n")}
    $versionInfo=[Diagnostics.FileVersionInfo]::GetVersionInfo($tempExe)
    if($versionInfo.CompanyName-notlike'Wakfu*Yama*'-or$versionInfo.ProductName-notlike'Wakfu*Yama'-or$versionInfo.FileVersion-eq'0.0.0.0'){throw "Kurulum EXE kimlik bilgileri uretilemedi. Company='$($versionInfo.CompanyName)', Product='$($versionInfo.ProductName)', Version='$($versionInfo.FileVersion)'"}
    Copy-Item -LiteralPath $tempExe -Destination $output -Force
    "OK|$output|$((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)"
}finally{
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}
