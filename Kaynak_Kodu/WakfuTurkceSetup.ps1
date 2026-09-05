$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Test-Administrator {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if(-not(Test-Administrator)){
    try {
        $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'))
        $process=Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList (@('-WindowStyle','Hidden')+$arguments)
        exit $process.ExitCode
    } catch {
        [Windows.Forms.MessageBox]::Show('Kurulum için yönetici izni verilmedi.','Wakfu Türkçe Yama','OK','Warning')|Out-Null
        exit 1
    }
}

$PayloadDir=Split-Path -Parent $PSCommandPath
$ProjectRoot=if((Split-Path -Leaf $PayloadDir)-eq'Kaynak_Kodu'){Split-Path -Parent $PayloadDir}else{$PayloadDir}
$PayloadI18n=Join-Path $ProjectRoot 'Uretilenler\i18n.jar'
$PayloadFontDir=Join-Path $ProjectRoot 'Oyun_Kaynaklari\Fontlar'
$FontNames=@('asul.ttf','asulb.ttf','bagnard.ttf','coprgtb.ttf','coprgtl.ttf','londrina.ttf','lucidacally.ttf')
$BackupDir=Join-Path $ProjectRoot 'Oyun_Kaynaklari\Kurulum_Yedegi'

function Test-WakfuFolder([string]$path){return (Test-Path -LiteralPath (Join-Path $path 'contents\i18n\i18n_en.jar'))}
function Find-WakfuFromSteam([string]$steam){
    if(Test-WakfuFolder $steam){return $steam}
    $direct=Join-Path $steam 'steamapps\common\Wakfu';if(Test-WakfuFolder $direct){return $direct}
    $vdf=Join-Path $steam 'steamapps\libraryfolders.vdf'
    if(Test-Path -LiteralPath $vdf){$text=Get-Content -LiteralPath $vdf -Raw;foreach($m in [regex]::Matches($text,'"path"\s+"([^"]+)"')){$library=$m.Groups[1].Value.Replace('\\','\');$candidate=Join-Path $library 'steamapps\common\Wakfu';if(Test-WakfuFolder $candidate){return $candidate}}}
    return ''
}
function Find-WakfuFolder {
    $candidates=New-Object Collections.Generic.List[string]
    foreach($path in @('C:\Program Files (x86)\Steam\steamapps\common\Wakfu','C:\Program Files\Steam\steamapps\common\Wakfu')){if(-not$candidates.Contains($path)){$candidates.Add($path)}}
    foreach($reg in @('HKCU:\Software\Valve\Steam','HKLM:\SOFTWARE\WOW6432Node\Valve\Steam','HKLM:\SOFTWARE\Valve\Steam')){
        try{$steam=(Get-ItemProperty -LiteralPath $reg -ErrorAction Stop).SteamPath;if(-not$steam){$steam=(Get-ItemProperty -LiteralPath $reg -ErrorAction Stop).InstallPath};if($steam){$candidates.Add((Join-Path $steam 'steamapps\common\Wakfu'));$vdf=Join-Path $steam 'steamapps\libraryfolders.vdf';if(Test-Path -LiteralPath $vdf){$text=Get-Content -LiteralPath $vdf -Raw;foreach($m in [regex]::Matches($text,'"path"\s+"([^"]+)"')){$library=$m.Groups[1].Value.Replace('\\','\');$candidates.Add((Join-Path $library 'steamapps\common\Wakfu'))}}}}catch{}
    }
    foreach($candidate in $candidates){if(Test-WakfuFolder $candidate){return $candidate}}
    return ''
}

function Ensure-NameToggleShortcut([string]$dataJar){
    if(-not(Test-Path -LiteralPath $dataJar)){throw 'data.jar bulunamadı.'}
    $zip=[IO.Compression.ZipFile]::Open($dataJar,[IO.Compression.ZipArchiveMode]::Update)
    try{
        $entry=$zip.GetEntry('shortcuts.xml');if(-not$entry){throw 'shortcuts.xml bulunamadı.'}
        $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
        try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
        $pattern='(?s)(<shortcut\b(?=[^>]*\bid="showHideNameOverheadsCommand")[^>]*\bonKeyReleased\s*=\s*")false(")'
        $alreadyPattern='(?s)<shortcut\b(?=[^>]*\bid="showHideNameOverheadsCommand")[^>]*\bonKeyReleased\s*=\s*"true"'
        $matches=[regex]::Matches($text,$pattern,[Text.RegularExpressions.RegexOptions]::CultureInvariant)
        if($matches.Count-gt1){throw 'V oyuncu adı kısayolu birden çok kez bulundu; güvenli geri yükleme yapılmadı.'}
        if($matches.Count-eq1){$restored=[regex]::Replace($text,$pattern,'${1}true${2}',[Text.RegularExpressions.RegexOptions]::CultureInvariant)}
        elseif([regex]::IsMatch($text,$alreadyPattern,[Text.RegularExpressions.RegexOptions]::CultureInvariant)){$restored=$text}
        else{throw 'V oyuncu adı kısayolunun özgün bırakma davranışı bulunamadı.'}
        if($restored-ne$text){$entry.Delete();$replacement=$zip.CreateEntry('shortcuts.xml',[IO.Compression.CompressionLevel]::Optimal);$writer=New-Object IO.StreamWriter($replacement.Open(),(New-Object Text.UTF8Encoding($false)));try{$writer.Write($restored)}finally{$writer.Dispose()}}
    }finally{$zip.Dispose()}
}

function Install-Patch([string]$gameDir){
    if(-not(Test-WakfuFolder $gameDir)){throw 'Geçerli Wakfu klasörü seçilmedi.'}
    if(-not(Test-Path -LiteralPath $PayloadI18n)){throw 'Kurulum paketindeki i18n.jar bulunamadı.'}
    $running=Get-Process -Name Wakfu,java,javaw,Ankama*,zaap* -ErrorAction SilentlyContinue
    if($running){throw 'Kurulumdan önce Wakfu ve Ankama Launcher tamamen kapatılmalıdır.'}
    New-Item -ItemType Directory -Path $BackupDir -Force|Out-Null
    $i18nDir=Join-Path $gameDir 'contents\i18n';$guiDest=Join-Path $gameDir 'contents\gui_jar\gui.jar';$dataDest=Join-Path $gameDir 'contents\data\data.jar'
    foreach($name in @('i18n_en.jar','i18n.jar')){$src=Join-Path $i18nDir $name;$bak=Join-Path $BackupDir $name;if((Test-Path -LiteralPath $src)-and-not(Test-Path -LiteralPath $bak)){Copy-Item -LiteralPath $src -Destination $bak}}
    $guiBackup=Join-Path $BackupDir 'gui.jar';if((Test-Path -LiteralPath $guiDest)-and-not(Test-Path -LiteralPath $guiBackup)){Copy-Item -LiteralPath $guiDest -Destination $guiBackup}
    $dataBackup=Join-Path $BackupDir 'data.jar';if((Test-Path -LiteralPath $dataDest)-and-not(Test-Path -LiteralPath $dataBackup)){Copy-Item -LiteralPath $dataDest -Destination $dataBackup}
    Copy-Item -LiteralPath $PayloadI18n -Destination (Join-Path $i18nDir 'i18n_en.jar') -Force
    Copy-Item -LiteralPath $PayloadI18n -Destination (Join-Path $i18nDir 'i18n.jar') -Force
    if(Test-Path -LiteralPath $guiDest){
        $zip=[IO.Compression.ZipFile]::Open($guiDest,[IO.Compression.ZipArchiveMode]::Update)
        try{foreach($fontName in $FontNames){$fontPath=Join-Path $PayloadFontDir $fontName;if(-not(Test-Path -LiteralPath $fontPath)){continue};$entryName='theme/fonts/'+$fontName;$old=$zip.GetEntry($entryName);if(-not$old){continue};$old.Delete();$new=$zip.CreateEntry($entryName,[IO.Compression.CompressionLevel]::Optimal);$input=[IO.File]::OpenRead($fontPath);$output=$new.Open();try{$input.CopyTo($output)}finally{$output.Dispose();$input.Dispose()}}}finally{$zip.Dispose()}
    }
    Ensure-NameToggleShortcut $dataDest
    $expected=(Get-FileHash -LiteralPath $PayloadI18n -Algorithm SHA256).Hash
    if((Get-FileHash -LiteralPath (Join-Path $i18nDir 'i18n_en.jar') -Algorithm SHA256).Hash-ne$expected){throw 'Kurulum doğrulaması başarısız oldu.'}
}

function Restore-Original([string]$gameDir){
    if(-not(Test-WakfuFolder $gameDir)){throw 'Geçerli Wakfu klasörü seçilmedi.'}
    if(-not(Test-Path -LiteralPath (Join-Path $BackupDir 'i18n_en.jar'))){throw 'Bu bilgisayarda geri yüklenecek yedek bulunamadı.'}
    $running=Get-Process -Name Wakfu,java,javaw,Ankama*,zaap* -ErrorAction SilentlyContinue
    if($running){throw 'Geri yüklemeden önce Wakfu ve Ankama Launcher tamamen kapatılmalıdır.'}
    $i18nDir=Join-Path $gameDir 'contents\i18n'
    foreach($name in @('i18n_en.jar','i18n.jar')){$bak=Join-Path $BackupDir $name;if(Test-Path -LiteralPath $bak){Copy-Item -LiteralPath $bak -Destination (Join-Path $i18nDir $name) -Force}}
    $guiBackup=Join-Path $BackupDir 'gui.jar';if(Test-Path -LiteralPath $guiBackup){Copy-Item -LiteralPath $guiBackup -Destination (Join-Path $gameDir 'contents\gui_jar\gui.jar') -Force}
    $dataBackup=Join-Path $BackupDir 'data.jar';if(Test-Path -LiteralPath $dataBackup){Copy-Item -LiteralPath $dataBackup -Destination (Join-Path $gameDir 'contents\data\data.jar') -Force}
}

$form=New-Object Windows.Forms.Form;$form.Text='Wakfu Türkçe Yama Kurulumu';$form.Size=New-Object Drawing.Size(790,285);$form.StartPosition='CenterScreen';$form.FormBorderStyle='FixedDialog';$form.MaximizeBox=$false;$form.Font=New-Object Drawing.Font('Segoe UI',10)
$title=New-Object Windows.Forms.Label;$title.Text='Wakfu Türkçe Yama';$title.Font=New-Object Drawing.Font('Segoe UI',17,[Drawing.FontStyle]::Bold);$title.SetBounds(20,18,600,38)
$label=New-Object Windows.Forms.Label;$label.Text='Wakfu klasörü:';$label.SetBounds(20,70,120,25)
$pathBox=New-Object Windows.Forms.TextBox;$pathBox.SetBounds(20,98,420,28);$pathBox.Text=Find-WakfuFolder
$browseSteam=New-Object Windows.Forms.Button;$browseSteam.Text='Steam Klasörü Seç';$browseSteam.SetBounds(450,95,145,33)
$browseWakfu=New-Object Windows.Forms.Button;$browseWakfu.Text='Wakfu Klasörü Seç';$browseWakfu.SetBounds(605,95,150,33)
$install=New-Object Windows.Forms.Button;$install.Text='Türkçe Yamayı Yükle';$install.SetBounds(155,155,210,45);$install.BackColor=[Drawing.Color]::PaleGreen
$restore=New-Object Windows.Forms.Button;$restore.Text='Orijinali Geri Yükle';$restore.SetBounds(410,155,210,45)
$status=New-Object Windows.Forms.Label;$status.Text='Oyun ve launcher kapalı olmalıdır.';$status.SetBounds(20,215,730,25)
$browseSteam.Add_Click({$dialog=New-Object Windows.Forms.FolderBrowserDialog;$dialog.Description='Steam ana klasörünü seçin';if($dialog.ShowDialog()-eq'OK'){$found=Find-WakfuFromSteam $dialog.SelectedPath;if($found){$pathBox.Text=$found}else{[Windows.Forms.MessageBox]::Show('Seçilen Steam klasöründe veya bağlı kütüphanelerde Wakfu bulunamadı.','Wakfu bulunamadı','OK','Warning')|Out-Null}}})
$browseWakfu.Add_Click({$dialog=New-Object Windows.Forms.FolderBrowserDialog;$dialog.Description='Doğrudan Wakfu oyun klasörünü seçin';if($dialog.ShowDialog()-eq'OK'){$pathBox.Text=$dialog.SelectedPath}})
$install.Add_Click({try{Install-Patch $pathBox.Text;$status.Text='Türkçe yama kuruldu ve doğrulandı.';[Windows.Forms.MessageBox]::Show('Türkçe yama başarıyla kuruldu. Oyunu açabilirsiniz.','Kurulum tamam','OK','Information')|Out-Null}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Kurulum hatası','OK','Error')|Out-Null}})
$restore.Add_Click({try{Restore-Original $pathBox.Text;$status.Text='Orijinal dosyalar geri yüklendi.';[Windows.Forms.MessageBox]::Show('Orijinal oyun dosyaları geri yüklendi.','Geri yükleme tamam','OK','Information')|Out-Null}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Geri yükleme hatası','OK','Error')|Out-Null}})
$form.Controls.AddRange(@($title,$label,$pathBox,$browseSteam,$browseWakfu,$install,$restore,$status));[void]$form.ShowDialog()
