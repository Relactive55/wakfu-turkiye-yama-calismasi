param(
    [Parameter(Mandatory=$true)][string]$SetupExe,
    [Parameter(Mandatory=$true)][string]$ProgramExe,
    [switch]$FullInstallSimulation
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Web.Extensions

function Get-StreamHash([IO.Stream]$Stream){
    $sha=[Security.Cryptography.SHA256]::Create()
    try{return ([BitConverter]::ToString($sha.ComputeHash($Stream))).Replace('-','')}finally{$sha.Dispose()}
}
function Read-ResourceText($assembly,[string]$name){
    $stream=$assembly.GetManifestResourceStream($name);if($null-eq$stream){throw "Gömülü bileşen bulunamadı: $name"}
    try{$reader=New-Object IO.StreamReader($stream,[Text.Encoding]::UTF8,$true);try{return $reader.ReadToEnd()}finally{$reader.Dispose()}}finally{if($stream){$stream.Dispose()}}
}
function Get-AssemblyFromFile([string]$path){return [Reflection.Assembly]::Load([IO.File]::ReadAllBytes([IO.Path]::GetFullPath($path)))}
function Get-JarEntryBytes([string]$path,[string]$entryName){
    $zip=[IO.Compression.ZipFile]::OpenRead($path)
    try{$entry=$zip.GetEntry($entryName);if($null-eq$entry){throw "JAR girdisi eksik: $entryName"};$stream=$entry.Open();$memory=New-Object IO.MemoryStream;try{$stream.CopyTo($memory);return $memory.ToArray()}finally{$memory.Dispose();$stream.Dispose()}}finally{$zip.Dispose()}
}
function Assert-RequiredTranslations($assembly){
    $expected=[ordered]@{
        'content.15.11955'='Dev Piwi Kesesi'
        'content.15.15865'=('Geni'+[char]0x015F+' Madenci Kutusu')
        'content.15.19799'=('Bile'+[char]0x015F+'en Sepeti')
        'content.15.31167'=('G'+[char]0x00F6+'ksel '+[char]0x00C7+'anta')
        'content.54.830'='Terrana Kumulu'
        'content.54.1415'='Terrana Kumulu'
        'content.54.1697'='Terrana Kumulu'
        'content.61.256'='Sufokia - Terrana Kumulu'
        'content.66.50501'='Terrana Kumulu'
        'content.66.67401'="Sufokia'daki Terrana Kumulu"
        'content.66.80901'='Terrana Kumulu'
        'content.66.95801'='Terrana Kumulu'
    }
    $resource=$assembly.GetManifestResourceStream('WakfuPatch.i18n.jar');if($null-eq$resource){throw 'Setup Türkçe metin paketi eksik.'}
    try{
        $zip=New-Object IO.Compression.ZipArchive($resource,[IO.Compression.ZipArchiveMode]::Read,$true)
        try{
            $entry=$zip.GetEntry('texts_en.properties');if($null-eq$entry){throw 'Setup Türkçe metin tablosu eksik.'}
            $found=@{};$reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
            try{
                while(($line=$reader.ReadLine())-ne$null){
                    $position=$line.IndexOf('=');if($position-lt1){continue}
                    $key=$line.Substring(0,$position);if($expected.Contains($key)){$found[$key]=$line.Substring($position+1)}
                }
            }finally{$reader.Dispose()}
            foreach($key in $expected.Keys){if(-not$found.ContainsKey($key)-or[string]$found[$key]-cne[string]$expected[$key]){throw "Zorunlu Turkce metin dogrulanamadi: $key"}}
        }finally{$zip.Dispose()}
    }finally{$resource.Dispose()}
}
function Test-SafeNameOverheadJar([string]$path){
    try{$data=Get-JarEntryBytes $path 'dde.class';if($data.Length-lt9-or$data[0]-ne0xCA-or$data[1]-ne0xFE-or$data[2]-ne0xBA-or$data[3]-ne0xBE){return $false};$safe=0;$original=0;$legacy=0;for($i=0;$i-le$data.Length-9;$i++){if($data[$i+3]-ne0x07-or$data[$i+4]-ne0x2A-or$data[$i+5]-ne0xB6-or$data[$i+8]-ne0xB1){continue};if($data[$i]-eq0x04-and$data[$i+1]-eq0x9A-and$data[$i+2]-eq0x00){$safe++};if($data[$i]-eq0x1B-and$data[$i+1]-eq0x9A-and$data[$i+2]-eq0x00){$original++};if($data[$i]-eq0xA7-and$data[$i+1]-eq0x00-and$data[$i+2]-eq0x08){$legacy++}};return $safe-eq1-and$original-eq0-and$legacy-eq0}catch{return $false}
}
function Test-HoverCompatibleNameToggleJar([string]$path){
    try{$entry='com/ankamagames/wakfu/client/console/command/display/ShowNameAndHighlightElementsCommand.class';$data=Get-JarEntryBytes $path $entry;if($data.Length-lt4-or$data[0]-ne0xCA-or$data[1]-ne0xFE-or$data[2]-ne0xBA-or$data[3]-ne0xBE){return $false};$patched=0;$original=0;for($i=0;$i-le$data.Length-4;$i++){if($data[$i]-eq0x00-and$data[$i+1]-eq0x00-and$data[$i+2]-eq0x00-and$data[$i+3]-eq0xB1){$patched++};if($data[$i]-eq0xB8-and$data[$i+3]-eq0xB1){$original++}};return $patched-eq1-and$original-eq0}catch{return $false}
}
function Test-PressOnlyNameShortcutJar([string]$path){
    try{$bytes=Get-JarEntryBytes $path 'shortcuts.xml';$text=[Text.Encoding]::UTF8.GetString($bytes);$expected='(?s)<shortcut\b(?=[^>]*\bid="showHideNameOverheadsCommand")(?=[^>]*\bkeyCode\s*=\s*"86")(?=[^>]*\bonKeyReleased\s*=\s*"false")[^>]*>';return [regex]::Matches($text,$expected,[Text.RegularExpressions.RegexOptions]::CultureInvariant).Count-eq1}catch{return $false}
}
function Get-JavaUtf8ConstantCounts([byte[]]$data,[string[]]$values){
    if($null-eq$data-or$data.Length-lt10-or$data[0]-ne0xCA-or$data[1]-ne0xFE-or$data[2]-ne0xBA-or$data[3]-ne0xBE){throw 'Geçersiz Java sınıfı.'}
    $wanted=[ordered]@{};foreach($value in $values){$wanted[$value]=[Text.Encoding]::UTF8.GetBytes($value)}
    $counts=[ordered]@{};foreach($value in $values){$counts[$value]=0}
    $constantPoolCount=([int]$data[8]-shl8)-bor[int]$data[9];$position=10
    for($index=1;$index-lt$constantPoolCount;$index++){
        if($position-ge$data.Length){throw 'Eksik Java sabit havuzu.'}
        $tag=[int]$data[$position];$position++
        switch($tag){
            1 {
                if($position+2-gt$data.Length){throw 'Eksik Java UTF-8 sabiti.'}
                $length=([int]$data[$position]-shl8)-bor[int]$data[$position+1];$start=$position+2
                if($start+$length-gt$data.Length){throw 'Eksik Java UTF-8 sabiti.'}
                foreach($value in $values){
                    $bytes=[byte[]]$wanted[$value];if($length-ne$bytes.Length){continue}
                    $same=$true;for($offset=0;$offset-lt$length;$offset++){if($data[$start+$offset]-ne$bytes[$offset]){$same=$false;break}}
                    if($same){$counts[$value]=1+[int]$counts[$value]}
                }
                $position=$start+$length
            }
            {$_-in3,4}{$position+=4}
            {$_-in5,6}{$position+=8;$index++}
            {$_-in7,8,16,19,20}{$position+=2}
            {$_-in9,10,11,12,17,18}{$position+=4}
            15 {$position+=3}
            default {throw "Desteklenmeyen Java sabit havuzu etiketi: $tag"}
        }
        if($position-gt$data.Length){throw 'Eksik Java sabit havuzu.'}
    }
    return $counts
}
function Test-OverheadTextScaleJar([string]$path,[ValidateSet('normal','small','tiny')][string]$profile){
    try{
        $font28='fontNarrow28BoldBordered';$font24='fontNarrow24BoldBordered';$font20='fontNarrow20BoldBordered';$font16='fontNarrow16BoldBordered'
        $counts=Get-JavaUtf8ConstantCounts (Get-JarEntryBytes $path 'dde.class') @($font28,$font24,$font20,$font16)
        $expected=switch($profile){
            'normal' {@{font28=1;font24=1;font20=0;font16=0}}
            'small'  {@{font28=0;font24=1;font20=1;font16=0}}
            'tiny'   {@{font28=0;font24=0;font20=1;font16=1}}
        }
        return [int]$counts[$font28]-eq$expected.font28-and[int]$counts[$font24]-eq$expected.font24-and[int]$counts[$font20]-eq$expected.font20-and[int]$counts[$font16]-eq$expected.font16
    }catch{return $false}
}
function Test-ProgramOverheadScaleContract([string]$scriptPath){
    if(-not(Test-Path -LiteralPath $scriptPath)){return $false}
    $text=Get-Content -LiteralPath $scriptPath -Raw -Encoding UTF8
    $checks=@(
        '\$script:OverheadTextScaleProfile\s*=\s*''tiny''',
        'OverheadTextScaleProfile',
        "Key='normal';Main=28;Title=24",
        "Key='small';Main=24;Title=20",
        "Key='tiny';Main=20;Title=16",
        'Items\.AddRange\(\[object\[\]\]@\(''Normal \(28 / 24\)''',
        '24 / 20',
        '20 / 16',
        'BasUstuYaziSecimi'
    )
    foreach($pattern in $checks){if($text-notmatch$pattern){return $false}}
    return $true
}

$setupAssembly=Get-AssemblyFromFile $SetupExe
$setupManifest=(Read-ResourceText $setupAssembly 'WakfuPatch.distribution_manifest.json')|ConvertFrom-Json
foreach($property in $setupManifest.resources.PSObject.Properties){
    $stream=$setupAssembly.GetManifestResourceStream('WakfuPatch.'+$property.Name);if($null-eq$stream){throw "Setup kaynağı eksik: $($property.Name)"}
    try{$actual=Get-StreamHash $stream}finally{$stream.Dispose()}
    if($actual-ne[string]$property.Value){throw "Setup kaynağı bozuk: $($property.Name)"}
}
Assert-RequiredTranslations $setupAssembly

$programAssembly=Get-AssemblyFromFile $ProgramExe
$packed=$programAssembly.GetManifestResourceStream('WakfuTool.app.zip');if($null-eq$packed){throw 'Ana programın gömülü paketi bulunamadı.'}
try{
    $zip=New-Object IO.Compression.ZipArchive($packed,[IO.Compression.ZipArchiveMode]::Read,$false)
    try{
        $manifestEntry=$zip.GetEntry('Ayarlar/dagitim_manifest.json');if($null-eq$manifestEntry){$manifestEntry=$zip.GetEntry('Ayarlar\dagitim_manifest.json')};if($null-eq$manifestEntry){throw 'Ana program dağıtım manifesti eksik.'}
        $reader=New-Object IO.StreamReader($manifestEntry.Open(),[Text.Encoding]::UTF8,$true);try{$programManifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
        foreach($property in $programManifest.files.PSObject.Properties){
            $entry=$zip.GetEntry($property.Name);if($null-eq$entry){$entry=$zip.GetEntry($property.Name.Replace('/','\'))};if($null-eq$entry){throw "Ana program bileşeni eksik: $($property.Name)"}
            $stream=$entry.Open();try{$actual=Get-StreamHash $stream}finally{$stream.Dispose()}
            if($actual-ne[string]$property.Value){throw "Ana program bileşeni bozuk: $($property.Name)"}
        }
    }finally{$zip.Dispose()}
}finally{$packed.Dispose()}
if([string]$setupManifest.version-ne[string]$programManifest.version){throw "Setup ve ana program sürümleri farklı: $($setupManifest.version) / $($programManifest.version)"}

if($FullInstallSimulation){
    $unicodeFixture=Join-Path $env:TEMP ('WakfuUnicodeTest_'+[Guid]::NewGuid().ToString('N'))
    try{
        $unicodeSourceDir=Join-Path $unicodeFixture 'PROJELERİM\WAKFU ÇEVİRİ\Uretilenler';$payloadDir=Join-Path $unicodeFixture 'transaction\payload';$targetDir=Join-Path $unicodeFixture 'target';New-Item -ItemType Directory -Path $unicodeSourceDir,$payloadDir,$targetDir -Force|Out-Null
        $unicodeSource=Join-Path $unicodeSourceDir 'i18n.jar';$payloadSource=Join-Path $payloadDir '00_i18n.jar';$target=Join-Path $targetDir 'i18n.jar';[IO.File]::WriteAllText($unicodeSource,'unicode-path-payload',(New-Object Text.UTF8Encoding($false)));Copy-Item -LiteralPath $unicodeSource -Destination $payloadSource -Force
        # Canlı üretim klasörü kurulumdan önce kaybolsa/değişse bile işlem,
        # doğrulanmış geçici kopyadan tamamlanmalıdır.
        [IO.File]::Delete($unicodeSource);$safeSource=$payloadSource.Replace("'","''");$safeTarget=$target.Replace("'","''");$copyScript=Join-Path $unicodeFixture 'transaction\unicode_kur.ps1'
        $copyText="`$ErrorActionPreference='Stop'`r`nCopy-Item -LiteralPath '$safeSource' -Destination '$safeTarget' -Force`r`n"
        [IO.File]::WriteAllText($copyScript,$copyText,(New-Object Text.UTF8Encoding($true)));$bytes=[IO.File]::ReadAllBytes($copyScript);if($bytes.Length-lt3-or$bytes[0]-ne0xEF-or$bytes[1]-ne0xBB-or$bytes[2]-ne0xBF){throw 'Unicode kurulum komut dosyasının UTF-8 BOM işareti eksik.'}
        $process=Start-Process powershell.exe -WindowStyle Hidden -Wait -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$copyScript);if($process.ExitCode-ne0-or-not(Test-Path -LiteralPath $target)-or(Get-Content -LiteralPath $target -Raw -Encoding UTF8)-ne'unicode-path-payload'){throw 'Türkçe/Unicode klasör yolundan geçici kaynak kurulum sınaması başarısız.'}
    }finally{Remove-Item -LiteralPath $unicodeFixture -Recurse -Force -ErrorAction SilentlyContinue}

    $launcherFixture=Join-Path $env:TEMP ('WakfuLauncherTest_'+[Guid]::NewGuid().ToString('N'));$oldToolRoot=$env:WAKFU_TOOL_STATE_ROOT;$env:WAKFU_TOOL_STATE_ROOT=$launcherFixture
    try{
        $launcherType=$programAssembly.GetType('WakfuAracLauncher',$true);$extract=$launcherType.GetMethod('ExtractEmbeddedApplication',[Reflection.BindingFlags]'Static,NonPublic');if($null-eq$extract){throw 'Ana program çıkarma işlevi test için bulunamadı.'}
        $app=Join-Path $launcherFixture 'App';$extract.Invoke($null,[object[]]@([string]$app))|Out-Null
        if(-not(Test-Path -LiteralPath (Join-Path $app 'Kaynak_Kodu\WakfuTurkceCeviri.ps1'))){throw 'Temiz bilgisayar ana program çıkarma sınaması başarısız.'}
        $settings=Join-Path $app 'Ayarlar\arayuz_ayarlari.json';$userTranslation=Join-Path $app 'Ceviri_Verileri\wakfu_tr_ceviri.json';$installedManifest=Join-Path $app 'Ayarlar\dagitim_manifest.json'
        $expectedUiSettings='{"test_setting":"preserve","OverheadTextScaleProfile":"small"}'
        [IO.File]::WriteAllText($settings,$expectedUiSettings,(New-Object Text.UTF8Encoding($false)));[IO.File]::WriteAllText($userTranslation,'{"USER_TEST":"keep-backup"}',(New-Object Text.UTF8Encoding($false)))
        $oldManifest=Get-Content -LiteralPath $installedManifest -Raw -Encoding UTF8|ConvertFrom-Json;$oldManifest.version='onceki-surum';[IO.File]::WriteAllText($installedManifest,($oldManifest|ConvertTo-Json -Depth 5 -Compress),(New-Object Text.UTF8Encoding($false)))
        $extract.Invoke($null,[object[]]@([string]$app))|Out-Null
        if((Get-Content -LiteralPath $settings -Raw -Encoding UTF8)-ne$expectedUiSettings){throw 'Ana program yükseltmesi seçilen baş üstü yazı profilini korumadı.'}
        if((Get-Content -LiteralPath $userTranslation -Raw -Encoding UTF8)-eq'{"USER_TEST":"keep-backup"}'){throw 'Ana program yükseltmesi güncel çeviri çekirdeğini yüklemedi.'}
        $backedUp=@(Get-ChildItem -LiteralPath (Join-Path $launcherFixture 'Kullanici_Yedekleri') -Filter 'wakfu_tr_ceviri.json' -File -Recurse -ErrorAction SilentlyContinue|Where-Object{(Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8)-eq'{"USER_TEST":"keep-backup"}'})
        if($backedUp.Count-ne1){throw 'Ana program yükseltmesi kullanıcı çevirisini güvenli yedeğe almadı.'}
        $coreScript=Join-Path $app 'Kaynak_Kodu\WakfuTurkceCeviri.ps1';if(-not(Test-ProgramOverheadScaleContract $coreScript)){throw 'Ana programın seçilebilir baş üstü yazı profilleri eksik veya hatalı.'};[IO.File]::AppendAllText($coreScript,"`r`n# CORRUPTION_TEST",[Text.Encoding]::UTF8);[IO.File]::WriteAllText($userTranslation,'{"USER_TEST":"same-version-preserve"}',(New-Object Text.UTF8Encoding($false)))
        $extract.Invoke($null,[object[]]@([string]$app))|Out-Null
        if((Get-Content -LiteralPath $coreScript -Raw -Encoding UTF8)-match'CORRUPTION_TEST'){throw 'Ana program aynı sürümde bozuk çekirdeği onarmadı.'}
        if((Get-Content -LiteralPath $userTranslation -Raw -Encoding UTF8)-ne'{"USER_TEST":"same-version-preserve"}'){throw 'Ana program aynı sürüm onarımında kullanıcı çevirisini korumadı.'}
        if((Get-Content -LiteralPath $settings -Raw -Encoding UTF8)-ne$expectedUiSettings){throw 'Ana program aynı sürüm onarımında baş üstü yazı profilini korumadı.'}
    }finally{$env:WAKFU_TOOL_STATE_ROOT=$oldToolRoot;Remove-Item -LiteralPath $launcherFixture -Recurse -Force -ErrorAction SilentlyContinue}

    $sourceDir=Split-Path -Parent $MyInvocation.MyCommand.Path;$projectRoot=Split-Path -Parent $sourceDir
    $fixture=Join-Path $env:TEMP ('WakfuDagitimTest_'+[Guid]::NewGuid().ToString('N'))
    $oldStateRoot=$env:WAKFU_PATCH_STATE_ROOT;$env:WAKFU_PATCH_STATE_ROOT=Join-Path $fixture 'state'
    try{
        foreach($dir in @('game\contents\i18n','game\contents\gui_jar','game\contents\data','game\lib')){New-Item -ItemType Directory -Path (Join-Path $fixture $dir) -Force|Out-Null}
        $game=Join-Path $fixture 'game';$current=Join-Path $projectRoot 'Oyun_Kaynaklari\Guncel'
        foreach($copy in @(
            @((Join-Path $current 'i18n_en.jar'),(Join-Path $game 'contents\i18n\i18n_en.jar')),
            @((Join-Path $current 'gui.jar'),(Join-Path $game 'contents\gui_jar\gui.jar')),
            @((Join-Path $current 'wakfu-client.jar'),(Join-Path $game 'lib\wakfu-client.jar')),
            @((Join-Path $current 'data.jar'),(Join-Path $game 'contents\data\data.jar'))
        )){if(-not(Test-Path -LiteralPath $copy[0])){throw "Temiz test kaynağı eksik: $($copy[0])"};Copy-Item -LiteralPath $copy[0] -Destination $copy[1] -Force}
        if(Test-Path -LiteralPath (Join-Path $game 'contents\i18n\i18n.jar')){throw 'Temiz Steam kurulum sınaması etkin i18n.jar olmadan başlamadı.'}
        $setupEntryPoint=$setupAssembly.EntryPoint;if($null-eq$setupEntryPoint-or$setupEntryPoint.GetParameters().Count-ne1-or$setupEntryPoint.GetParameters()[0].ParameterType-ne[string[]]){throw 'Setup gizli kurulum komut satırı arayüzü bulunamadı.'}
        $setupType=$setupAssembly.GetType('WakfuSetupApp',$true)
        $install=$setupType.GetMethod('Install',[Reflection.BindingFlags]'Static,NonPublic')
        if($null-eq$install-or$install.GetParameters().Count-ne2){throw 'Setup seçilebilir profil kurulum işlevi test için bulunamadı.'}
        function Invoke-TestInstall([string]$profile){
            try{$install.Invoke($null,[object[]]@([string]$game,[string]$profile))|Out-Null}
            catch{if($_.Exception.InnerException){throw ([Exception]$_.Exception.InnerException)}else{throw}}
        }
        function Get-GameHashes{[ordered]@{i18n_en=(Get-FileHash (Join-Path $game 'contents\i18n\i18n_en.jar') -Algorithm SHA256).Hash;i18n=(Get-FileHash (Join-Path $game 'contents\i18n\i18n.jar') -Algorithm SHA256).Hash;gui=(Get-FileHash (Join-Path $game 'contents\gui_jar\gui.jar') -Algorithm SHA256).Hash;client=(Get-FileHash (Join-Path $game 'lib\wakfu-client.jar') -Algorithm SHA256).Hash;data=(Get-FileHash (Join-Path $game 'contents\data\data.jar') -Algorithm SHA256).Hash}}
        function Assert-TestProfile([ValidateSet('normal','small','tiny')][string]$profile){
            $clientJar=Join-Path $game 'lib\wakfu-client.jar';$dataJar=Join-Path $game 'contents\data\data.jar'
            if(-not(Test-SafeNameOverheadJar $clientJar)){throw "V sınıfı güvenli biçimde üretilmedi: profil=$profile"}
            if(-not(Test-HoverCompatibleNameToggleJar $clientJar)){throw "V açıkken fare üstü ad uyumluluğu üretilmedi: profil=$profile"}
            if(-not(Test-OverheadTextScaleJar $clientJar $profile)){throw "Baş üstü yazı profili doğru üretilmedi: profil=$profile"}
            if(-not(Test-PressOnlyNameShortcutJar $dataJar)){throw "V tuşu basış başına tek aç/kapat biçiminde üretilmedi: profil=$profile"}
            $stateFile=Join-Path $env:WAKFU_PATCH_STATE_ROOT 'kurulum_durumu.json';if(-not(Test-Path -LiteralPath $stateFile)){throw "Kurulum profil durumu yazılmadı: profil=$profile"}
            $state=Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8|ConvertFrom-Json;if([string]$state.overheadScaleProfile-ne$profile){throw "Kurulum profil durumu uyuşmuyor: beklenen=$profile, bulunan=$($state.overheadScaleProfile)"}
        }
        $profileHashes=[ordered]@{}
        foreach($profile in @('small','normal','tiny')){
            Invoke-TestInstall $profile;Assert-TestProfile $profile;$firstProfileInstall=Get-GameHashes
            Invoke-TestInstall $profile;Assert-TestProfile $profile;$secondProfileInstall=Get-GameHashes
            foreach($key in $firstProfileInstall.Keys){if($firstProfileInstall[$key]-ne$secondProfileInstall[$key]){throw "Profil tekrar kurulumu kararlı değil: profil=$profile, dosya=$key"}}
            $profileHashes[$profile]=$firstProfileInstall
        }
        if($profileHashes.small.client-eq$profileHashes.normal.client-or$profileHashes.small.client-eq$profileHashes.tiny.client-or$profileHashes.normal.client-eq$profileHashes.tiny.client){throw 'Baş üstü yazı profilleri farklı istemci paketleri üretmedi.'}
        Invoke-TestInstall 'small';Assert-TestProfile 'small';$first=Get-GameHashes
        $beforeInvalid=Get-GameHashes;$invalidRejected=$false;try{Invoke-TestInstall 'invalid-profile'}catch{$invalidRejected=$true};if(-not$invalidRejected){throw 'Geçersiz baş üstü yazı profili güvenli biçimde reddedilmedi.'};$afterInvalid=Get-GameHashes
        foreach($key in $beforeInvalid.Keys){if($beforeInvalid[$key]-ne$afterInvalid[$key]){throw "Geçersiz profil canlı dosyayı değiştirdi: $key"}}
        $updateJar=Join-Path $game 'contents\i18n\i18n_en.jar';Copy-Item -LiteralPath (Join-Path $current 'i18n_en.jar') -Destination $updateJar -Force
        $zipUpdate=[IO.Compression.ZipFile]::Open($updateJar,[IO.Compression.ZipArchiveMode]::Update);try{$entry=$zipUpdate.CreateEntry('codex_update_probe.txt');$writer=New-Object IO.StreamWriter($entry.Open(),(New-Object Text.UTF8Encoding($false)));try{$writer.Write('update-probe')}finally{$writer.Dispose()}}finally{$zipUpdate.Dispose()}
        Copy-Item -LiteralPath $updateJar -Destination (Join-Path $game 'contents\i18n\i18n.jar') -Force;Invoke-TestInstall 'small';Assert-TestProfile 'small'
        $afterUpdate=Get-GameHashes
        if($afterUpdate.i18n_en-eq$first.i18n_en){throw 'Oyun güncellemesi uyarlama sınaması yeni kaynak üretmedi.'}
        Invoke-TestInstall 'small';Assert-TestProfile 'small';$afterUpdateRepeat=Get-GameHashes
        foreach($key in $afterUpdate.Keys){if($afterUpdate[$key]-ne$afterUpdateRepeat[$key]){throw "Güncelleme sonrası tekrar kurulum kararlı değil: $key"}}
        $client=Join-Path $game 'lib\wakfu-client.jar';$broken=[IO.Compression.ZipFile]::Open($client,[IO.Compression.ZipArchiveMode]::Update);try{$entry=$broken.GetEntry('dde.class');if($null-eq$entry){throw 'Rollback sınaması için dde.class bulunamadı.'};$entry.Delete()}finally{$broken.Dispose()}
        $beforeFailure=Get-GameHashes;$failed=$false;try{Invoke-TestInstall 'small'}catch{$failed=$true};if(-not$failed){throw 'Uyumsuz oyun sürümü güvenli biçimde reddedilmedi.'};$afterFailure=Get-GameHashes
        foreach($key in $beforeFailure.Keys){if($beforeFailure[$key]-ne$afterFailure[$key]){throw "Başarısız kurulum canlı dosyayı değiştirdi: $key"}}
    }finally{
        $env:WAKFU_PATCH_STATE_ROOT=$oldStateRoot
        Remove-Item -LiteralPath $fixture -Recurse -Force -ErrorAction SilentlyContinue
    }
}

"OK|$($setupManifest.version)|SETUP=$((Get-FileHash -LiteralPath $SetupExe -Algorithm SHA256).Hash)|PROGRAM=$((Get-FileHash -LiteralPath $ProgramExe -Algorithm SHA256).Hash)|SIMULATION=$([bool]$FullInstallSimulation)"
