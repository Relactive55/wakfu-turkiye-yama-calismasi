param([string[]]$Keys=@())
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Web.Extensions
Add-Type -AssemblyName System.IO.Compression.FileSystem
$sourceDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot=if((Split-Path -Leaf $sourceDir)-eq'Kaynak_Kodu'){Split-Path -Parent $sourceDir}else{$sourceDir}
$manualPath=Join-Path $projectRoot 'Ceviri_Verileri\manual_repairs_v23.json'
$sourceJar=Join-Path $projectRoot 'Oyun_Kaynaklari\Guncel\i18n_en.jar'
if($Keys.Count-eq0){
    $Keys=@(
        'aptitudes.pointsToNextLevel','booster.pack','defeat','breedLongDesc.1','breedLongDesc.2','breedLongDesc.3','breedLongDesc.4','breedLongDesc.5','breedLongDesc.6','breedLongDesc.7','breedLongDesc.8','breedLongDesc.9','breedLongDesc.10','breedLongDesc.11','breedLongDesc.12','breedLongDesc.13','breedLongDesc.14','breedLongDesc.15','breedLongDesc.16','breedLongDesc.17','breedLongDesc.18','breedLongDesc.19','build.remove.item.from.all.success','enchantment.validate.changes.gain',
        'nation.vote.eligible.warning','quest.wabbit.lenald.liz.14','spell.cast.maxPerTurn','content.10.337',
        'content.10.986','content.10.989','content.10.1071','content.13.318129','content.14.297',
        'content.15.11955','content.15.15865','content.15.19799','content.15.31167',
        'content.54.830','content.54.1415','content.54.1697','content.61.256',
        'content.66.50501','content.66.67401','content.66.80901','content.66.95801',
        'content.30.986','content.30.989','content.30.1071','content.33.86969','content.33.163138',
        'content.33.187207','content.33.188970','content.33.308222','content.33.318669','content.33.358720',
        'content.75.3481','content.75.3892','content.75.3924','content.75.3939','content.75.3960',
        'content.75.4303','content.76.9891','content.76.9936','content.4.4805','content.13.149678','content.33.149678',
        'content.16.19748','critere.isBattleground','critere.not.isBattleground','critere.isInRanch','critere.not.isInRanch','critere.notGetInstanceId',
        'critere.isInNationJail','critere.not.isInNationJail'
    )
}

function Get-FormatTokens([string]$text) {
    if([string]::IsNullOrEmpty($text)){return @()}
    $atoms=@([regex]::Matches($text,'\{\[[^\]]+\]\?(?:s|es)?:\}|\\[ntr]|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|<[^>]*>|%[A-Za-z_][A-Za-z0-9_.-]*%'))
    $byStart=@{};foreach($atom in $atoms){$byStart[$atom.Index]=$atom}
    $result=New-Object Collections.Generic.List[string];$depth=0;$i=0
    while($i-lt$text.Length){
        if($byStart.ContainsKey($i)){$atom=$byStart[$i];$result.Add($atom.Value);$i+=$atom.Length;continue}
        $char=$text[$i]
        if($char-eq'{'){$result.Add('{');$depth++}
        elseif($char-eq'}'){$result.Add('}');if($depth-gt0){$depth--}}
        elseif($depth-gt0-and($char-eq'?' -or $char-eq':')){$result.Add([string]$char)}
        $i++
    }
    return @($result)
}

function Test-FormatTokens([string]$source,[string]$translated) {
    $a=@(Get-FormatTokens $source);$b=@(Get-FormatTokens $translated)
    $exact=$a.Count-eq$b.Count
    if($exact){for($i=0;$i-lt$a.Count;$i++){if($a[$i]-cne$b[$i]){$exact=$false;break}}}
    if($exact){return $true}
    $headerPattern='\{\[[^\]]+\]\?'
    $ordinaryPattern='\\[ntr]|<[^>]*>|%[A-Za-z_][A-Za-z0-9_.-]*%|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]'
    $headersA=@([regex]::Matches($source,$headerPattern)|ForEach-Object{$_.Value})
    $headersB=@([regex]::Matches($translated,$headerPattern)|ForEach-Object{$_.Value})
    if($headersA.Count-ne$headersB.Count){return $false}
    for($i=0;$i-lt$headersA.Count;$i++){if($headersA[$i]-cne$headersB[$i]){return $false}}
    $plainA=[regex]::Replace($source,$headerPattern,'');$plainB=[regex]::Replace($translated,$headerPattern,'')
    $ordinaryA=@([regex]::Matches($plainA,$ordinaryPattern)|ForEach-Object{$_.Value})
    $ordinaryB=@([regex]::Matches($plainB,$ordinaryPattern)|ForEach-Object{$_.Value})
    if($ordinaryA.Count-ne$ordinaryB.Count){return $false}
    for($i=0;$i-lt$ordinaryA.Count;$i++){if($ordinaryA[$i]-cne$ordinaryB[$i]){return $false}}
    foreach($marker in @('{','}',':}')){
        if([regex]::Matches($source,[regex]::Escape($marker)).Count-ne[regex]::Matches($translated,[regex]::Escape($marker)).Count){return $false}
    }
    return $true
}

$serializer=New-Object Web.Script.Serialization.JavaScriptSerializer
$serializer.MaxJsonLength=[int]::MaxValue
$manual=$serializer.DeserializeObject([IO.File]::ReadAllText($manualPath,[Text.Encoding]::UTF8))
$wanted=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
foreach($key in $Keys){[void]$wanted.Add($key)}
$sources=@{}
$zip=[IO.Compression.ZipFile]::OpenRead($sourceJar)
try{
    $entry=$zip.GetEntry('texts_en.properties')
    $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
    try{
        while(($line=$reader.ReadLine())-ne$null){
            $pos=$line.IndexOf('=');if($pos-lt1){continue}
            $key=$line.Substring(0,$pos);if($wanted.Contains($key)){$sources[$key]=$line.Substring($pos+1)}
        }
    }finally{$reader.Dispose()}
}finally{$zip.Dispose()}
$bad=New-Object Collections.Generic.List[string]
foreach($key in $Keys){
    if(-not$sources.ContainsKey($key)-or-not$manual.ContainsKey($key)-or-not(Test-FormatTokens ([string]$sources[$key]) ([string]$manual[$key]))){$bad.Add($key)}
}
"FORMAT_TESTED=$($Keys.Count)|BAD=$($bad.Count)"
$bad
if($bad.Count-gt0){exit 1}
