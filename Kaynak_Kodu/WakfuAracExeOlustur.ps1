param([string]$OutputPath='')
$ErrorActionPreference='Stop'
$sourceDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot=if((Split-Path -Leaf $sourceDir)-eq'Kaynak_Kodu'){Split-Path -Parent $sourceDir}else{$sourceDir}
$output=if([string]::IsNullOrWhiteSpace($OutputPath)){Join-Path $projectRoot 'Wakfu_Turkce_Ceviri_Araci.exe'}else{[IO.Path]::GetFullPath($OutputPath)}
$outputDir=Split-Path -Parent $output
if(-not(Test-Path -LiteralPath $outputDir)){New-Item -ItemType Directory -Path $outputDir -Force|Out-Null}

$stage=Join-Path $env:TEMP ('WakfuArac_'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage|Out-Null
try{
    $package=Join-Path $stage 'app.zip'
    $packageRoot=Join-Path $stage 'app'
    foreach($relativeDir in @('Kaynak_Kodu','Ceviri_Verileri','Ayarlar','Uretilenler','Raporlar','Belgeler','Oyun_Kaynaklari\Fontlar','Oyun_Kaynaklari\Yamalar','Oyun_Kaynaklari\Orijinal_Yedek')){
        New-Item -ItemType Directory -Path (Join-Path $packageRoot $relativeDir) -Force|Out-Null
    }

    $sourceFiles=@(
        'WakfuTurkceCeviri.ps1','WakfuTurkceCeviri.bat','wakfu_gpu_translate.py','wakfu_audit.py',
        'build_wakfu_jar.py','apply_deterministic_repairs.py','recover_live_translations.py',
        'semantic_repairs_v120.py','semantic_repairs_v123.py','WakfuSetupApp.cs','WakfuSohbetCevirici.cs',
        'WakfuSetupOlustur.ps1','WakfuTurkceSetup.ps1','WakfuSetupBaslat.bat',
        'WakfuAracLauncher.cs','WakfuAracExeOlustur.ps1','WakfuTumPaketleriOlustur.ps1','WakfuFormatDogrula.ps1','WakfuDagitimDogrula.ps1','WakfuSohbetCeviriciOlustur.ps1',
        'WakfuKaynakYedekle.ps1','WakfuKaynakYedekle.bat'
    )
    foreach($name in $sourceFiles){
        $source=Join-Path $sourceDir $name
        if(-not(Test-Path -LiteralPath $source)){throw "Program bileşeni eksik: $source"}
        Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot ('Kaynak_Kodu\'+$name))
    }
    foreach($name in @('wakfu_tr_ceviri.json','terim_duzeltmeleri.json','manual_repairs_v23.json','Wakfu_GPU_Baglam.json')){
        $source=Join-Path $projectRoot ('Ceviri_Verileri\'+$name)
        if(Test-Path -LiteralPath $source){Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot ('Ceviri_Verileri\'+$name))}
    }
    $builtJar=Join-Path $projectRoot 'Uretilenler\i18n.jar'
    if(-not(Test-Path -LiteralPath $builtJar)){throw 'Güncel i18n.jar bulunamadı. Önce paket oluşturun.'}
    Copy-Item -LiteralPath $builtJar -Destination (Join-Path $packageRoot 'Uretilenler\i18n.jar')
    $chatTranslator=Join-Path $projectRoot 'Wakfu_Sohbet_Cevirici.exe'
    if(-not(Test-Path -LiteralPath $chatTranslator)){throw 'Güncel sohbet çeviricisi bulunamadı.'}
    Copy-Item -LiteralPath $chatTranslator -Destination (Join-Path $packageRoot 'Wakfu_Sohbet_Cevirici.exe')
    $baseJar=Join-Path $projectRoot 'Oyun_Kaynaklari\Orijinal_Yedek\i18n_en.jar'
    if(-not(Test-Path -LiteralPath $baseJar)){throw 'Temiz i18n_en.jar yedeği bulunamadı.'}
    Copy-Item -LiteralPath $baseJar -Destination (Join-Path $packageRoot 'Oyun_Kaynaklari\Orijinal_Yedek\i18n_en.jar')
    $almanaxPatch=Join-Path $projectRoot 'Oyun_Kaynaklari\Yamalar\almanax_bgU.class'
    if(-not(Test-Path -LiteralPath $almanaxPatch)){throw 'Almanax istemci yaması bulunamadı.'}
    Copy-Item -LiteralPath $almanaxPatch -Destination (Join-Path $packageRoot 'Oyun_Kaynaklari\Yamalar\almanax_bgU.class')
    $almanaxPatchSource=Join-Path $projectRoot 'Oyun_Kaynaklari\Yamalar\bgU.java'
    if(-not(Test-Path -LiteralPath $almanaxPatchSource)){throw 'Almanax istemci yamasının kaynak kodu bulunamadı.'}
    Copy-Item -LiteralPath $almanaxPatchSource -Destination (Join-Path $packageRoot 'Oyun_Kaynaklari\Yamalar\bgU.java')
    Get-ChildItem -LiteralPath (Join-Path $projectRoot 'Oyun_Kaynaklari\Fontlar') -Filter '*.ttf' -File|ForEach-Object{
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $packageRoot ('Oyun_Kaynaklari\Fontlar\'+$_.Name))
    }
    foreach($name in @('arayuz_ayarlari.json','gpu_runtime_path.txt')){
        $source=Join-Path $projectRoot ('Ayarlar\'+$name)
        if(Test-Path -LiteralPath $source){Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot ('Ayarlar\'+$name))}
    }
    foreach($name in @('README.txt','KAYNAK_KODU_BILGI.txt')){
        $source=Join-Path $projectRoot ('Belgeler\'+$name)
        if(Test-Path -LiteralPath $source){Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot ('Belgeler\'+$name))}
    }

    $mainScript=Join-Path $sourceDir 'WakfuTurkceCeviri.ps1'
    $versionMatch=[regex]::Match((Get-Content -LiteralPath $mainScript -Raw -Encoding UTF8),'\$AppVersion\s*=\s*''([^'']+)''')
    if(-not$versionMatch.Success){throw 'Dağıtım sürümü ana programdan okunamadı.'}
    $fileHashes=[ordered]@{}
    Get-ChildItem -LiteralPath $packageRoot -File -Recurse|Sort-Object FullName|ForEach-Object{
        $relative=$_.FullName.Substring($packageRoot.Length).TrimStart('\') -replace'\\','/'
        $fileHashes[$relative]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
    $distribution=[ordered]@{version=$versionMatch.Groups[1].Value;created=(Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK');files=$fileHashes;upgradeMode='atomic-swap-with-user-backup'}
    $distributionPath=Join-Path $packageRoot 'Ayarlar\dagitim_manifest.json'
    [IO.File]::WriteAllText($distributionPath,($distribution|ConvertTo-Json -Depth 5 -Compress),(New-Object Text.UTF8Encoding($false)))

    Compress-Archive -LiteralPath (Get-ChildItem -LiteralPath $packageRoot|ForEach-Object{$_.FullName}) -DestinationPath $package -CompressionLevel Optimal
    $launcherSource=Join-Path $sourceDir 'WakfuAracLauncher.cs'
    if(-not(Test-Path -LiteralPath $launcherSource)){throw 'WakfuAracLauncher.cs bulunamadı.'}
    $stagedLauncher=Join-Path $stage 'WakfuAracLauncher.cs'
    Copy-Item -LiteralPath $launcherSource -Destination $stagedLauncher
    $manifest=Join-Path $stage 'app.manifest'
    [IO.File]::WriteAllText($manifest,'<?xml version="1.0" encoding="utf-8"?><assembly manifestVersion="1.0" xmlns="urn:schemas-microsoft-com:asm.v1"><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false" /></requestedPrivileges></security></trustInfo></assembly>',[Text.Encoding]::UTF8)
    $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if(-not(Test-Path -LiteralPath $csc)){$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'}
    if(-not(Test-Path -LiteralPath $csc)){throw '.NET Framework C# derleyicisi bulunamadı.'}
    $tempExe=Join-Path $stage 'Wakfu_Turkce_Ceviri_Araci.exe'
    $rsp=Join-Path $stage 'compile.rsp'
    $response=@('/nologo','/target:winexe','/optimize+','/platform:anycpu',('/out:"'+$tempExe+'"'),('/win32manifest:"'+$manifest+'"'),'/reference:System.dll','/reference:System.Core.dll','/reference:System.Web.Extensions.dll','/reference:System.Windows.Forms.dll','/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',('/resource:"'+$package+'",WakfuTool.app.zip'),('"'+$stagedLauncher+'"'))
    [IO.File]::WriteAllLines($rsp,$response,(New-Object Text.UTF8Encoding($true)))
    $compiler=@(& $csc ('@'+$rsp) 2>&1)
    if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $tempExe)){throw ($compiler-join"`n")}
    Copy-Item -LiteralPath $tempExe -Destination $output -Force
    "OK|$output|$((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)"
}finally{
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
