param([string]$OutputPath='')
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$sourceDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot=if((Split-Path -Leaf $sourceDir)-eq'Kaynak_Kodu'){Split-Path -Parent $sourceDir}else{$sourceDir}
$source=Join-Path $sourceDir 'WakfuSohbetCevirici.cs'
$output=if([string]::IsNullOrWhiteSpace($OutputPath)){Join-Path $projectRoot 'Wakfu_Sohbet_Cevirici.exe'}else{[IO.Path]::GetFullPath($OutputPath)}
if(-not(Test-Path -LiteralPath $source)){throw "Sohbet çeviricisi kaynak kodu bulunamadı: $source"}
$outputDir=Split-Path -Parent $output
if(-not(Test-Path -LiteralPath $outputDir)){New-Item -ItemType Directory -Path $outputDir -Force|Out-Null}
$stage=Join-Path $env:TEMP ('WakfuChat_'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage|Out-Null
try{
    $itemSourceCandidates=@(
        (Join-Path $projectRoot 'Oyun_Kaynaklari\Guncel\i18n_en.jar'),
        (Join-Path $projectRoot 'Oyun_Kaynaklari\Orijinal_Yedek\i18n_en.jar'),
        (Join-Path $projectRoot 'Uretilenler\i18n.jar')
    )
    $itemSource=$itemSourceCandidates|Where-Object{Test-Path -LiteralPath $_}|Select-Object -First 1
    if([string]::IsNullOrWhiteSpace($itemSource)){throw 'WAKFU eşya adları için i18n kaynağı bulunamadı.'}
    $itemNamesPath=Join-Path $stage 'wakfu_item_names.txt'
    $itemNames=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::OrdinalIgnoreCase)
    $zip=[IO.Compression.ZipFile]::OpenRead($itemSource)
    try{
        $entry=$zip.GetEntry('texts_en.properties');if($null-eq$entry){throw 'Eşya adları için texts_en.properties bulunamadı.'}
        $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
        try{
            while(($line=$reader.ReadLine())-ne$null){
                $split=$line.IndexOf('=');if($split-lt1){continue}
                $key=$line.Substring(0,$split);if($key-notmatch'^content\.15\.'){continue}
                $name=$line.Substring($split+1).Trim()
                if($name.Length-lt2-or$name.Length-gt100-or$name-match'\\[nrt]|[<>\[\]]'-or$name-notmatch'\p{L}{2}'){continue}
                if(-not$itemNames.ContainsKey($name)){$itemNames[$name]=$name}
            }
        }finally{$reader.Dispose()}
    }finally{$zip.Dispose()}
    if($itemNames.Count-lt10000){throw "WAKFU eşya adları listesi beklenenden küçük: $($itemNames.Count)"}
    $sortedNames=@($itemNames.Values|Sort-Object @{Expression={$_.Length};Descending=$true},@{Expression={$_};Descending=$false})
    [IO.File]::WriteAllLines($itemNamesPath,$sortedNames,(New-Object Text.UTF8Encoding($false)))
    $manifest=Join-Path $stage 'chat.manifest'
    [IO.File]::WriteAllText($manifest,'<?xml version="1.0" encoding="utf-8"?><assembly manifestVersion="1.0" xmlns="urn:schemas-microsoft-com:asm.v1"><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false" /></requestedPrivileges></security></trustInfo></assembly>',[Text.Encoding]::UTF8)
    $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if(-not(Test-Path -LiteralPath $csc)){$csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'}
    if(-not(Test-Path -LiteralPath $csc)){throw '.NET Framework C# derleyicisi bulunamadı.'}
    $tempExe=Join-Path $stage 'Wakfu_Sohbet_Cevirici.exe'
    $rsp=Join-Path $stage 'compile.rsp'
    $response=@('/nologo','/target:winexe','/optimize+','/platform:anycpu',('/out:"'+$tempExe+'"'),('/win32manifest:"'+$manifest+'"'),'/reference:System.dll','/reference:System.Core.dll','/reference:System.Drawing.dll','/reference:System.Net.Http.dll','/reference:System.Security.dll','/reference:System.Web.Extensions.dll','/reference:System.Windows.Forms.dll',('/resource:"'+$itemNamesPath+'",WakfuChat.item_names.txt'),('"'+$source+'"'))
    [IO.File]::WriteAllLines($rsp,$response,(New-Object Text.UTF8Encoding($true)))
    $compiler=@(& $csc ('@'+$rsp) 2>&1)
    if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $tempExe)){throw ($compiler-join"`n")}
    $versionInfo=[Diagnostics.FileVersionInfo]::GetVersionInfo($tempExe)
    if($versionInfo.CompanyName-notlike'Wakfu*Yama*'-or$versionInfo.ProductName-notlike'Wakfu*Yama'-or$versionInfo.FileVersion-eq'0.0.0.0'){throw "Sohbet ceviricisi EXE kimlik bilgileri uretilemedi. Company='$($versionInfo.CompanyName)', Product='$($versionInfo.ProductName)', Version='$($versionInfo.FileVersion)'"}
    $offlineResult=Join-Path $stage 'offline-test.txt'
    $offlineProcess=Start-Process -FilePath $tempExe -ArgumentList ('--offline-test='+$offlineResult) -WindowStyle Hidden -Wait -PassThru
    if($offlineProcess.ExitCode-ne0-or-not(Test-Path -LiteralPath $offlineResult)){throw "Sohbet çeviricisi çevrimdışı davranış testi çalışmadı. Çıkış: $($offlineProcess.ExitCode)"}
    $offlineText=Get-Content -LiteralPath $offlineResult -Raw -Encoding UTF8
    if($offlineText-notmatch'^OK\|ITEMS=\d+\|WTB=OK\|WTS=OK\|NAMES=OK'){throw "Sohbet çeviricisi çevrimdışı davranış testi başarısız: $offlineText"}
    Copy-Item -LiteralPath $tempExe -Destination $output -Force
    "OK|$output|$((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)|$($offlineText.Trim())"
}finally{
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
