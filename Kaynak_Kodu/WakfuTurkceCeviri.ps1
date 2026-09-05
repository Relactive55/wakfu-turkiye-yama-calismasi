param(
    [switch]$AuditOnly,
    [switch]$BuildOnly,
    [switch]$InstallOnly,
    [switch]$NonInteractive,
    [switch]$UiSmokeTest,
    [string]$AuditOutput,
    [string]$SmokeOutput,
    [int]$AuditLimit=0
)

$ErrorActionPreference = 'Stop'
$script:NonInteractiveMode=[bool]$NonInteractive
$script:ProgramStopwatch=[Diagnostics.Stopwatch]::StartNew()
if($AuditOutput -and (Test-Path -LiteralPath $AuditOutput)){$env:WAKFU_EXE_DIR=[IO.Path]::GetFullPath($AuditOutput)}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Web.Extensions
if(-not('WakfuFastSearch' -as[type])){
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
public static class WakfuFastSearch {
    static readonly Regex ProtectedKey = new Regex(
        @"^content\.(3|7|8|12|15|20|38|48|54|77|78|82|89|130|159)\.|^content\.6\.1049$|^breed\.\d+$|\.boussole\.|^boussole\.|^worldName\.|^desc\.mru\.activate\.[^.]+\.[^.]+$|^(item|monster|mob|npc|spell|skill|pet|mount)\..*\.name$",
        RegexOptions.IgnoreCase|RegexOptions.CultureInvariant|RegexOptions.Compiled);
    public static string[] ProtectedNames(string[] keys,string[] english) {
        var names=new HashSet<string>(StringComparer.Ordinal);
        var translatedStates=new HashSet<string>(StringComparer.Ordinal){
            "content.8.1263","content.8.2718","content.8.4048","content.8.4260",
            "content.8.5817","content.8.5865","content.8.7386",
            "content.8.748","content.8.5355","content.8.1915","content.8.1916",
            "content.15.2175","content.15.11955","content.15.15865","content.15.19799",
            "content.15.24267","content.15.27097","content.15.27098","content.15.27099",
            "content.15.27110","content.15.29612","content.15.31167"};
        for(int i=0;i<keys.Length;i++) if(keys[i]!="content.15.0" && !translatedStates.Contains(keys[i]) && ProtectedKey.IsMatch(keys[i]??"") && !String.IsNullOrWhiteSpace(english[i])) names.Add(english[i].Trim());
        names.Add("Canoon");names.Add("Moon-Canoon");
        var result=new string[names.Count];names.CopyTo(result);return result;
    }
    public static string[] BuildTurkish(string[] keys, string[] english,
        IDictionary<string,string> translations, IDictionary<string,string> termKeys,
        IDictionary<string,string> termValues) {
        var result=new string[keys.Length];
        for(int i=0;i<keys.Length;i++) {
            string value;
            if(termKeys.TryGetValue(keys[i],out value)) result[i]=value ?? "";
            else if(termValues.TryGetValue(english[i],out value)) result[i]=value ?? "";
            else if(translations.TryGetValue(keys[i],out value)) result[i]=value ?? "";
            else result[i]="";
        }
        return result;
    }
    public static int[] Find(string[] keys,string[] english,string[] turkish,string[] words,int limit) {
        var found=new List<int>(Math.Min(limit,1024));
        for(int i=0;i<keys.Length && found.Count<limit;i++) {
            bool ok=true;
            foreach(string word in words) {
                if((keys[i]??"").IndexOf(word,StringComparison.CurrentCultureIgnoreCase)<0 &&
                   (english[i]??"").IndexOf(word,StringComparison.CurrentCultureIgnoreCase)<0 &&
                   (turkish[i]??"").IndexOf(word,StringComparison.CurrentCultureIgnoreCase)<0) {ok=false;break;}
            }
            if(ok) found.Add(i);
        }
        return found.ToArray();
    }
    public static int[] FindExactTurkish(string[] turkish,string value,int limit) {
        var found=new List<int>();
        for(int i=0;i<turkish.Length && found.Count<limit;i++)
            if(String.Equals((turkish[i]??"").Trim(),value,StringComparison.CurrentCultureIgnoreCase)) found.Add(i);
        return found.ToArray();
    }
    public static void Update(string[] keys,string[] turkish,string key,string value) {
        for(int i=0;i<keys.Length;i++) if(String.Equals(keys[i],key,StringComparison.Ordinal)){turkish[i]=value??"";return;}
    }
    static int U2(byte[] data,int offset) { return (data[offset]<<8)|data[offset+1]; }
    static void PutU2(Stream stream,int value) { stream.WriteByte((byte)(value>>8));stream.WriteByte((byte)value); }
    static void PutUtf8(Stream stream,string value) {
        byte[] bytes=Encoding.UTF8.GetBytes(value);stream.WriteByte(1);PutU2(stream,bytes.Length);stream.Write(bytes,0,bytes.Length);
    }
    static int ConstantPoolEnd(byte[] data,out int count) {
        if(data.Length<10||data[0]!=0xCA||data[1]!=0xFE||data[2]!=0xBA||data[3]!=0xBE)throw new InvalidDataException("Geçersiz Java sınıfı.");
        count=U2(data,8);int p=10;
        for(int i=1;i<count;i++){
            int tag=data[p++];
            switch(tag){
                case 1:int length=U2(data,p);p+=2+length;break;
                case 3:case 4:p+=4;break;
                case 5:case 6:p+=8;i++;break;
                case 7:case 8:case 16:case 19:case 20:p+=2;break;
                case 9:case 10:case 11:case 12:case 17:case 18:p+=4;break;
                case 15:p+=3;break;
                default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);
            }
            if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
        }
        return p;
    }
    static int Find(byte[] data,byte[] value) {
        for(int i=0;i<=data.Length-value.Length;i++){bool same=true;for(int j=0;j<value.Length;j++)if(data[i+j]!=value[j]){same=false;break;}if(same)return i;}return -1;
    }
    static int Count(byte[] data,byte[] value) {
        int found=0;for(int i=0;i<=data.Length-value.Length;i++){bool same=true;for(int j=0;j<value.Length;j++)if(data[i+j]!=value[j]){same=false;break;}if(same)found++;}return found;
    }
    static bool HasUtf8(byte[] data,string value) {
        byte[] bytes=Encoding.UTF8.GetBytes(value);
        for(int i=2;i<=data.Length-bytes.Length;i++){if(U2(data,i-2)!=bytes.Length)continue;bool same=true;for(int j=0;j<bytes.Length;j++)if(data[i+j]!=bytes[j]){same=false;break;}if(same)return true;}return false;
    }
    public static byte[] ReplaceUtf8(byte[] data,string oldValue,string newValue) {
        byte[] oldBytes=Encoding.UTF8.GetBytes(oldValue),newBytes=Encoding.UTF8.GetBytes(newValue);int count=U2(data,8),p=10,oldStart=-1,oldCount=0,newCount=0;
        for(int i=1;i<count;i++){
            int tag=data[p++];
            switch(tag){
                case 1:
                    int length=U2(data,p);int start=p+2;bool oldSame=length==oldBytes.Length,newSame=length==newBytes.Length;
                    for(int j=0;j<length&&(oldSame||newSame);j++){if(oldSame&&data[start+j]!=oldBytes[j])oldSame=false;if(newSame&&data[start+j]!=newBytes[j])newSame=false;}
                    if(oldSame){oldStart=start;oldCount++;}if(newSame)newCount++;p=start+length;break;
                case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;
                case 7:case 8:case 16:case 19:case 20:p+=2;break;
                case 9:case 10:case 11:case 12:case 17:case 18:p+=4;break;case 15:p+=3;break;
                default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);
            }
            if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
        }
        if(oldCount==0&&newCount>0)return data;
        if(oldCount!=1)throw new InvalidDataException("Java metin sabiti güvenle bulunamadı: "+oldValue);
        byte[] patched=new byte[data.Length-oldBytes.Length+newBytes.Length];int lengthOffset=oldStart-2;
        Buffer.BlockCopy(data,0,patched,0,lengthOffset);patched[lengthOffset]=(byte)(newBytes.Length>>8);patched[lengthOffset+1]=(byte)newBytes.Length;
        Buffer.BlockCopy(newBytes,0,patched,oldStart,newBytes.Length);Buffer.BlockCopy(data,oldStart+oldBytes.Length,patched,oldStart+newBytes.Length,data.Length-oldStart-oldBytes.Length);return patched;
    }
    public static byte[] PatchWeatherTime(byte[] data) {
        if(HasUtf8(data,"tr-TR")&&HasUtf8(data,"forLanguageTag"))return data;
        int count;int cpEnd=ConstantPoolEnd(data,out count);
        byte[] oldCall={0xB8,0x00,0x3F,0xB6,0x00,0x3D,0xB6,0x00,0x34};int call=Find(data,oldCall);
        if(call<0||Count(data,oldCall)!=1)throw new InvalidDataException("Hava durumu saat biçimi bu oyun sürümünde güvenle bulunamadı.");
        int trUtf=count,trString=count+1,localeUtf=count+2,localeClass=count+3,nameUtf=count+4,descUtf=count+5,nameType=count+6,methodRef=count+7;
        byte[] additions;
        using(var stream=new MemoryStream()){
            PutUtf8(stream,"tr-TR");stream.WriteByte(8);PutU2(stream,trUtf);
            PutUtf8(stream,"java/util/Locale");stream.WriteByte(7);PutU2(stream,localeUtf);
            PutUtf8(stream,"forLanguageTag");PutUtf8(stream,"(Ljava/lang/String;)Ljava/util/Locale;");
            stream.WriteByte(12);PutU2(stream,nameUtf);PutU2(stream,descUtf);
            stream.WriteByte(10);PutU2(stream,localeClass);PutU2(stream,nameType);additions=stream.ToArray();
        }
        byte[] patched=new byte[data.Length+additions.Length];
        Buffer.BlockCopy(data,0,patched,0,8);patched[8]=(byte)((count+8)>>8);patched[9]=(byte)(count+8);
        Buffer.BlockCopy(data,10,patched,10,cpEnd-10);Buffer.BlockCopy(additions,0,patched,cpEnd,additions.Length);
        Buffer.BlockCopy(data,cpEnd,patched,cpEnd+additions.Length,data.Length-cpEnd);
        int target=call+additions.Length;byte[] newCall={0x13,(byte)(trString>>8),(byte)trString,0xB8,(byte)(methodRef>>8),(byte)methodRef,0x00,0x00,0x00};
        Buffer.BlockCopy(newCall,0,patched,target,newCall.Length);return patched;
    }
    public static byte[] PatchBattlegroundTime(byte[] data) {
        if(HasUtf8(data,"tr-TR")&&HasUtf8(data,"forLanguageTag"))return data;
        int count;int cpEnd=ConstantPoolEnd(data,out count);
        byte[] oldCall={0xB8,0x00,0x73,0xB6,0x00,0x71,0xB6,0x00,0x66};
        if(Count(data,oldCall)!=3)throw new InvalidDataException("Savaş alanı tarih-saat biçimi bu oyun sürümünde güvenle bulunamadı.");
        int trUtf=count,trString=count+1,localeUtf=count+2,localeClass=count+3,nameUtf=count+4,descUtf=count+5,nameType=count+6,methodRef=count+7;
        byte[] additions;
        using(var stream=new MemoryStream()){
            PutUtf8(stream,"tr-TR");stream.WriteByte(8);PutU2(stream,trUtf);
            PutUtf8(stream,"java/util/Locale");stream.WriteByte(7);PutU2(stream,localeUtf);
            PutUtf8(stream,"forLanguageTag");PutUtf8(stream,"(Ljava/lang/String;)Ljava/util/Locale;");
            stream.WriteByte(12);PutU2(stream,nameUtf);PutU2(stream,descUtf);
            stream.WriteByte(10);PutU2(stream,localeClass);PutU2(stream,nameType);additions=stream.ToArray();
        }
        byte[] patched=new byte[data.Length+additions.Length];
        Buffer.BlockCopy(data,0,patched,0,8);patched[8]=(byte)((count+8)>>8);patched[9]=(byte)(count+8);
        Buffer.BlockCopy(data,10,patched,10,cpEnd-10);Buffer.BlockCopy(additions,0,patched,cpEnd,additions.Length);
        Buffer.BlockCopy(data,cpEnd,patched,cpEnd+additions.Length,data.Length-cpEnd);
        byte[] newCall={0x13,(byte)(trString>>8),(byte)trString,0xB8,(byte)(methodRef>>8),(byte)methodRef,0x00,0x00,0x00};
        for(int n=0;n<3;n++){
            int target=Find(patched,oldCall);if(target<0)throw new InvalidDataException("Savaş alanı tarih-saat çağrısı eksik kaldı.");
            Buffer.BlockCopy(newCall,0,patched,target,newCall.Length);
        }
        return patched;
    }
    static void CountPersistentNameOverheadPatterns(byte[] data,out int original,out int legacyBad,out int safeCount) {
        original=-1;legacyBad=-1;safeCount=0;int originalCount=0,legacyBadCount=0;
        for(int i=0;i<=data.Length-9;i++){
            bool tail=data[i+3]==0x07&&data[i+4]==0x2A&&data[i+5]==0xB6&&data[i+8]==0xB1;
            if(!tail)continue;
            if(data[i]==0x1B&&data[i+1]==0x9A&&data[i+2]==0x00){original=i;originalCount++;}
            if(data[i]==0xA7&&data[i+1]==0x00&&data[i+2]==0x08){legacyBad=i;legacyBadCount++;}
            if(data[i]==0x04&&data[i+1]==0x9A&&data[i+2]==0x00)safeCount++;
        }
        if(originalCount!=1)original=-1;
        if(legacyBadCount!=1)legacyBad=-1;
        if(originalCount>1||legacyBadCount>1)safeCount=-1;
    }
    public static bool HasSafePersistentNameOverhead(byte[] data) {
        int original,legacyBad,safeCount;CountPersistentNameOverheadPatterns(data,out original,out legacyBad,out safeCount);
        return original<0&&legacyBad<0&&safeCount==1;
    }
    public static byte[] PatchPersistentNameOverhead(byte[] data) {
        int original,legacyBad,safeCount;CountPersistentNameOverheadPatterns(data,out original,out legacyBad,out safeCount);
        if(original<0&&legacyBad<0&&safeCount==1)return data;
        int target=original>=0?original:legacyBad;
        if(target<0||safeCount!=0)throw new InvalidDataException("Kalıcı V oyuncu adı yaşam döngüsü bu oyun sürümünde güvenle bulunamadı.");
        byte[] result=(byte[])data.Clone();
        // Geçici görünürlük olayları isimleri temizleyemez. V'nin kapatma yolu
        // yöneticideki doğrudan clean() çağrısını kullandığından aynen çalışır.
        // Yalnız iload_1 -> iconst_1 değiştirilir; dal ve StackMapTable yapısı korunur.
        result[target]=0x04;result[target+1]=0x9A;result[target+2]=0x00;result[target+3]=0x07;
        if(!HasSafePersistentNameOverhead(result))throw new InvalidDataException("Kalıcı V oyuncu adı yaması doğrulanamadı.");
        return result;
    }
    static int U4(byte[] data,int offset) {
        if(offset<0||offset+4>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
        long value=((long)data[offset]<<24)|((long)data[offset+1]<<16)|((long)data[offset+2]<<8)|data[offset+3];
        if(value>Int32.MaxValue)throw new InvalidDataException("Java sınıfı bölümü çok büyük.");
        return (int)value;
    }
    static int SkipJavaAttributes(byte[] data,int position,int count) {
        for(int i=0;i<count;i++){
            if(position+6>data.Length)throw new InvalidDataException("Eksik Java özniteliği.");
            int length=U4(data,position+2);position+=6;
            if(position+length>data.Length)throw new InvalidDataException("Eksik Java özniteliği.");
            position+=length;
        }
        return position;
    }
    static int LocateHoverCompatibleNameToggleTail(byte[] data,out bool patched) {
        int cpCount;int cpEnd=ConstantPoolEnd(data,out cpCount);var tags=new byte[cpCount];var first=new int[cpCount];var second=new int[cpCount];var utf8=new string[cpCount];int p=10;
        for(int i=1;i<cpCount;i++){
            int tag=data[p++];tags[i]=(byte)tag;
            switch(tag){
                case 1:int length=U2(data,p);p+=2;utf8[i]=Encoding.UTF8.GetString(data,p,length);p+=length;break;
                case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;
                case 7:case 8:case 16:case 19:case 20:first[i]=U2(data,p);p+=2;break;
                case 9:case 10:case 11:case 12:case 17:case 18:first[i]=U2(data,p);second[i]=U2(data,p+2);p+=4;break;
                case 15:first[i]=data[p];second[i]=U2(data,p+1);p+=3;break;
                default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);
            }
            if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
        }
        if(p!=cpEnd||p+8>data.Length)throw new InvalidDataException("Eksik Java sınıfı gövdesi.");
        int thisClass=U2(data,p+2);p+=6;int interfaceCount=U2(data,p);p+=2+2*interfaceCount;
        if(p+2>data.Length)throw new InvalidDataException("Eksik Java alan tablosu.");
        int fieldCount=U2(data,p);p+=2;
        for(int i=0;i<fieldCount;i++){if(p+8>data.Length)throw new InvalidDataException("Eksik Java alanı.");int attributes=U2(data,p+6);p=SkipJavaAttributes(data,p+8,attributes);}
        if(p+2>data.Length)throw new InvalidDataException("Eksik Java yöntem tablosu.");
        int methodCount=U2(data,p);p+=2;int target=-1,candidates=0;bool targetPatched=false,hasCwc=false;
        for(int i=0;i<methodCount;i++){
            if(p+8>data.Length)throw new InvalidDataException("Eksik Java yöntemi.");
            int nameIndex=U2(data,p+2),descriptorIndex=U2(data,p+4),attributeCount=U2(data,p+6);string methodName=utf8[nameIndex],descriptor=utf8[descriptorIndex];p+=8;
            if(methodName=="cWC"&&descriptor=="()V")hasCwc=true;
            for(int j=0;j<attributeCount;j++){
                if(p+6>data.Length)throw new InvalidDataException("Eksik Java yöntem özniteliği.");int attributeName=U2(data,p),attributeLength=U4(data,p+2),info=p+6;
                if(info+attributeLength>data.Length)throw new InvalidDataException("Eksik Java yöntem özniteliği.");
                if(methodName=="a"&&utf8[attributeName]=="Code"){
                    if(attributeLength<12)throw new InvalidDataException("Eksik Java kod özniteliği.");int codeLength=U4(data,info+4),codeStart=info+8,codeEnd=codeStart+codeLength;
                    if(codeEnd>info+attributeLength||codeLength<4)throw new InvalidDataException("Eksik Java yöntem kodu.");
                    bool isPatched=data[codeEnd-4]==0x00&&data[codeEnd-3]==0x00&&data[codeEnd-2]==0x00&&data[codeEnd-1]==0xB1;
                    bool isOriginal=false;
                    if(data[codeEnd-4]==0xB8&&data[codeEnd-1]==0xB1){int methodRef=U2(data,codeEnd-3);if(methodRef>0&&methodRef<cpCount&&tags[methodRef]==10&&first[methodRef]==thisClass){int nameType=second[methodRef];isOriginal=nameType>0&&nameType<cpCount&&tags[nameType]==12&&utf8[first[nameType]]=="cWC"&&utf8[second[nameType]]=="()V";}}
                    if(isOriginal||isPatched){target=codeEnd-4;targetPatched=isPatched;candidates++;}
                }
                p=info+attributeLength;
            }
        }
        if(!hasCwc||candidates!=1||target<0)throw new InvalidDataException("V fare üstü uyumluluk noktası bu oyun sürümünde güvenle bulunamadı.");patched=targetPatched;return target;
    }
    public static bool HasHoverCompatibleNameToggle(byte[] data) {
        try{bool patched;LocateHoverCompatibleNameToggleTail(data,out patched);return patched;}catch{return false;}
    }
    public static byte[] PatchHoverCompatibleNameToggle(byte[] data) {
        bool patched;int target=LocateHoverCompatibleNameToggleTail(data,out patched);if(patched)return data;
        byte[] result=(byte[])data.Clone();result[target]=0x00;result[target+1]=0x00;result[target+2]=0x00;
        if(!HasHoverCompatibleNameToggle(result))throw new InvalidDataException("V açıkken fare üstü ad yaması doğrulanamadı.");return result;
    }
    static int FindUtf8Constant(byte[] data,string value,out int matches) {
        byte[] wanted=Encoding.UTF8.GetBytes(value);matches=0;int found=-1,count=U2(data,8),p=10;
        for(int i=1;i<count;i++){
            if(p>=data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
            int tag=data[p++];
            switch(tag){
                case 1:
                    if(p+2>data.Length)throw new InvalidDataException("Eksik Java UTF-8 sabiti.");
                    int length=U2(data,p),start=p+2;if(start+length>data.Length)throw new InvalidDataException("Eksik Java UTF-8 sabiti.");
                    bool same=length==wanted.Length;
                    for(int j=0;j<length&&same;j++)if(data[start+j]!=wanted[j])same=false;
                    if(same){matches++;found=start;}p=start+length;break;
                case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;
                case 7:case 8:case 16:case 19:case 20:p+=2;break;
                case 9:case 10:case 11:case 12:case 17:case 18:p+=4;break;case 15:p+=3;break;
                default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);
            }
            if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
        }
        return found;
    }
    static int OverheadFontProfile(int mainSize,int titleSize) {
        if(mainSize==28&&titleSize==24)return 0;
        if(mainSize==24&&titleSize==20)return 1;
        if(mainSize==20&&titleSize==16)return 2;
        throw new ArgumentOutOfRangeException("mainSize","Desteklenmeyen baş üstü yazı profili.");
    }
    static string OverheadFontName(int size) { return "fontNarrow"+size+"BoldBordered"; }
    static int DetectOverheadFontProfile(byte[] data) {
        int c28,c24,c20,c16;
        FindUtf8Constant(data,OverheadFontName(28),out c28);FindUtf8Constant(data,OverheadFontName(24),out c24);
        FindUtf8Constant(data,OverheadFontName(20),out c20);FindUtf8Constant(data,OverheadFontName(16),out c16);
        if(c28==1&&c24==1&&c20==0&&c16==0)return 0;
        if(c28==0&&c24==1&&c20==1&&c16==0)return 1;
        if(c28==0&&c24==0&&c20==1&&c16==1)return 2;
        return -1;
    }
    public static bool HasOverheadFontProfile(byte[] data,int mainSize,int titleSize) {
        return DetectOverheadFontProfile(data)==OverheadFontProfile(mainSize,titleSize);
    }
    public static byte[] PatchOverheadFontProfile(byte[] data,int mainSize,int titleSize) {
        int targetProfile=OverheadFontProfile(mainSize,titleSize),sourceProfile=DetectOverheadFontProfile(data);
        if(sourceProfile==targetProfile)return data;
        if(sourceProfile<0)throw new InvalidDataException("Baş üstü oyuncu adı yazı çifti bu oyun sürümünde güvenle bulunamadı.");
        int sourceMain=sourceProfile==0?28:(sourceProfile==1?24:20);
        int sourceTitle=sourceProfile==0?24:(sourceProfile==1?20:16);
        int mainMatches,titleMatches;
        int mainStart=FindUtf8Constant(data,OverheadFontName(sourceMain),out mainMatches);
        int titleStart=FindUtf8Constant(data,OverheadFontName(sourceTitle),out titleMatches);
        byte[] mainBytes=Encoding.UTF8.GetBytes(OverheadFontName(mainSize));
        byte[] titleBytes=Encoding.UTF8.GetBytes(OverheadFontName(titleSize));
        if(mainMatches!=1||titleMatches!=1||mainBytes.Length!=OverheadFontName(sourceMain).Length||titleBytes.Length!=OverheadFontName(sourceTitle).Length)
            throw new InvalidDataException("Baş üstü oyuncu adı yazı çifti güvenle değiştirilemedi.");
        byte[] result=(byte[])data.Clone();
        Buffer.BlockCopy(mainBytes,0,result,mainStart,mainBytes.Length);Buffer.BlockCopy(titleBytes,0,result,titleStart,titleBytes.Length);
        if(!HasOverheadFontProfile(result,mainSize,titleSize))throw new InvalidDataException("Baş üstü oyuncu adı yazı profili doğrulanamadı.");
        return result;
    }
}
'@
}

$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = if($env:WAKFU_PROJECT_ROOT -and (Test-Path -LiteralPath $env:WAKFU_PROJECT_ROOT)){
    [IO.Path]::GetFullPath($env:WAKFU_PROJECT_ROOT)
}elseif((Split-Path -Leaf $ToolDir)-eq'Kaynak_Kodu'){
    Split-Path -Parent $ToolDir
}else{
    $ToolDir
}
$AppVersion='07.09-WakfuQuality-v65-Portable'
function Test-WakfuGameDir([string]$path){return (-not[string]::IsNullOrWhiteSpace($path)) -and (Test-Path -LiteralPath (Join-Path $path 'contents\i18n\i18n_en.jar'))}
function Find-WakfuInSteam([string]$steamRoot){
    if([string]::IsNullOrWhiteSpace($steamRoot)){return $null}
    if(Test-WakfuGameDir $steamRoot){return [IO.Path]::GetFullPath($steamRoot)}
    $direct=Join-Path $steamRoot 'steamapps\common\Wakfu';if(Test-WakfuGameDir $direct){return [IO.Path]::GetFullPath($direct)}
    $vdf=Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
    if(Test-Path -LiteralPath $vdf){
        $text=Get-Content -LiteralPath $vdf -Raw -ErrorAction SilentlyContinue
        foreach($match in [regex]::Matches([string]$text,'"path"\s+"([^"]+)"')){
            $library=$match.Groups[1].Value.Replace('\\','\');$candidate=Join-Path $library 'steamapps\common\Wakfu'
            if(Test-WakfuGameDir $candidate){return [IO.Path]::GetFullPath($candidate)}
        }
    }
    return $null
}
function Find-WakfuGameDir {
    $candidates=New-Object Collections.Generic.List[string]
    if($env:WAKFU_GAME_DIR){[void]$candidates.Add([string]$env:WAKFU_GAME_DIR)}
    $rememberedFile=Join-Path $ProjectRoot 'Ayarlar\wakfu_oyun_yolu.txt'
    if(Test-Path -LiteralPath $rememberedFile){$remembered=(Get-Content -LiteralPath $rememberedFile -Raw -ErrorAction SilentlyContinue).Trim();if($remembered){[void]$candidates.Add($remembered)}}
    foreach($root in @(${env:ProgramFiles(x86)},$env:ProgramFiles)) {if($root){[void]$candidates.Add((Join-Path $root 'Steam'))}}
    foreach($key in @('HKCU:\Software\Valve\Steam','HKLM:\Software\Valve\Steam','HKLM:\Software\WOW6432Node\Valve\Steam')){
        try{$props=Get-ItemProperty -LiteralPath $key -ErrorAction Stop;$steam=[string]($props.SteamPath);if(-not$steam){$steam=[string]($props.InstallPath)};if($steam){[void]$candidates.Add($steam)}}catch{}
    }
    foreach($candidate in $candidates){$found=Find-WakfuInSteam $candidate;if($found){return $found}}
    return $null
}
$GameDir=Find-WakfuGameDir
if(-not$GameDir){$GameDir=Join-Path ${env:ProgramFiles(x86)} 'Steam\steamapps\common\Wakfu'}
$script:CanonicalUiTranslations=@{
    'achievement.quest.type.1'='Destan';'quest.categoryTitle.epic'='Destan'
    'AP'='Aksiyon Puanları';'BAGS'='Çantalar';'bestiary.label'='Canavar Kitabı';'booster.pack.ui.title'='Güçlendirici'
    'battleground.01.supply.bonus.2'='Milis';'BLAZED_SMILEYS'='Bezgin'
    'blindBox.desc.rollSkip'='Aç / Geç';'boat.noDestinationAvailable'='Kullanılabilir varış noktası yok'
    'bonusPenalties'='Bonuslar / Cezalar';'bonusPointDistributionTable'='Tablolar yükleniyor'
    'booster.pack.inactive'='ETKİN DEĞİL';'citizenRank.name.HOODLUM'='Kanun Kaçağı'
    'citizenRank.name.INHABITANT'='Sakin';'notification.outlawTitle'='Kanun Kaçağı'
    'tuto.PvpNation.title'='Kanun Kaçağı';'options.playability'='Oynanış'
    'min'='En az';'max'='En çok'
    'rerollXp.info.notRight'="İkincil karakterler için XP bonusu. Bu bonus, bir Güçlendirici ile x[#1.1]'ye yükseltilebilir."
    'content.8.1263'='Oynanış';'content.8.2718'='Oynanış';'content.8.4048'='Oynanış'
    'content.8.4260'='Oynanış';'content.8.5817'='Oynanış';'content.8.5865'='Oynanış';'content.8.7386'='Oynanış'
    'content.15.2175'='Cepler';'content.15.11955'='Dev Piwi Kesesi';'content.15.15865'='Geniş Madenci Kutusu';'content.15.19799'='Bileşen Sepeti';'content.15.31167'='Göksel Çanta'
    'content.15.24267'='Deneyim';'content.15.27097'='Yakın Dövüş Ustalığı';'content.15.27098'='Menzil Ustalığı'
    'content.15.27099'='Berserk Ustalığı';'content.15.27110'='İyileştirme Ustalığı';'content.15.29612'='Ara'
    'content.62.2170'='Karanlık Odalar';'content.64.11374'='"Astrub - Prologue" ana görevini tamamla (Karanlık Odalar)'
}
$DataDir = Join-Path $ProjectRoot 'Ceviri_Verileri'
$SettingsDir = Join-Path $ProjectRoot 'Ayarlar'
$BuildDir = Join-Path $ProjectRoot 'Uretilenler'
$ReportsDir = Join-Path $ProjectRoot 'Raporlar'
$GameAssetsDir = Join-Path $ProjectRoot 'Oyun_Kaynaklari'
$TranslationBackupDir=Join-Path $DataDir 'Yedekler'
foreach($requiredDir in @($DataDir,$SettingsDir,$BuildDir,$ReportsDir,$GameAssetsDir,$TranslationBackupDir)){New-Item -ItemType Directory -Path $requiredDir -Force|Out-Null}
$ProjectFile = Join-Path $DataDir 'wakfu_tr_ceviri.json'
$TerminologyFile = Join-Path $DataDir 'terim_duzeltmeleri.json'
$ManualRepairsFile = Join-Path $DataDir 'manual_repairs_v23.json'
$OutputJar = Join-Path $BuildDir 'i18n.jar'
$PackagedBackupDir = Join-Path $GameAssetsDir 'Orijinal_Yedek'
$BackupDir = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'WakfuTurkceYama\Yedekler\Resmi_Oyun_Dosyalari'
$MirrorBackupRoot = $null
$InstalledEnglishJar = Join-Path $GameDir 'contents\i18n\i18n_en.jar'
$OriginalEnglishJar = Join-Path $BackupDir 'i18n_en.jar'
$PackagedBaseEnglishJar = Join-Path $PackagedBackupDir 'i18n_en.jar'
$CurrentSourceDir = Join-Path $GameAssetsDir 'Guncel'
$CurrentEnglishJar = Join-Path $CurrentSourceDir 'i18n_en.jar'
$SourceJar = if (Test-Path -LiteralPath $CurrentEnglishJar) { $CurrentEnglishJar } elseif (Test-Path -LiteralPath $OriginalEnglishJar) { $OriginalEnglishJar } elseif(Test-Path -LiteralPath $PackagedBaseEnglishJar){$PackagedBaseEnglishJar}else { $InstalledEnglishJar }
$InstalledGuiJar = Join-Path $GameDir 'contents\gui_jar\gui.jar'
$OriginalGuiJar = Join-Path $BackupDir 'gui.jar'
$CurrentGuiJar = Join-Path $CurrentSourceDir 'gui.jar'
$OutputGuiJar = Join-Path $BuildDir 'gui_tr.jar'
$InstalledClientJar = Join-Path $GameDir 'lib\wakfu-client.jar'
$OriginalClientJar = Join-Path $BackupDir 'wakfu-client.jar'
$CurrentClientJar = Join-Path $CurrentSourceDir 'wakfu-client.jar'
$OutputClientJar = Join-Path $BuildDir 'wakfu-client_tr.jar'
$InstalledDataJar = Join-Path $GameDir 'contents\data\data.jar'
$OriginalDataJar = Join-Path $BackupDir 'data.jar'
$CurrentDataJar = Join-Path $CurrentSourceDir 'data.jar'
$OutputDataJar = Join-Path $BuildDir 'data_tr.jar'
$InstallStateFile=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'WakfuTurkceYama\kurulum_durumu.json'
function Set-WakfuGameDir([string]$path){
    if(-not(Test-WakfuGameDir $path)){throw 'Geçerli Wakfu klasörü seçilmedi.'}
    $script:GameDir=[IO.Path]::GetFullPath($path)
    $script:InstalledEnglishJar=Join-Path $script:GameDir 'contents\i18n\i18n_en.jar'
    $script:InstalledGuiJar=Join-Path $script:GameDir 'contents\gui_jar\gui.jar'
    $script:InstalledClientJar=Join-Path $script:GameDir 'lib\wakfu-client.jar'
    $script:InstalledDataJar=Join-Path $script:GameDir 'contents\data\data.jar'
    [IO.File]::WriteAllText((Join-Path $SettingsDir 'wakfu_oyun_yolu.txt'),$script:GameDir,(New-Object Text.UTF8Encoding($false)))
}
function Ensure-WakfuGameDir {
    if(Test-WakfuGameDir $script:GameDir){Set-WakfuGameDir $script:GameDir;return $true}
    $picker=New-Object Windows.Forms.FolderBrowserDialog;$picker.Description='Wakfu oyun klasörünü seçin (içinde contents ve lib klasörleri bulunur).'
    if($picker.ShowDialog()-ne[Windows.Forms.DialogResult]::OK){return $false}
    try{Set-WakfuGameDir $picker.SelectedPath;return $true}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Wakfu klasörü','OK','Error')|Out-Null;return $false}
}
$AlmanaxPatchClass = Join-Path $GameAssetsDir 'Yamalar\almanax_bgU.class'
$FontPatchDir = Join-Path $GameAssetsDir 'Fontlar'
$GoogleWorkerCount = 10
$GpuPathFile=Join-Path $SettingsDir 'gpu_runtime_path.txt'
function Find-ExistingGpuRuntime {
    $candidates=New-Object Collections.Generic.List[string]
    if(Test-Path -LiteralPath $GpuPathFile){
        $remembered=[string](Get-Content -LiteralPath $GpuPathFile -Raw -ErrorAction SilentlyContinue)
        if($remembered){[void]$candidates.Add($remembered.Trim())}
    }
    if($env:WAKFU_GPU_RUNTIME){[void]$candidates.Add([string]$env:WAKFU_GPU_RUNTIME)}
    [void]$candidates.Add((Join-Path $ProjectRoot 'GPU'))
    foreach($candidate in $candidates){if(Test-Path -LiteralPath (Join-Path $candidate 'venv\Scripts\python.exe')){return $candidate}}
    return $null
}
$DetectedGpuRuntime=Find-ExistingGpuRuntime
$GpuRuntimeDir = if($DetectedGpuRuntime){$DetectedGpuRuntime}else{(Join-Path $ProjectRoot 'GPU')}
$GpuPython = Join-Path $GpuRuntimeDir 'venv\Scripts\python.exe'
if($DetectedGpuRuntime){[IO.File]::WriteAllText($GpuPathFile,$DetectedGpuRuntime,(New-Object Text.UTF8Encoding($false)))}
$GpuWorker = Join-Path $ToolDir 'wakfu_gpu_translate.py'
$AuditWorker = Join-Path $ToolDir 'wakfu_audit.py'
$JarBuilder = Join-Path $ToolDir 'build_wakfu_jar.py'
$AuditPython = Join-Path $ProjectRoot 'Araclar\Python\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $AuditPython)){
    if(Test-Path -LiteralPath $GpuPython){
        $AuditPython=$GpuPython
    }else{
        $pythonCommand=Get-Command python.exe -ErrorAction SilentlyContinue
        if($pythonCommand -and $pythonCommand.Source -notmatch '(?i)\\WindowsApps\\python(?:3)?\.exe$' -and (Test-Path -LiteralPath $pythonCommand.Source)){$AuditPython=$pythonCommand.Source}
    }
}
$SetupBuilder = Join-Path $ToolDir 'WakfuSetupOlustur.ps1'
$SetupExe = Join-Path $ProjectRoot 'Wakfu_Turkce_Yama_Setup.exe'
$script:GpuProcess = $null
$script:GpuResultFile = $null
$script:Entries = @()
$script:Visible = @()
$script:Translations = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
$script:TermKeys = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
$script:TermValues = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
$script:TermPhrases = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
$script:ManualRepairs = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
$script:SortedTermPhraseKeys = @()
$script:SelectedKey = $null
$script:LoadedTurkishValue = ''
$script:CancelTranslation = $false
$script:ReverseSearchCache=@{}
$script:Closing=$false
$script:BulkPromptPending=$false
$script:LoadingEntry=$false
$script:ProjectDirty=$false
$script:ManualDirty=$false
$script:BuildDirty=$false
$script:SaveTimer=$null
$script:EntryEnglish=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
$script:ProtectedNameValues=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
$script:SkillTitleValues=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
$script:ItemTitleValues=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
$script:SearchKeys=[string[]]@()
$script:SearchEnglish=[string[]]@()
$script:SearchTurkish=[string[]]@()
$LogDir=$ReportsDir
$LogFile=Join-Path $LogDir 'Wakfu_Ceviri_Log.txt'
$LiveTsv=Join-Path $LogDir 'Wakfu_Ceviri_Canli.tsv'
$StatusTsv=Join-Path $LogDir 'Wakfu_Ceviri_Durum.tsv'
$IssuesTsv=Join-Path $LogDir 'Wakfu_Ceviri_Sorunlar.tsv'
$DiagnosticSummary=Join-Path $LogDir 'Wakfu_Ceviri_Ozet.txt'
$LastGpuInput=Join-Path $LogDir 'Wakfu_GPU_Son_Girdi.jsonl'
$LastGpuOutput=Join-Path $LogDir 'Wakfu_GPU_Son_Sonuc.jsonl'
$LastGpuContext=Join-Path $DataDir 'Wakfu_GPU_Baglam.json'
$UiSettingsFile=Join-Path $SettingsDir 'arayuz_ayarlari.json'
# Varsayılan: koyu charcoal/navy tema (açık tema istenirse ayardan kapatılır).
$script:DarkThemeEnabled=$true
$script:OverheadTextScaleProfile='tiny'
if(Test-Path -LiteralPath $UiSettingsFile){
    try{
        $savedUi=Get-Content -LiteralPath $UiSettingsFile -Raw -Encoding UTF8|ConvertFrom-Json
        if($null-ne$savedUi.DarkTheme){$script:DarkThemeEnabled=[bool]$savedUi.DarkTheme}
        $savedOverheadProfile=[string]$savedUi.OverheadTextScaleProfile
        if($savedOverheadProfile-in@('normal','small','tiny')){$script:OverheadTextScaleProfile=$savedOverheadProfile}
    }catch{}
}

function Get-OverheadFontProfile {
    switch([string]$script:OverheadTextScaleProfile){
        'normal' {return [pscustomobject]@{Key='normal';Main=28;Title=24;Label='Normal (28 / 24)'}}
        'tiny' {return [pscustomobject]@{Key='tiny';Main=20;Title=16;Label='Çok küçük (20 / 16) — Önerilen'}}
        default {return [pscustomobject]@{Key='small';Main=24;Title=20;Label='Küçük (24 / 20)'}}
    }
}

function Save-UiSettings {
    try{
        $settings=[ordered]@{DarkTheme=[bool]$script:DarkThemeEnabled;OverheadTextScaleProfile=[string](Get-OverheadFontProfile).Key}
        [IO.File]::WriteAllText($UiSettingsFile,($settings|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)))
    }catch{Write-AppLog "Arayüz ayarı kaydedilemedi: $($_.Exception.Message)"}
}

function Set-ControlTheme([Windows.Forms.Control]$control,[bool]$dark) {
    # Charcoal / lacivert tonları — mor AI klişesinden kaçınılır.
    $bg=if($dark){[Drawing.Color]::FromArgb(20,23,28)}else{[Drawing.SystemColors]::Control}
    $surface=if($dark){[Drawing.Color]::FromArgb(28,33,40)}else{[Drawing.SystemColors]::Control}
    $input=if($dark){[Drawing.Color]::FromArgb(34,40,48)}else{[Drawing.SystemColors]::Window}
    $textColor=if($dark){[Drawing.Color]::FromArgb(236,239,244)}else{[Drawing.SystemColors]::ControlText}
    $muted=if($dark){[Drawing.Color]::FromArgb(154,165,180)}else{[Drawing.SystemColors]::ControlText}
    $header=if($dark){[Drawing.Color]::FromArgb(39,47,57)}else{[Drawing.SystemColors]::Control}
    $altRow=if($dark){[Drawing.Color]::FromArgb(30,36,44)}else{[Drawing.SystemColors]::Window}
    $select=if($dark){[Drawing.Color]::FromArgb(25,94,145)}else{[Drawing.SystemColors]::Highlight}
    $btnFace=if($dark){[Drawing.Color]::FromArgb(45,53,63)}else{[Drawing.SystemColors]::Control}
    $btnBorder=if($dark){[Drawing.Color]::FromArgb(75,88,104)}else{[Drawing.SystemColors]::ControlDark}

    if($control-is[Windows.Forms.DataGridView]){
        $control.BackgroundColor=if($dark){[Drawing.Color]::FromArgb(24,26,30)}else{[Drawing.SystemColors]::AppWorkspace}
        $control.GridColor=if($dark){[Drawing.Color]::FromArgb(70,76,86)}else{[Drawing.SystemColors]::ControlDark}
        $control.BorderStyle=if($dark){'FixedSingle'}else{'Fixed3D'}
        $control.CellBorderStyle=if($dark){'SingleHorizontal'}else{'Single'}
        $control.RowHeadersBorderStyle='Single'
        $control.EnableHeadersVisualStyles=-not$dark
        $control.ColumnHeadersBorderStyle='Single'
        $control.ColumnHeadersDefaultCellStyle.BackColor=$header
        $control.ColumnHeadersDefaultCellStyle.ForeColor=$textColor
        $control.ColumnHeadersDefaultCellStyle.SelectionBackColor=$header
        $control.ColumnHeadersDefaultCellStyle.SelectionForeColor=$textColor
        $control.RowHeadersDefaultCellStyle.BackColor=$header
        $control.RowHeadersDefaultCellStyle.ForeColor=$textColor
        $control.RowHeadersDefaultCellStyle.SelectionBackColor=$select
        $control.RowHeadersDefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
        $control.DefaultCellStyle.BackColor=$input
        $control.DefaultCellStyle.ForeColor=$textColor
        $control.DefaultCellStyle.SelectionBackColor=$select
        $control.DefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
        $control.RowsDefaultCellStyle.BackColor=$input
        $control.RowsDefaultCellStyle.ForeColor=$textColor
        $control.RowsDefaultCellStyle.SelectionBackColor=$select
        $control.RowsDefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
        $control.AlternatingRowsDefaultCellStyle.BackColor=$altRow
        $control.AlternatingRowsDefaultCellStyle.ForeColor=$textColor
        $control.AlternatingRowsDefaultCellStyle.SelectionBackColor=$select
        $control.AlternatingRowsDefaultCellStyle.SelectionForeColor=[Drawing.Color]::White
    }elseif($control-is[Windows.Forms.TextBoxBase]){
        $control.BackColor=$input;$control.ForeColor=$textColor
        if($control-is[Windows.Forms.TextBox]){$control.BorderStyle='FixedSingle'}
    }elseif($control-is[Windows.Forms.ComboBox]){
        $control.BackColor=$input;$control.ForeColor=$textColor;$control.FlatStyle=if($dark){'Flat'}else{'Standard'}
    }elseif($control-is[Windows.Forms.CheckBox]){
        $control.UseVisualStyleBackColor=-not$dark
        $control.FlatStyle=if($dark){'Flat'}else{'Standard'}
        $control.BackColor=$surface;$control.ForeColor=$textColor
    }elseif($control-is[Windows.Forms.Label]){
        $control.BackColor=$surface;$control.ForeColor=$textColor
    }elseif($control-is[Windows.Forms.StatusStrip]){
        $control.BackColor=$surface;$control.ForeColor=$textColor
        $control.RenderMode='Professional'
        $control.SizingGrip=$false
        foreach($item in $control.Items){
            $item.ForeColor=$textColor
            try{$item.BackColor=$surface}catch{}
        }
    }elseif($control-is[Windows.Forms.Button]){
        $control.UseVisualStyleBackColor=-not$dark
        $control.BackColor=$btnFace;$control.ForeColor=$textColor
        $control.FlatStyle=if($dark){'Flat'}else{'Standard'}
        if($dark){$control.FlatAppearance.BorderColor=$btnBorder;$control.FlatAppearance.BorderSize=1;$control.FlatAppearance.MouseOverBackColor=[Drawing.Color]::FromArgb(58,70,84);$control.FlatAppearance.MouseDownBackColor=[Drawing.Color]::FromArgb(38,82,112)}
    }elseif($control-is[Windows.Forms.TabControl]){
        $control.BackColor=$bg;$control.ForeColor=$textColor
        if($dark){$control.DrawMode='OwnerDrawFixed'}else{$control.DrawMode='Normal'}
    }elseif($control-is[Windows.Forms.TabPage]){
        $control.BackColor=$bg;$control.ForeColor=$textColor
        $control.UseVisualStyleBackColor=-not$dark
    }elseif($control-is[Windows.Forms.SplitContainer]){
        $control.BackColor=if($dark){[Drawing.Color]::FromArgb(50,56,66)}else{[Drawing.SystemColors]::ControlDark}
        $control.Panel1.BackColor=$bg;$control.Panel2.BackColor=$bg
    }elseif($control-is[Windows.Forms.Panel] -or $control-is[Windows.Forms.TableLayoutPanel]){
        $control.BackColor=$surface;$control.ForeColor=$textColor
    }else{
        $control.BackColor=$bg;$control.ForeColor=$textColor
    }
    foreach($child in @($control.Controls)){Set-ControlTheme $child $dark}
}

function Set-AppTheme([bool]$dark) {
    if($null-eq$form){return}
    Set-ControlTheme $form $dark
    if($null-ne$hint){$hint.ForeColor=if($dark){[Drawing.Color]::FromArgb(158,166,178)}else{[Drawing.SystemColors]::GrayText}}
    if($null-ne$allText){$allText.ForeColor=if($dark){[Drawing.Color]::FromArgb(158,166,178)}else{[Drawing.SystemColors]::ControlText}}
    if($null-ne$gpuText){$gpuText.ForeColor=if($dark){[Drawing.Color]::FromArgb(158,166,178)}else{[Drawing.SystemColors]::ControlText}}
    if($null-ne$logText){$logText.ForeColor=if($dark){[Drawing.Color]::FromArgb(158,166,178)}else{[Drawing.SystemColors]::ControlText}}
    if($dark){
        $btnGpu.BackColor=[Drawing.Color]::FromArgb(40,110,55);$btnGpu.ForeColor=[Drawing.Color]::White
        $btnInstall.BackColor=[Drawing.Color]::FromArgb(196,150,20);$btnInstall.ForeColor=[Drawing.Color]::White
        if($null-ne$btnInstallSetup){$btnInstallSetup.BackColor=[Drawing.Color]::FromArgb(196,150,20);$btnInstallSetup.ForeColor=[Drawing.Color]::White}
        $btnClearMemory.BackColor=[Drawing.Color]::FromArgb(130,48,48);$btnClearMemory.ForeColor=[Drawing.Color]::White
        $btnClearGamePatch.BackColor=[Drawing.Color]::FromArgb(120,95,35);$btnClearGamePatch.ForeColor=[Drawing.Color]::White
        $btnSetupBuild.BackColor=[Drawing.Color]::FromArgb(40,110,55);$btnSetupBuild.ForeColor=[Drawing.Color]::White
    }else{
        $btnGpu.BackColor=[Drawing.Color]::PaleGreen;$btnGpu.ForeColor=[Drawing.SystemColors]::ControlText
        $btnInstall.BackColor=[Drawing.Color]::Gold;$btnInstall.ForeColor=[Drawing.SystemColors]::ControlText
        if($null-ne$btnInstallSetup){$btnInstallSetup.BackColor=[Drawing.Color]::Gold;$btnInstallSetup.ForeColor=[Drawing.SystemColors]::ControlText}
        $btnClearMemory.BackColor=[Drawing.Color]::MistyRose;$btnClearMemory.ForeColor=[Drawing.SystemColors]::ControlText
        $btnClearGamePatch.BackColor=[Drawing.Color]::LightGoldenrodYellow;$btnClearGamePatch.ForeColor=[Drawing.SystemColors]::ControlText
        $btnSetupBuild.BackColor=[Drawing.Color]::PaleGreen;$btnSetupBuild.ForeColor=[Drawing.SystemColors]::ControlText
    }
    $form.Invalidate($true)
    if($script:SelectedKey){Apply-TurkishEditorState (Test-IsForcedEnglishNameKey $script:SelectedKey)}
}

function Test-IsLinkedSkillNameKey([string]$key){
    if($key-notmatch'^content\.(6|8|33)\.'){return $false}
    if(-not$script:EntryEnglish -or -not$script:EntryEnglish.ContainsKey($key) -or -not$script:SkillTitleValues){return $false}
    $source=([string]$script:EntryEnglish[$key]).Trim()
    return ($source -and $script:SkillTitleValues.Contains($source))
}

function Test-IsLinkedItemNameKey([string]$key){
    if($key-notmatch'^content\.(6|8)\.'){return $false}
    if(-not$script:EntryEnglish -or -not$script:EntryEnglish.ContainsKey($key) -or -not$script:ItemTitleValues){return $false}
    $source=([string]$script:EntryEnglish[$key]).Trim()
    return ($source -and $script:ItemTitleValues.Contains($source))
}

function Test-IsIntrinsicProtectedNameKey([string]$key){
    # Bütün büyü/yetenek başlıkları özgün İngilizce adıyla gösterilir.
    if($key-match'^content\.3\.'){return $true}
    # Bütün eşya adları özgün İngilizce kalır; yalnız tür, özellik ve
    # açıklamalar Türkçeleştirilir.
    if($key-match'^content\.15\.' -and -not(Test-IsTranslatableInventoryUiKey $key)){return $true}
    # Savaş içi durum adları da özgün kalır; yalnız sınıf tanıtımındaki
    # Gameplay sekmeleri Türkçeleştirilir.
    if($key-match'^content\.8\.' -and -not(Test-IsTranslatableCombatStateKey $key)){return $true}
    if($key-eq'content.6.1049'){return $true}
    # Açıklamalarda altı çizili/bağlantılı gösterilen ve gerçek bir content.3
    # büyü başlığıyla birebir eşleşen etki/durum adları da aynı adı kullanır.
    if(Test-IsLinkedSkillNameKey $key){return $true}
    if(Test-IsLinkedItemNameKey $key){return $true}
    if($key-in@(
        'content.6.1851','content.6.1852','content.6.1853','content.6.1854','content.6.2135',
        'content.8.1555','content.8.1964','content.8.1965','content.8.3425','content.8.3430',
        'content.8.3431','content.8.3442','content.8.4092','content.8.5449','content.8.7526',
        'content.8.7757','content.8.7792','content.8.8306',
        'content.33.178524','content.33.393883','content.33.394159'
    )){return $true}
    # Çanta/kese/kutu/sepet, anahtar/içecek ve kitap/günlük/not/tarif adları genel eşya
    # başlıklarıdır. İçlerindeki gerçek Wakfu özel adı korunabilir.
    if($key-match'^content\.15\.'-and$script:EntryEnglish-and$script:EntryEnglish.ContainsKey($key)){
        $containerSource=[string]$script:EntryEnglish[$key]
        if($containerSource-match'(?i)\b(?:Bag|Pouch|Box|Basket|Book|Books|Treatise|Diary|Note|Notes|Manual|Journal|Recipe|Recipes|Stories|Encyclopedia|Tome|Chronicle|Almanac|Catalog|Key|Juice)\b'){return $false}
    }
    if($key-in@(
        'content.15.0',
        'content.15.2175',
        'content.15.2603',
        'content.15.11955',
        'content.15.15865',
        'content.15.18629',
        'content.15.19799',
        'content.15.31167',
        'content.15.15994',
        'content.15.24202',
        'content.15.24877',
        'content.15.29614',
        'content.3.4202',
        'content.3.4401',
        'content.3.4422',
        'content.3.4570',
        'content.3.6575',
        'content.3.7348',
        'content.3.7581',
        'content.3.8558',
        'content.38.5',
        'content.38.518',
        'content.61.517',
        'content.78.336',
        'content.78.354',
        'content.78.368',
        'content.78.379',
        'content.3.4054',
        'content.3.4388',
        'content.3.4416',
        'content.3.4420',
        'content.3.4562',
        'content.3.4793',
        'content.3.5186',
        'content.3.6576',
        'content.3.7579',
        'content.15.10483',
        'content.15.14315',
        'content.15.19748',
        'content.15.28804',
        'content.15.28805',
        'content.15.28902',
        'content.15.28903',
        'content.15.28904',
        'content.15.28905',
        'content.15.32838',
        'content.3.636',
        'content.3.645',
        'content.3.1415',
        'content.3.3540',
        'content.3.8555',
        'content.7.5062',
        'content.7.4037',
        'content.7.4038',
        'content.15.18580',
        'content.15.18096',
        'content.15.31719',
        'content.15.31720',
        'content.15.31721'
    )){return $false}
    if($key-in@(
        'content.6.789',
        'content.8.923',
        'content.8.8743',
        'content.8.9048'
    )){return $true}
    # content.33/34/35/62 mekanik, unvan ve görev başlığıdır; özel ad değildir.
    return ($key-match'^content\.(3|7|12|15|20|38|48|54|77|78|82|89|130|159)\.' -or $key-match'^breed\.\d+$' -or $key-match'\.boussole\.' -or $key-match'^boussole\.' -or $key-match'^worldName\.' -or $key-match'^desc\.mru\.activate\.[^.]+\.[^.]+$' -or $key-match'(?i)^(item|monster|mob|npc|spell|skill|pet|mount)\..*\.name$')
}

function Test-IsTranslatableCombatStateKey([string]$key){
    return ($key-in@(
        'content.8.1263','content.8.2718','content.8.4048','content.8.4260',
        'content.8.5817','content.8.5865','content.8.7386',
        'content.8.748','content.8.5355','content.8.1915','content.8.1916'
    ))
}

function Test-IsTranslatableInventoryUiKey([string]$key){
    return ($key-in@(
        'content.15.2175','content.15.11955','content.15.15865','content.15.19799',
        'content.15.24267','content.15.27097','content.15.27098','content.15.27099',
        'content.15.27110','content.15.29612','content.15.31167'
    ))
}

function Test-IsForcedEnglishNameKey([string]$key){
    # Büyü/yetenek, savaş içi durum, eşya, canavar, NPC ve karakter adları
    # İngilizce kilitlenir. Gameplay sınıf tanıtım sekmesi arayüz istisnasıdır.
    if([string]::IsNullOrWhiteSpace($key)){return $false}
    if($key-match'^content\.3\.'){return $true}
    if($key-match'^content\.15\.' -and -not(Test-IsTranslatableInventoryUiKey $key)){return $true}
    if($key-match'^content\.8\.' -and -not(Test-IsTranslatableCombatStateKey $key)){return $true}
    if($key-eq'content.6.1049'){return $true}
    if(Test-IsLinkedSkillNameKey $key){return $true}
    if(Test-IsLinkedItemNameKey $key){return $true}
    if($key-in@(
        'content.6.1851','content.6.1852','content.6.1853','content.6.1854','content.6.2135',
        'content.8.1555','content.8.1964','content.8.1965','content.8.3425','content.8.3430',
        'content.8.3431','content.8.3442','content.8.4092','content.8.5449','content.8.7526',
        'content.8.7757','content.8.7792','content.8.8306',
        'content.33.178524','content.33.393883','content.33.394159'
    )){return $true}
    if($key-in@(
        'content.38.5',
        'content.38.518',
        'content.78.336',
        'content.78.354',
        'content.78.368',
        'content.78.379',
        'content.3.4054',
        'content.3.4388',
        'content.3.4416',
        'content.3.4420',
        'content.3.4562',
        'content.3.4793',
        'content.3.5186',
        'content.3.6576',
        'content.3.7579',
        'content.15.10483',
        'content.15.14315',
        'content.15.19748',
        'content.15.28804',
        'content.15.28805',
        'content.15.28902',
        'content.15.28903',
        'content.15.28904',
        'content.15.28905',
        'content.15.32838',
        'content.7.5062',
        'content.7.4037',
        'content.7.4038'
    )){return $false}
    return ($key-match'^content\.(7|38|48|130|159)\.' -or $key-match'^breed\.\d+$' -or $key-match'\.boussole\.' -or $key-match'^boussole\.' -or $key-match'^worldName\.' -or $key-match'(?i)^(monster|mob|npc)\..*\.name$')
}

function Apply-TurkishEditorState([bool]$locked){
    if($null-eq$turkish){return}
    $turkish.ReadOnly=$locked
    $turkish.TabStop=-not$locked
    $turkish.ShortcutsEnabled=$true
    $dark=[bool]$script:DarkThemeEnabled
    if($locked){
        $turkish.BackColor=if($dark){[Drawing.Color]::FromArgb(38,40,44)}else{[Drawing.SystemColors]::Control}
        $turkish.ForeColor=if($dark){[Drawing.Color]::FromArgb(170,176,184)}else{[Drawing.SystemColors]::GrayText}
        $turkish.Cursor='No'
        if($null-ne$l2){$l2.Text='Türkçe çeviri (özel ad — kilitli)'}
        if($null-ne$btnSaveRow){$btnSaveRow.Enabled=$false}
    }else{
        $turkish.BackColor=if($dark){[Drawing.Color]::FromArgb(44,48,56)}else{[Drawing.SystemColors]::Window}
        $turkish.ForeColor=if($dark){[Drawing.Color]::FromArgb(232,235,240)}else{[Drawing.SystemColors]::WindowText}
        $turkish.Cursor='IBeam'
        if($null-ne$l2){$l2.Text='Türkçe çeviri'}
        if($null-ne$btnSaveRow){$btnSaveRow.Enabled=$true}
    }
}

function Test-IsWorldTermOverrideKey([string]$key){
    # content.35 dünya haritasındaki banka, hapishane, pazar yeri gibi
    # etkileşim noktalarını içerir. Aynı İngilizce sözcük korunan bir NPC,
    # eşya veya yetenek adında da geçse bile doğrulanmış yer terimi haritada
    # Türkçe kalmalıdır.
    return ($key-match'^content\.(35|54|59|66|77|78|79|81|82|83|88|89|93|96|106|122|124|126|137|140|151|155|158|161)\.')
}

function Test-IsProtectedNameKey([string]$key){
    # Yetenek, savaş içi durum ve eşya başlıkları hiçbir manuel/terim istisnası
    # olmadan özgün İngilizceye kilitlenir. Gameplay sekmeleri çevrilebilir.
    if($key-match'^content\.3\.'){return $true}
    if($key-match'^content\.15\.' -and -not(Test-IsTranslatableInventoryUiKey $key)){return $true}
    if($key-match'^content\.8\.' -and -not(Test-IsTranslatableCombatStateKey $key)){return $true}
    if($key-eq'content.6.1049'){return $true}
    if(Test-IsLinkedSkillNameKey $key){return $true}
    if(Test-IsLinkedItemNameKey $key){return $true}
    if($key-in@(
        'content.6.1851','content.6.1852','content.6.1853','content.6.1854','content.6.2135',
        'content.8.1555','content.8.1964','content.8.1965','content.8.3425','content.8.3430',
        'content.8.3431','content.8.3442','content.8.4092','content.8.5449','content.8.7526',
        'content.8.7757','content.8.7792','content.8.8306',
        'content.33.178524','content.33.393883','content.33.394159'
    )){return $true}
    if($key-match'^content\.13\.' -and $script:EntryEnglish -and $script:EntryEnglish.ContainsKey($key)){
        $source=[string]$script:EntryEnglish[$key]
        if($source-match'^\s*\[se\](?:\s|$)' -or $source-match'^\s*-?\s*\[#\d+\]\s+(?:AP|WP|MP)(?:\s+\(.+\))?\s*$'){return $true}
    }
    if($script:TermKeys -and $script:TermKeys.ContainsKey($key)){return $false}
    if($key-in@(
        'content.15.2175',
        'content.15.2603',
        'content.15.11955',
        'content.15.15865',
        'content.15.18629',
        'content.15.19799',
        'content.15.31167',
        'content.15.15994',
        'content.15.24202',
        'content.15.24877',
        'content.15.29614',
        'content.3.4202',
        'content.3.4401',
        'content.3.4422',
        'content.3.4570',
        'content.3.6575',
        'content.3.7348',
        'content.3.7581',
        'content.3.8558',
        'content.38.5',
        'content.38.518',
        'content.61.517',
        'content.78.336',
        'content.78.354',
        'content.78.368',
        'content.78.379'
    )){return $false}
    if(Test-IsIntrinsicProtectedNameKey $key){return $true}
    if($script:EntryEnglish -and $script:EntryEnglish.ContainsKey($key) -and $script:ProtectedNameValues){
        $source=([string]$script:EntryEnglish[$key]).Trim()
        # Kaynak değeri için doğrulanmış genel bir Türkçe terim varsa bu
        # anahtar arayüz/metin anahtarıdır. Gerçek eşya, büyü, NPC ve yaratık
        # adları yukarıdaki intrinsic kuralla zaten korunmuştur.
        if($source -and $script:TermValues -and $script:TermValues.ContainsKey($source)){
            if(Test-IsWorldTermOverrideKey $key){return $false}
        }
        if($source -and $script:ProtectedNameValues.Contains($source)){
            $entry=[pscustomobject]@{Key=$key}
            $cat=Get-WakfuTextCategory $entry
            # Aynı İngilizce metin bir eşya/canavar adında geçse bile arayüz,
            # görev, buff ve açıklama satırlarını kilitleme.
            if($cat-in@('ARAYUZ','GENEL_OYUN_METNI','MEKANIK_BUFF_ACIKLAMA','GOREV_HEDEF','DIYALOG_HIKAYE','REHBER_EGITIM','ESYA_ACIKLAMA','PAZAR_TICARET','TEKNIK_ETKI_KALIBI','WAKFU_OZEL_ADI','BASARIM_KATEGORISI','BASARIM_ADI')){
                return $false
            }
            return $true
        }
    }
    return $false
}

function Get-WakfuTextCategory($entry){
    $key=[string]$entry.Key
    if($key-match'^content\.3\.'){return 'YETENEK_ADI'}
    if($key-match'^content\.6\.'){return 'YETENEK_ETKI_ADI'}
    if($key-match'^content\.7\.'){return 'YARATIK_ADI'}
    if($key-match'^content\.8\.'){return 'BUFF_DURUM_ADI'}
    if($key-match'^content\.12\.'){return 'KAYNAK_ADI'}
    if($key-match'^content\.15\.'){return 'ESYA_KAYNAK_ADI'}
    if($key-match'^content\.20\.'){return 'ESYA_SETI_ADI'}
    if($key-match'^content\.38\.'){return 'YARATIK_AILESI_ADI'}
    if($key-match'^content\.61\.'){return 'BASARIM_KATEGORISI'}
    if($key-match'^content\.62\.'){return 'BASARIM_ADI'}
    if($key-match'^content\.(34|54|77|78|89)\.'){return 'WAKFU_OZEL_ADI'}
    if($key-match'^content\.82\.'){return 'ULASIM_OZEL_ADI'}
    if($key-match'^content\.(48|159)\.' -or$key-match'\.boussole\.'){return 'NPC_ADI'}
    if($key-match'^content\.130\.'){return 'KARAKTER_ADI'}
    if($key-match'^breed\.\d+$'){return 'SINIF_ADI'}
    if($key-match'^breed\.role\.name\.'){return 'SINIF_ROLU'}
    if($key-match'^breed\.role\.desc\.'){return 'SINIF_ROL_ACIKLAMASI'}
    if($key-match'^breed\.'){return 'KARAKTER_OLUSTURMA'}
    if($key-match'^content\.157\.'){return 'OZEL_MEKAN_ADI'}
    if($key-match'^content\.16\.'){return 'ESYA_ACIKLAMA'}
    if($key-match'^content\.33\.'){return 'TEKNIK_ETKI_KALIBI'}
    if($key-match'^content\.35\.'){return 'NPC_ETKILESIM_MEKAN_ADI'}
    if($key-match'^content\.(4|9|10|13|30|146)\.'){return 'MEKANIK_BUFF_ACIKLAMA'}
    if($key-match'^content\.(55|87|101|102)\.'){return 'PAZAR_TICARET'}
    if($key-match'^content\.(64|76)\.'){return 'GOREV_HEDEF'}
    if($key-match'^content\.(47|49|63|75)\.'){return 'DIYALOG_HIKAYE'}
    if($key-match'^content\.(65|67|156)\.'){return 'REHBER_EGITIM'}
    if($key-match'(?i)(market|auction|shop|trade|exchange|seller|purchase|sale)'){return 'PAZAR_TICARET'}
    if($key-match'^content\.64\.' -or$key-match'(?i)(quest|objective|mission|achievement)'){return 'GOREV_HEDEF'}
    if($key-match'^content\.63\.' -or$key-match'(?i)(dialog|speech|monologue|conversation|talk|chat|wabbit)'){return 'DIYALOG_HIKAYE'}
    if($key-match'^content\.(67|156)\.' -or$key-match'(?i)(tutorial|guide|help|tip)'){return 'REHBER_EGITIM'}
    if($key-match'(?i)(buff|effect|state|status|damage|mastery|resistance|armor|heal)'){return 'MEKANIK_BUFF_ACIKLAMA'}
    if($key-match'(?i)(item.*desc|description|tooltip|details)'){return 'ESYA_ACIKLAMA'}
    if($key-match'(?i)(ui|window|button|menu|option|inventory|character|build|interface|label|popup|panel)'){return 'ARAYUZ'}
    return 'GENEL_OYUN_METNI'
}

function Write-AppLog([string]$message,[string]$level='BILGI'){
    try{
        if((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length-gt100MB){Move-Item -LiteralPath $LogFile -Destination ($LogFile+'.onceki.txt') -Force}
        $line='[{0}] [{1}] {2}'-f(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$level,$message
        [IO.File]::AppendAllText($LogFile,$line+[Environment]::NewLine,(New-Object Text.UTF8Encoding($true)))
    }catch{}
}

function Initialize-LiveTranslationLog {
    try{
        if(-not(Test-Path -LiteralPath $LiveTsv)-or(Get-Item -LiteralPath $LiveTsv).Length-eq0){
            $header="Zaman`tYontem`tAnahtar`tKategori`tDurum`tIngilizce`tTurkce`tAciklama"
            [IO.File]::WriteAllText($LiveTsv,$header+[Environment]::NewLine,(New-Object Text.UTF8Encoding($true)))
        }
    }catch{Write-AppLog "Canlı çeviri günlüğü başlatılamadı: $($_.Exception.Message)" 'LOG-HATA'}
}

function Convert-ToLiveTsvLine([string]$key,[string]$source,[string]$translated,[string]$method,[string]$recordStatus,[string]$details=''){
    if($script:EntryEnglish.ContainsKey($key)){$source=[string]$script:EntryEnglish[$key]}
    $category=if($key-eq'__fallback__'){'ARAMA'}else{Get-WakfuTextCategory ([pscustomobject]@{Key=$key})}
    $fields=@((Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'),$method,$key,$category,$recordStatus,$source,$translated,$details)|ForEach-Object{Convert-ToTsvField ([string]$_)}
    return ($fields-join"`t")
}

function Write-LiveTranslationRecord([string]$key,[string]$source,[string]$translated,[string]$method,[string]$recordStatus,[string]$details=''){
    try{
        Initialize-LiveTranslationLog
        $line=Convert-ToLiveTsvLine $key $source $translated $method $recordStatus $details
        [IO.File]::AppendAllText($LiveTsv,$line+[Environment]::NewLine,(New-Object Text.UTF8Encoding($false)))
    }catch{Write-AppLog "Canlı çeviri kaydı yazılamadı | Anahtar=$key | $($_.Exception.Message)" 'LOG-HATA'}
}

function Write-TranslationLogSnapshot([string]$stage,[string]$details='',[bool]$includeAllRemaining=$false){
    try{
        $translated=0;$missing=0;$sameEnglish=0;$formatBroken=0;$namesExcluded=0
        $examples=New-Object Collections.Generic.List[string]
        foreach($entry in $script:Entries){
            $key=[string]$entry.Key;$source=[string]$entry.English
            $safeSource=($source-replace"`r",'\r'-replace"`n",'\n')
            $current=if($script:TermKeys.ContainsKey($key)-and-not$script:ManualRepairs.ContainsKey($key)){[string]$script:TermKeys[$key]}elseif((Test-IsWorldTermOverrideKey $key)-and$script:TermValues.ContainsKey($source)){[string]$script:TermValues[$source]}elseif($script:ManualRepairs.ContainsKey($key)){[string]$script:ManualRepairs[$key]}elseif($script:TermKeys.ContainsKey($key)){[string]$script:TermKeys[$key]}elseif($script:TermValues.ContainsKey($source)){[string]$script:TermValues[$source]}elseif($script:Translations.ContainsKey($key)){[string]$script:Translations[$key]}else{''}
            $safeCurrent=($current-replace"`r",'\r'-replace"`n",'\n')
            if(Test-IsProtectedNameKey $key){$namesExcluded++;if($includeAllRemaining -or $examples.Count-lt20){$examples.Add("$key | NEDEN=Zorunlu Wakfu ad koruması | EN=$safeSource | TR=$safeCurrent")};continue}
            if([string]::IsNullOrWhiteSpace($current)){$missing++;if($includeAllRemaining -or $examples.Count-lt20){$examples.Add("$key | NEDEN=Boş/sonuç yok | EN=$safeSource | TR=$safeCurrent")};continue}
            $value=[string]$script:Translations[$key]
            if($value.Trim()-ceq$source.Trim()){$sameEnglish++;if($includeAllRemaining -or $examples.Count-lt20){$examples.Add("$key | NEDEN=İngilizceyle aynı | EN=$safeSource | TR=$safeCurrent")};continue}
            if(-not(Test-FormatTokens $source $value)){$formatBroken++;if($includeAllRemaining -or $examples.Count-lt20){$examples.Add("$key | NEDEN=Biçim kodu uyuşmuyor | EN=$safeSource | TR=$safeCurrent")};continue}
            $translated++
        }
        $remaining=$missing+$sameEnglish+$formatBroken+$namesExcluded
        Write-AppLog "$stage | Toplam=$($script:Entries.Count) | Çevrilmiş=$translated | Çevrilmemiş=$remaining | Boş=$missing | İngilizceyleAynı=$sameEnglish | BiçimKodu=$formatBroken | İsimOlarakHariç=$namesExcluded | $details"
        foreach($example in $examples){Write-AppLog "Çevrilmeyen satır: $example" 'DETAY'}
    }catch{Write-AppLog "İstatistik oluşturulamadı: $($_.Exception.Message)" 'HATA'}
}

function Test-I18nJar([string]$path) {
    try { $z=[IO.Compression.ZipFile]::OpenRead($path); try { return ($null-ne$z.GetEntry('texts_en.properties')) } finally {$z.Dispose()} } catch { return $false }
}

function Test-IsEnglishI18nJar([string]$path) {
    try {
        $z=[IO.Compression.ZipFile]::OpenRead($path)
        try {
            $entry=$z.GetEntry('texts_en.properties');if(-not$entry){return $false}
            $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
            try { while(($line=$reader.ReadLine())-ne$null){if($line-eq'abilities=Characteristics'){return $true}} }
            finally {$reader.Dispose()}
        } finally {$z.Dispose()}
    } catch {}
    return $false
}

function Test-GuiJar([string]$path) {
    try { $z=[IO.Compression.ZipFile]::OpenRead($path); try { return ($null-ne$z.GetEntry('theme/fonts/asul.ttf')) } finally {$z.Dispose()} } catch { return $false }
}

function Test-ClientJar([string]$path) {
    try { $z=[IO.Compression.ZipFile]::OpenRead($path);try{return($null-ne$z.GetEntry('cOt.class'))}finally{$z.Dispose()} } catch{return $false}
}

function Test-PersistentNameOverheadJar([string]$path) {
    try {
        $fontProfile=Get-OverheadFontProfile
        $z=[IO.Compression.ZipFile]::OpenRead($path)
        try {
            $entry=$z.GetEntry('dde.class');if(-not$entry){return $false}
            $stream=$entry.Open();$memory=New-Object IO.MemoryStream
            try{
                $bytes=$null;$stream.CopyTo($memory);$bytes=$memory.ToArray()
                if(-not([WakfuFastSearch]::HasSafePersistentNameOverhead($bytes) -and [WakfuFastSearch]::HasOverheadFontProfile($bytes,[int]$fontProfile.Main,[int]$fontProfile.Title))){return $false}
            }finally{$memory.Dispose();$stream.Dispose()}
            $commandEntry=$z.GetEntry('com/ankamagames/wakfu/client/console/command/display/ShowNameAndHighlightElementsCommand.class');if(-not$commandEntry){return $false}
            $commandStream=$commandEntry.Open();$commandMemory=New-Object IO.MemoryStream
            try{$commandStream.CopyTo($commandMemory);return [WakfuFastSearch]::HasHoverCompatibleNameToggle($commandMemory.ToArray())}finally{$commandMemory.Dispose();$commandStream.Dispose()}
        } finally {$z.Dispose()}
    } catch{return $false}
}

function Test-ClientJvmVerification([string]$path) {
    $java=Join-Path $GameDir 'jre\bin\java.exe'
    if(-not(Test-Path -LiteralPath $java)){return $true}
    try {
        foreach($className in @('dde','com.ankamagames.wakfu.client.console.command.display.ShowNameAndHighlightElementsCommand')){
            $psi=New-Object Diagnostics.ProcessStartInfo
            $psi.FileName=$java
            $psi.Arguments='-Xverify:all -cp "'+([IO.Path]::GetFullPath($path))+';'+(Join-Path $GameDir 'lib\*')+'" '+$className
            $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
            $process=New-Object Diagnostics.Process;$process.StartInfo=$psi
            [void]$process.Start();$output=$process.StandardOutput.ReadToEnd()+"`n"+$process.StandardError.ReadToEnd();$process.WaitForExit();$process.Dispose()
            if($output-match'VerifyError'-or$output-notmatch'Main method not found in class'){return $false}
        }
        return $true
    } catch{return $false}
}

function Test-DataJar([string]$path) {
    try {
        $z=[IO.Compression.ZipFile]::OpenRead($path)
        try {
            $entry=$z.GetEntry('shortcuts.xml');if(-not$entry){return $false}
            $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
            try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
            return $text.Contains('id="showHideNameOverheadsCommand"')
        } finally {$z.Dispose()}
    } catch{return $false}
}

function Test-NameToggleShortcutJar([string]$path) {
    try {
        $z=[IO.Compression.ZipFile]::OpenRead($path)
        try {
            $entry=$z.GetEntry('shortcuts.xml');if(-not$entry){return $false}
            $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
            try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
            $expected='(?s)<shortcut\b(?=[^>]*\bid="showHideNameOverheadsCommand")(?=[^>]*\bkeyCode\s*=\s*"86")(?=[^>]*\bonKeyReleased\s*=\s*"false")[^>]*>'
            return [regex]::Matches($text,$expected,[Text.RegularExpressions.RegexOptions]::CultureInvariant).Count-eq1
        } finally {$z.Dispose()}
    } catch{return $false}
}

function Get-FileFingerprint([string]$path) {
    if(-not(Test-Path -LiteralPath $path)){return 'YOK'}
    $item=Get-Item -LiteralPath $path
    if($item.Length-le32MB){return "FULL:$((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash)"}
    $sampleSize=1MB
    $data=New-Object byte[] (8+($sampleSize*2))
    [Buffer]::BlockCopy([BitConverter]::GetBytes([int64]$item.Length),0,$data,0,8)
    $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{
        [void]$stream.Read($data,8,$sampleSize)
        [void]$stream.Seek([Math]::Max($sampleSize,$item.Length-$sampleSize),[IO.SeekOrigin]::Begin)
        [void]$stream.Read($data,8+$sampleSize,$sampleSize)
    }finally{$stream.Dispose()}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$hash=$sha.ComputeHash($data)}finally{$sha.Dispose()}
    return 'QUICK:'+(([BitConverter]::ToString($hash))-replace'-','')
}

function Get-TextFingerprint([string]$text) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$hash=$sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))}finally{$sha.Dispose()}
    return (([BitConverter]::ToString($hash))-replace'-','')
}

function Test-SameFileFast([string]$left,[string]$right) {
    if(-not(Test-Path -LiteralPath $left)-or-not(Test-Path -LiteralPath $right)){return $false}
    $a=Get-Item -LiteralPath $left;$b=Get-Item -LiteralPath $right
    if($a.Length-ne$b.Length){return $false}
    return (Get-FileFingerprint $left)-eq(Get-FileFingerprint $right)
}

$BuildCacheFile=Join-Path $SettingsDir 'paket_onbellegi.json'
function Read-BuildCache {
    if(Test-Path -LiteralPath $BuildCacheFile){try{return (Get-Content -LiteralPath $BuildCacheFile -Raw -Encoding UTF8|ConvertFrom-Json)}catch{}}
    return [pscustomobject]@{i18n='';gui='';client='';data=''}
}
function Save-BuildCache([string]$i18n,[string]$gui,[string]$client,[string]$data) {
    $cache=[ordered]@{version=$AppVersion;i18n=$i18n;gui=$gui;client=$client;data=$data;updated=(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')}
    [IO.File]::WriteAllText($BuildCacheFile,($cache|ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)))
}

function Read-InstallState {
    if(Test-Path -LiteralPath $InstallStateFile){try{return Get-Content -LiteralPath $InstallStateFile -Raw -Encoding UTF8|ConvertFrom-Json}catch{}}
    return $null
}
function Test-RecordedPatchedFile([string]$key,[string]$path) {
    if(-not(Test-Path -LiteralPath $path)){return $false};$state=Read-InstallState;if($null-eq$state -or $null-eq$state.patched){return $false}
    if($state.gameDir -and ([IO.Path]::GetFullPath([string]$state.gameDir).TrimEnd('\')-ne[IO.Path]::GetFullPath($GameDir).TrimEnd('\'))){return $false}
    $expected=[string]$state.patched.$key;if(-not$expected){return $false}
    return ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash-eq$expected)
}
function Write-InstallState {
    $stateDir=Split-Path -Parent $InstallStateFile;New-Item -ItemType Directory -Path $stateDir -Force|Out-Null
    $official=[ordered]@{}
    foreach($pair in @(@('i18n_en',$OriginalEnglishJar),@('i18n',(Join-Path $BackupDir 'i18n.jar')),@('gui',$OriginalGuiJar),@('client',$OriginalClientJar),@('data',$OriginalDataJar))){if(Test-Path -LiteralPath $pair[1]){$official[$pair[0]]=(Get-FileHash -LiteralPath $pair[1] -Algorithm SHA256).Hash}}
    $patched=[ordered]@{}
    foreach($pair in @(@('i18n_en',$InstalledEnglishJar),@('i18n',(Join-Path $GameDir 'contents\i18n\i18n.jar')),@('gui',$InstalledGuiJar),@('client',$InstalledClientJar),@('data',$InstalledDataJar))){if(Test-Path -LiteralPath $pair[1]){$patched[$pair[0]]=(Get-FileHash -LiteralPath $pair[1] -Algorithm SHA256).Hash}}
    $record=[ordered]@{version=$AppVersion;gameDir=[IO.Path]::GetFullPath($GameDir);installedAt=(Get-Date -Format 'yyyy-MM-dd HH:mm:ss');overheadTextScaleProfile=[string](Get-OverheadFontProfile).Key;official=$official;patched=$patched}
    $temp=$InstallStateFile+'.'+[Guid]::NewGuid().ToString('N')+'.tmp';[IO.File]::WriteAllText($temp,($record|ConvertTo-Json -Depth 5 -Compress),(New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temp -Destination $InstallStateFile -Force
}
function Archive-OfficialBackup {
    if(-not(Test-Path -LiteralPath $BackupDir)){return}
    $files=@(Get-ChildItem -LiteralPath $BackupDir -File -ErrorAction SilentlyContinue);if($files.Count-eq0){return}
    $archive=Join-Path (Split-Path -Parent $BackupDir) ('Arsiv\'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'_'+[Guid]::NewGuid().ToString('N').Substring(0,6))
    New-Item -ItemType Directory -Path $archive -Force|Out-Null;foreach($file in $files){Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $archive $file.Name) -Force}
}

function Sync-GameUpdates {
    New-Item -ItemType Directory -Path $CurrentSourceDir -Force | Out-Null
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    $changes=New-Object Collections.Generic.List[string]
    $backupArchived=$false
    if(Test-Path -LiteralPath $InstalledEnglishJar){
        $installedHash=Get-FileFingerprint $InstalledEnglishJar
        $outputHash=Get-FileFingerprint $OutputJar
        $currentHash=Get-FileFingerprint $CurrentEnglishJar
        if($installedHash-ne$outputHash -and $installedHash-ne$currentHash -and -not(Test-RecordedPatchedFile 'i18n_en' $InstalledEnglishJar) -and (Test-IsEnglishI18nJar $InstalledEnglishJar)){
            if(-not(Test-I18nJar $InstalledEnglishJar)){throw 'Güncellenen i18n_en.jar doğrulanamadı.'}
            if(-not$backupArchived){Archive-OfficialBackup;$backupArchived=$true}
            Copy-Item -LiteralPath $InstalledEnglishJar -Destination $CurrentEnglishJar -Force
            Copy-Item -LiteralPath $InstalledEnglishJar -Destination $OriginalEnglishJar -Force
            $installedActive=Join-Path $GameDir 'contents\i18n\i18n.jar';if(Test-Path -LiteralPath $installedActive){Copy-Item -LiteralPath $installedActive -Destination (Join-Path $BackupDir 'i18n.jar') -Force}
            [void]$changes.Add('Yeni i18n_en.jar kaynak olarak alındı.')
        }
    }
    # Kurulu Türkçe yama hiçbir zaman İngilizce kaynak olarak kullanılmamalı.
    # Güncel kaynak yalnız gerçekten İngilizceyse seçilir; aksi halde temiz
    # orijinal yedek kullanılır.
    if((Test-Path -LiteralPath $CurrentEnglishJar) -and (Test-IsEnglishI18nJar $CurrentEnglishJar)){$script:SourceJar=$CurrentEnglishJar}
    elseif(Test-Path -LiteralPath $OriginalEnglishJar){$script:SourceJar=$OriginalEnglishJar}
    else{$script:SourceJar=$PackagedBaseEnglishJar}
    if(Test-Path -LiteralPath $InstalledGuiJar){
        $installedGuiHash=Get-FileFingerprint $InstalledGuiJar
        $outputGuiHash=Get-FileFingerprint $OutputGuiJar
        $currentGuiHash=Get-FileFingerprint $CurrentGuiJar
        if($installedGuiHash-ne$outputGuiHash -and $installedGuiHash-ne$currentGuiHash -and -not(Test-RecordedPatchedFile 'gui' $InstalledGuiJar)){
            if(-not(Test-GuiJar $InstalledGuiJar)){throw 'Güncellenen gui.jar doğrulanamadı.'}
            if(-not$backupArchived){Archive-OfficialBackup;$backupArchived=$true}
            Copy-Item -LiteralPath $InstalledGuiJar -Destination $CurrentGuiJar -Force
            Copy-Item -LiteralPath $InstalledGuiJar -Destination $OriginalGuiJar -Force
            [void]$changes.Add('Yeni gui.jar font yaması için kaynak olarak alındı.')
        }
    }
    if(Test-Path -LiteralPath $InstalledClientJar){
        $installedClientHash=Get-FileFingerprint $InstalledClientJar
        $outputClientHash=Get-FileFingerprint $OutputClientJar
        $currentClientHash=Get-FileFingerprint $CurrentClientJar
        if($installedClientHash-ne$outputClientHash -and $installedClientHash-ne$currentClientHash -and -not(Test-RecordedPatchedFile 'client' $InstalledClientJar)){
            if(-not(Test-ClientJar $InstalledClientJar)){throw 'Güncellenen wakfu-client.jar doğrulanamadı.'}
            if(-not$backupArchived){Archive-OfficialBackup;$backupArchived=$true}
            Copy-Item -LiteralPath $InstalledClientJar -Destination $CurrentClientJar -Force
            Copy-Item -LiteralPath $InstalledClientJar -Destination $OriginalClientJar -Force
            [void]$changes.Add('Yeni wakfu-client.jar arayüz düzeltmesi için kaynak olarak alındı.')
        }
    }
    if(Test-Path -LiteralPath $InstalledDataJar){
        $installedDataHash=Get-FileFingerprint $InstalledDataJar
        $outputDataHash=Get-FileFingerprint $OutputDataJar
        $currentDataHash=Get-FileFingerprint $CurrentDataJar
        if($installedDataHash-ne$outputDataHash -and $installedDataHash-ne$currentDataHash -and -not(Test-RecordedPatchedFile 'data' $InstalledDataJar)){
            if(-not(Test-DataJar $InstalledDataJar)){throw 'Güncellenen data.jar doğrulanamadı.'}
            if(-not$backupArchived){Archive-OfficialBackup;$backupArchived=$true}
            Copy-Item -LiteralPath $InstalledDataJar -Destination $CurrentDataJar -Force
            Copy-Item -LiteralPath $InstalledDataJar -Destination $OriginalDataJar -Force
            [void]$changes.Add('Yeni data.jar V oyuncu adı görünürlüğü düzeltmesi için kaynak olarak alındı.')
        }
    }
    return @($changes)
}

function Build-ClientPatch {
    $clientSource=if(Test-Path -LiteralPath $CurrentClientJar){$CurrentClientJar}elseif(Test-Path -LiteralPath $OriginalClientJar){$OriginalClientJar}else{$InstalledClientJar}
    if(-not(Test-ClientJar $clientSource)){throw 'Karakter seçim ekranı için geçerli wakfu-client.jar bulunamadı.'}
    Copy-Item -LiteralPath $clientSource -Destination $OutputClientJar -Force
    $zip=[IO.Compression.ZipFile]::Open($OutputClientJar,[IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry=$zip.GetEntry('cOt.class');if(-not$entry){throw 'cOt.class bulunamadı.'}
        $stream=$entry.Open();$memory=New-Object IO.MemoryStream
        try{$stream.CopyTo($memory);$bytes=$memory.ToArray()}finally{$memory.Dispose();$stream.Dispose()}
        $old=[Text.Encoding]::UTF8.GetBytes('%selection% %yourCharacter%')
        $new=[Text.Encoding]::UTF8.GetBytes('Karakterini Seç')
        $index=-1
        for($i=2;$i-le$bytes.Length-$old.Length;$i++){
            $same=$true;for($j=0;$j-lt$old.Length;$j++){if($bytes[$i+$j]-ne$old[$j]){$same=$false;break}}
            if($same -and (($bytes[$i-2]-shl8)-bor$bytes[$i-1])-eq$old.Length){$index=$i;break}
        }
        if($index-lt0){
            $already=[Text.Encoding]::UTF8.GetBytes('Karakterini Seç')
            $foundAlready=$false
            for($i=2;$i-le$bytes.Length-$already.Length;$i++){if((($bytes[$i-2]-shl8)-bor$bytes[$i-1])-ne$already.Length){continue};$same=$true;for($j=0;$j-lt$already.Length;$j++){if($bytes[$i+$j]-ne$already[$j]){$same=$false;break}};if($same){$foundAlready=$true;break}}
            if(-not$foundAlready){throw 'Karakter seçimi başlık kalıbı bu oyun sürümünde bulunamadı.'}
        } else {
            $patched=New-Object byte[] ($bytes.Length-$old.Length+$new.Length)
            [Buffer]::BlockCopy($bytes,0,$patched,0,$index-2)
            $patched[$index-2]=[byte]($new.Length-shr8);$patched[$index-1]=[byte]($new.Length-band255)
            [Buffer]::BlockCopy($new,0,$patched,$index,$new.Length)
            [Buffer]::BlockCopy($bytes,$index+$old.Length,$patched,$index+$new.Length,$bytes.Length-($index+$old.Length))
            $entry.Delete();$replacement=$zip.CreateEntry('cOt.class',[IO.Compression.CompressionLevel]::Optimal);$out=$replacement.Open()
            try{$out.Write($patched,0,$patched.Length)}finally{$out.Dispose()}
        }
        $weatherEntry=$zip.GetEntry('bSn.class');if(-not$weatherEntry){throw 'Hava durumu saat biçimi sınıfı bulunamadı.'}
        $weatherStream=$weatherEntry.Open();$weatherMemory=New-Object IO.MemoryStream
        try{$weatherStream.CopyTo($weatherMemory);$weatherBytes=$weatherMemory.ToArray()}finally{$weatherMemory.Dispose();$weatherStream.Dispose()}
        $patchedWeather=[WakfuFastSearch]::PatchWeatherTime($weatherBytes)
        if($patchedWeather.Length-ne$weatherBytes.Length){
            $weatherEntry.Delete();$weatherReplacement=$zip.CreateEntry('bSn.class',[IO.Compression.CompressionLevel]::Optimal);$weatherOut=$weatherReplacement.Open()
            try{$weatherOut.Write($patchedWeather,0,$patchedWeather.Length)}finally{$weatherOut.Dispose()}
        }
        $battlegroundEntry=$zip.GetEntry('bhw.class');if(-not$battlegroundEntry){throw 'Savaş alanı tarih-saat biçimi sınıfı bulunamadı.'}
        $battlegroundStream=$battlegroundEntry.Open();$battlegroundMemory=New-Object IO.MemoryStream
        try{$battlegroundStream.CopyTo($battlegroundMemory);$battlegroundBytes=$battlegroundMemory.ToArray()}finally{$battlegroundMemory.Dispose();$battlegroundStream.Dispose()}
        $patchedBattleground=[WakfuFastSearch]::PatchBattlegroundTime($battlegroundBytes)
        if($patchedBattleground.Length-ne$battlegroundBytes.Length){
            $battlegroundEntry.Delete();$battlegroundReplacement=$zip.CreateEntry('bhw.class',[IO.Compression.CompressionLevel]::Optimal);$battlegroundOut=$battlegroundReplacement.Open()
            try{$battlegroundOut.Write($patchedBattleground,0,$patchedBattleground.Length)}finally{$battlegroundOut.Dispose()}
        }
        $achievementEntry=$zip.GetEntry('cQS.class');if(-not$achievementEntry){throw 'Başarım kök etiketi sınıfı bulunamadı.'}
        $achievementStream=$achievementEntry.Open();$achievementMemory=New-Object IO.MemoryStream
        try{$achievementStream.CopyTo($achievementMemory);$achievementBytes=$achievementMemory.ToArray()}finally{$achievementMemory.Dispose();$achievementStream.Dispose()}
        $patchedAchievement=[WakfuFastSearch]::ReplaceUtf8($achievementBytes,'Total','Toplam')
        if($patchedAchievement.Length-ne$achievementBytes.Length){
            $achievementEntry.Delete();$achievementReplacement=$zip.CreateEntry('cQS.class',[IO.Compression.CompressionLevel]::Optimal);$achievementOut=$achievementReplacement.Open()
            try{$achievementOut.Write($patchedAchievement,0,$patchedAchievement.Length)}finally{$achievementOut.Dispose()}
        }
        $nameEntry=$zip.GetEntry('dde.class');if(-not$nameEntry){throw 'Oyuncu adı yaşam döngüsü sınıfı bulunamadı.'}
        $nameStream=$nameEntry.Open();$nameMemory=New-Object IO.MemoryStream
        try{$nameStream.CopyTo($nameMemory);$nameBytes=$nameMemory.ToArray()}finally{$nameMemory.Dispose();$nameStream.Dispose()}
        $fontProfile=Get-OverheadFontProfile
        $patchedName=[WakfuFastSearch]::PatchPersistentNameOverhead($nameBytes)
        $patchedName=[WakfuFastSearch]::PatchOverheadFontProfile($patchedName,[int]$fontProfile.Main,[int]$fontProfile.Title)
        if(-not[Object]::ReferenceEquals($patchedName,$nameBytes)){
            $nameEntry.Delete();$nameReplacement=$zip.CreateEntry('dde.class',[IO.Compression.CompressionLevel]::Optimal);$nameOut=$nameReplacement.Open()
            try{$nameOut.Write($patchedName,0,$patchedName.Length)}finally{$nameOut.Dispose()}
        }
        $commandName='com/ankamagames/wakfu/client/console/command/display/ShowNameAndHighlightElementsCommand.class'
        $commandEntry=$zip.GetEntry($commandName);if(-not$commandEntry){throw 'V aç/kapat komutu bulunamadı.'}
        $commandStream=$commandEntry.Open();$commandMemory=New-Object IO.MemoryStream
        try{$commandStream.CopyTo($commandMemory);$commandBytes=$commandMemory.ToArray()}finally{$commandMemory.Dispose();$commandStream.Dispose()}
        $patchedCommand=[WakfuFastSearch]::PatchHoverCompatibleNameToggle($commandBytes)
        if(-not[Object]::ReferenceEquals($patchedCommand,$commandBytes)){
            $commandEntry.Delete();$commandReplacement=$zip.CreateEntry($commandName,[IO.Compression.CompressionLevel]::Optimal);$commandOut=$commandReplacement.Open()
            try{$commandOut.Write($patchedCommand,0,$patchedCommand.Length)}finally{$commandOut.Dispose()}
        }
        if(-not(Test-Path -LiteralPath $AlmanaxPatchClass)){throw 'Almanax açıklama yaması bulunamadı.'}
        $almanaxEntry=$zip.GetEntry('bgU.class');if(-not$almanaxEntry){throw 'bgU.class bulunamadı.'}
        $almanaxBytes=[IO.File]::ReadAllBytes($AlmanaxPatchClass)
        $almanaxEntry.Delete()
        $almanaxReplacement=$zip.CreateEntry('bgU.class',[IO.Compression.CompressionLevel]::Optimal)
        $almanaxOut=$almanaxReplacement.Open()
        try{$almanaxOut.Write($almanaxBytes,0,$almanaxBytes.Length)}finally{$almanaxOut.Dispose()}
    } finally{$zip.Dispose()}
    if(-not(Test-PersistentNameOverheadJar $OutputClientJar)){throw 'V oyuncu adı ve seçilen baş üstü yazı profili güvenlik doğrulamasından geçmedi.'}
    if(-not(Test-ClientJvmVerification $OutputClientJar)){throw 'V oyuncu adı sınıfı Java doğrulamasından geçmedi.'}
}

function Build-DataPatch {
    $dataSource=if(Test-Path -LiteralPath $CurrentDataJar){$CurrentDataJar}elseif(Test-Path -LiteralPath $OriginalDataJar){$OriginalDataJar}else{$InstalledDataJar}
    if(-not(Test-DataJar $dataSource)){throw 'V tuşunu geri yüklemek için geçerli data.jar bulunamadı.'}
    Copy-Item -LiteralPath $dataSource -Destination $OutputDataJar -Force
    $zip=[IO.Compression.ZipFile]::Open($OutputDataJar,[IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry=$zip.GetEntry('shortcuts.xml');if(-not$entry){throw 'shortcuts.xml bulunamadı.'}
        $reader=New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
        try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
        $pattern='(?s)(<shortcut\b(?=[^>]*\bid="showHideNameOverheadsCommand")[^>]*\bonKeyReleased\s*=\s*")true(")'
        $alreadyPattern='(?s)<shortcut\b(?=[^>]*\bid="showHideNameOverheadsCommand")(?=[^>]*\bkeyCode\s*=\s*"86")[^>]*\bonKeyReleased\s*=\s*"false"'
        $matches=[regex]::Matches($text,$pattern,[Text.RegularExpressions.RegexOptions]::CultureInvariant)
        if($matches.Count-gt1){throw 'V oyuncu adı kısayolu birden çok kez bulundu; güvenli geri yükleme yapılmadı.'}
        if($matches.Count-eq1){$restored=[regex]::Replace($text,$pattern,'${1}false${2}',[Text.RegularExpressions.RegexOptions]::CultureInvariant)}
        elseif([regex]::IsMatch($text,$alreadyPattern,[Text.RegularExpressions.RegexOptions]::CultureInvariant)){$restored=$text}
        else{throw 'V oyuncu adı kısayolunun tek basış davranışı bulunamadı.'}
        if($restored-ne$text){
            $entry.Delete();$replacement=$zip.CreateEntry('shortcuts.xml',[IO.Compression.CompressionLevel]::Optimal)
            $writer=New-Object IO.StreamWriter($replacement.Open(),(New-Object Text.UTF8Encoding($false)))
            try{$writer.Write($restored)}finally{$writer.Dispose()}
        }
    } finally{$zip.Dispose()}
    if(-not(Test-NameToggleShortcutJar $OutputDataJar)){throw 'V tuşunun basış başına tek aç/kapat davranışı doğrulanamadı.'}
}

function Build-GuiPatch {
    $guiSource=if(Test-Path -LiteralPath $CurrentGuiJar){$CurrentGuiJar}else{$OriginalGuiJar}
    if(-not(Test-Path -LiteralPath $guiSource) -or -not(Test-Path -LiteralPath $FontPatchDir)){return}
    Copy-Item -LiteralPath $guiSource -Destination $OutputGuiJar -Force
    $zip=[IO.Compression.ZipFile]::Open($OutputGuiJar,[IO.Compression.ZipArchiveMode]::Update)
    try {
        foreach($font in Get-ChildItem -LiteralPath $FontPatchDir -Filter '*.ttf'){
            $entryName='theme/fonts/'+$font.Name
            $old=$zip.GetEntry($entryName);if(-not$old){continue};$old.Delete()
            $new=$zip.CreateEntry($entryName,[IO.Compression.CompressionLevel]::Optimal)
            $sourceStream=[IO.File]::OpenRead($font.FullName);$destStream=$new.Open()
            try{$sourceStream.CopyTo($destStream)}finally{$destStream.Dispose();$sourceStream.Dispose()}
        }
    } finally {$zip.Dispose()}
}

function Read-PropertiesFromJar {
    if (-not (Test-Path -LiteralPath $SourceJar)) { throw "İngilizce dil paketi bulunamadı:`n$SourceJar" }
    $zip = [IO.Compression.ZipFile]::OpenRead($SourceJar)
    try {
        $entry = $zip.GetEntry('texts_en.properties')
        if (-not $entry) { throw 'texts_en.properties paket içinde bulunamadı.' }
        $reader = New-Object IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8, $true)
        try {
            $list = New-Object System.Collections.Generic.List[object]
            $searchKeyList=New-Object System.Collections.Generic.List[string]
            $searchEnglishList=New-Object System.Collections.Generic.List[string]
            while (($line = $reader.ReadLine()) -ne $null) {
                if ($line.Length -eq 0 -or $line[0] -in '#','!') { continue }
                $pos = $line.IndexOf('=')
                if ($pos -lt 1) { continue }
                $key = $line.Substring(0,$pos)
                $value = $line.Substring($pos+1)
                $list.Add([pscustomobject]@{ Key=$key; English=$value })
                $searchKeyList.Add($key)
                $searchEnglishList.Add($value)
            }
            $script:SearchKeys=$searchKeyList.ToArray()
            $script:SearchEnglish=$searchEnglishList.ToArray()
            return $list.ToArray()
        } finally { $reader.Dispose() }
    } finally { $zip.Dispose() }
}

function Load-Project {
    $script:Translations = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    if (Test-Path -LiteralPath $ProjectFile) {
        $serializer = New-Object Web.Script.Serialization.JavaScriptSerializer
        $serializer.MaxJsonLength = [int]::MaxValue
        $obj = $serializer.DeserializeObject((Get-Content -LiteralPath $ProjectFile -Raw -Encoding UTF8))
        foreach ($key in $obj.Keys) { $script:Translations[[string]$key] = [string]$obj[$key] }
    }
    $script:ProjectDirty=$false
}

function Update-TermPhraseMatcher {
    $script:SortedTermPhraseKeys=@($script:TermPhrases.Keys|Sort-Object Length -Descending)
    if($script:SortedTermPhraseKeys.Count-gt0){
        $alternatives=($script:SortedTermPhraseKeys|ForEach-Object{[regex]::Escape([string]$_)})-join'|'
        # “Tab” kuralının “Tablolar” sözcüğünü “Sekmelolar” yapması gibi
        # sözcük içi eşleşmeleri engelle. Kural yalnız bağımsız sözcük/ifade
        # sınırlarında çalışır.
        $pattern='(?<![\p{L}\p{N}_])(?:'+$alternatives+')(?![\p{L}\p{N}_])'
        $script:TermPhraseRegex=New-Object Text.RegularExpressions.Regex($pattern,[Text.RegularExpressions.RegexOptions]::CultureInvariant)
    }else{$script:TermPhraseRegex=$null}
}

function Apply-TermPhrases([string]$value) {
    if([string]::IsNullOrEmpty($value)){return $value}
    if($script:TermPhraseRegex){
        $value=$script:TermPhraseRegex.Replace($value,[Text.RegularExpressions.MatchEvaluator]{param($m)[string]$script:TermPhrases[$m.Value]})
    }
    return $value
}

function Load-Terminology {
    $script:TermKeys = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    $script:TermValues = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    $script:TermPhrases = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    if (-not (Test-Path -LiteralPath $TerminologyFile)) { return }
    $serializer = New-Object Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    $obj = $serializer.DeserializeObject((Get-Content -LiteralPath $TerminologyFile -Raw -Encoding UTF8))
    if ($obj.ContainsKey('keys')) { foreach ($key in $obj['keys'].Keys) { $script:TermKeys[[string]$key] = [string]$obj['keys'][$key] } }
    if ($obj.ContainsKey('values')) { foreach ($key in $obj['values'].Keys) { $script:TermValues[[string]$key] = [string]$obj['values'][$key] } }
    if ($obj.ContainsKey('phrases')) { foreach ($key in $obj['phrases'].Keys) { $script:TermPhrases[[string]$key] = [string]$obj['phrases'][$key] } }
    # Sürümle gelen doğrulanmış düzeltmeler, eski kullanıcı sözlüğü korunsa
    # bile her zaman uygulanır.
    $script:TermKeys['brumes.golem.activation']='Tuhaf pota dolu görünüyor. Golem canlanmış gibi.'
    $script:TermKeys['booster.pack']='Güçlendirici'
    $script:TermKeys['achievement.reward.booster']='Ek Güçlendirici Ödülleri'
    $script:TermKeys['achievement.reward.no.booster']='Güçlendiriciler sayesinde daha fazla ödül kazanın'
    $script:TermKeys['booster.pack.active.duration']='Etkin Güçlendirici:'
    $script:TermKeys['booster.pack.benefit']='Güçlendirici Avantajı'
    $script:TermKeys['content.15.0']='Yok'
    $script:TermKeys['content.15.2175']='Cepler'
    $script:TermKeys['content.15.24267']='Deneyim'
    $script:TermKeys['content.15.27097']='Yakın Dövüş Ustalığı'
    $script:TermKeys['content.15.27098']='Menzil Ustalığı'
    $script:TermKeys['content.15.27099']='Berserk Ustalığı'
    $script:TermKeys['content.15.27110']='İyileştirme Ustalığı'
    $script:TermKeys['content.15.29612']='Ara'
    $script:TermKeys['min']='En az'
    $script:TermKeys['max']='En çok'
    $script:TermKeys['rerollXp.info.notRight']="İkincil karakterler için XP bonusu. Bu bonus, bir Güçlendirici ile x[#1.1]'ye yükseltilebilir."
    $script:TermKeys['breed.role.name.0']='Hareketlilik'
    $script:TermKeys['breed.role.name.1']='Konumlandırma'
    $script:TermKeys['breed.role.name.2']='İyileştirme'
    $script:TermKeys['breed.role.name.3']='Koruma'
    $script:TermKeys['breed.role.name.4']='Destek'
    $script:TermKeys['breed.role.name.5']='Hasar'
    $script:TermKeys['breed.role.name.6']='Hareket Engelleme'
    $script:TermKeys['breed.role.name.7']='Kontrol'
    $script:TermKeys['breed.role.name.8']='Destek'
    $script:TermValues['Booster']='Güçlendirici'
    $script:TermValues['Boosters']='Güçlendiriciler'
    # İnsan tarafından denetlenmiş düzeltmeler her yeniden çeviri ve oyun
    # güncellemesinde en yüksek öncelikle korunur.
    $script:ManualRepairs = New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    if(Test-Path -LiteralPath $ManualRepairsFile){
        try{
            $manual=$serializer.DeserializeObject((Get-Content -LiteralPath $ManualRepairsFile -Raw -Encoding UTF8))
            foreach($key in $manual.Keys){
                $script:ManualRepairs[[string]$key]=[string]$manual[$key]
                $script:TermKeys[[string]$key]=[string]$manual[$key]
            }
        }catch{Write-AppLog "Kesin düzeltmeler yüklenemedi: $($_.Exception.Message)"}
    }
    Update-TermPhraseMatcher
}

function Save-Terminology {
    Update-TermPhraseMatcher
    $keys=[ordered]@{};$values=[ordered]@{};$phrases=[ordered]@{}
    foreach($k in($script:TermKeys.Keys|Sort-Object)){$keys[$k]=$script:TermKeys[$k]}
    foreach($k in($script:TermValues.Keys|Sort-Object)){$values[$k]=$script:TermValues[$k]}
    foreach($k in($script:TermPhrases.Keys|Sort-Object)){$phrases[$k]=$script:TermPhrases[$k]}
    $obj=[ordered]@{keys=$keys;values=$values;phrases=$phrases}
    [IO.File]::WriteAllText($TerminologyFile,($obj|ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($true)))
}

function Initialize-FastSearchIndex {
    if($script:SearchKeys.Count-ne$script:Entries.Count){$script:SearchKeys=[string[]]@($script:Entries|ForEach-Object{[string]$_.Key})}
    if($script:SearchEnglish.Count-ne$script:Entries.Count){$script:SearchEnglish=[string[]]@($script:Entries|ForEach-Object{[string]$_.English})}
    $script:SearchTurkish=[WakfuFastSearch]::BuildTurkish($script:SearchKeys,$script:SearchEnglish,$script:Translations,$script:TermKeys,$script:TermValues)
}

function Save-ManualRepairs {
    if($null-eq$script:ManualRepairs){$script:ManualRepairs=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)}
    $serializer = New-Object Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    # Sıralama her kayıttaki gecikmeyi artırır; Dictionary doğrudan yazılır.
    $tempFile=$ManualRepairsFile+'.tmp'
    [IO.File]::WriteAllText($tempFile,$serializer.Serialize($script:ManualRepairs),(New-Object Text.UTF8Encoding($true)))
    if(Test-Path -LiteralPath $ManualRepairsFile){
        $replaceBackup=$ManualRepairsFile+'.replace.bak'
        if(Test-Path -LiteralPath $replaceBackup){[IO.File]::Delete($replaceBackup)}
        [IO.File]::Replace($tempFile,$ManualRepairsFile,$replaceBackup,$true)
        if(Test-Path -LiteralPath $replaceBackup){[IO.File]::Delete($replaceBackup)}
    }else{[IO.File]::Move($tempFile,$ManualRepairsFile)}
    $script:ManualDirty=$false
}

function Get-ChangedSpan([string]$old,[string]$new) {
    $prefix=0;$limit=[Math]::Min($old.Length,$new.Length)
    while($prefix-lt$limit -and $old[$prefix]-ceq$new[$prefix]){$prefix++}
    $suffix=0
    while($suffix-lt($old.Length-$prefix) -and $suffix-lt($new.Length-$prefix) -and $old[$old.Length-1-$suffix]-ceq$new[$new.Length-1-$suffix]){$suffix++}
    $oldPart=$old.Substring($prefix,$old.Length-$prefix-$suffix)
    $newPart=$new.Substring($prefix,$new.Length-$prefix-$suffix)
    return [pscustomobject]@{Old=$oldPart;New=$newPart}
}

function Get-LastVowel([string]$text){$m=[regex]::Match($text,'[aeıioöuü](?!.*[aeıioöuü])','IgnoreCase');if($m.Success){return $m.Value.ToLowerInvariant()};return 'a'}
function Add-TurkishCase([string]$word,[string]$case) {
    $v=Get-LastVowel $word;$front=$v-in@('e','i','ö','ü');$rounded=$v-in@('o','ö','u','ü');$endsVowel=$word-match'[aeıioöuü]$';$possessive=$word-match'(?i)(ları|leri)$'
    $a=if($front){'e'}else{'a'};$i=if($front){if($rounded){'ü'}else{'i'}}else{if($rounded){'u'}else{'ı'}}
    switch($case){
        'dat'{if($possessive){$suffix='n'+$a}elseif($endsVowel){$suffix='y'+$a}else{$suffix=$a};return $word+$suffix}
        'loc'{$d=if($word-match'(?i)[fstkçşhp]$'){'t'}else{'d'};if($possessive){$suffix='n'+$d+$a}else{$suffix=$d+$a};return $word+$suffix}
        'abl'{$d=if($word-match'(?i)[fstkçşhp]$'){'t'}else{'d'};if($possessive){$suffix='n'+$d+$a+'n'}else{$suffix=$d+$a+'n'};return $word+$suffix}
        'gen'{if($endsVowel){$suffix='n'+$i+'n'}else{$suffix=$i+'n'};return $word+$suffix}
        'acc'{if($possessive){$suffix='n'+$i}elseif($endsVowel){$suffix='y'+$i}else{$suffix=$i};return $word+$suffix}
        default{return $word}
    }
}

function Get-CaseName([string]$suffix){switch -Regex($suffix.ToLowerInvariant()){'^(a|e)$'{return 'dat'}'^(da|de|ta|te)$'{return 'loc'}'^(dan|den|tan|ten)$'{return 'abl'}'^(ın|in|un|ün)$'{return 'gen'}'^(ı|i|u|ü)$'{return 'acc'}default{return ''}}}
function Remove-TurkishCase([string]$text,[string]$case){$patterns=@{dat='(na|ne|ya|ye|a|e)$';loc='(nda|nde|da|de|ta|te)$';abl='(ndan|nden|dan|den|tan|ten)$';gen='(nın|nin|nun|nün|ın|in|un|ün)$';acc='(nı|ni|nu|nü|yı|yi|yu|yü|ı|i|u|ü)$'};if($patterns.ContainsKey($case)){return [regex]::Replace($text,$patterns[$case],'','IgnoreCase')};return $text}

function Get-InflectedRules([string]$oldPart,[string]$newPart){
    $rules=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    $m=[regex]::Match($oldPart,"^(.*?)(?:['’](a|e|da|de|ta|te|dan|den|tan|ten|ın|in|un|ün|ı|i|u|ü))$",'IgnoreCase')
    if($m.Success){$oldStem=$m.Groups[1].Value;$case=Get-CaseName $m.Groups[2].Value;$newStem=Remove-TurkishCase $newPart $case}else{$oldStem=$oldPart;$newStem=$newPart}
    $rules[$oldPart]=$newPart
    if($oldStem.Length-ge2 -and $newStem.Length-ge1){
        $rules[$oldStem]=$newStem
        foreach($pair in @(@('a','dat'),@('e','dat'),@('da','loc'),@('de','loc'),@('ta','loc'),@('te','loc'),@('dan','abl'),@('den','abl'),@('tan','abl'),@('ten','abl'),@('ın','gen'),@('in','gen'),@('un','gen'),@('ün','gen'),@('ı','acc'),@('i','acc'),@('u','acc'),@('ü','acc'))){$rules[$oldStem+"'"+$pair[0]]=Add-TurkishCase $newStem $pair[1]}
    }
    return $rules
}

function Offer-BulkManualCorrection([string]$oldValue,[string]$newValue,[string]$editedKey) {
    if([string]::IsNullOrWhiteSpace($oldValue)-or[string]::IsNullOrWhiteSpace($newValue)-or$oldValue-ceq$newValue){return}
    $change=Get-ChangedSpan $oldValue $newValue
    if($change.Old.Length-lt2 -or $change.New.Length-lt1 -or $change.Old-match '[\[\]{}<>%\\]' -or $change.New-match '[\[\]{}<>%\\]'){return}
    $rules=Get-InflectedRules $change.Old $change.New
    # PowerShell 5.1 bazı makinelerde generic List[string].Add() çağrısını
    # WinForms olayının içinden yanlış bağlayabiliyor. ArrayList tek aşırı
    # yüklemeli Add kullanır ve += dizisinin büyüdükçe yaptığı kopyaları önler.
    $bulkTargetKeys=New-Object Collections.ArrayList
    # Regex yerine literal IndexOf: ~80k satırda UI donmasını azaltır.
    $needles=@($rules.Keys|Sort-Object Length -Descending)
    if($null-ne$status){$status.Text='Benzer satırlar taranıyor…'}
    if($null-ne$form -and -not$form.IsDisposed){$form.Refresh()}
    $enum=$script:Translations.GetEnumerator()
    while($enum.MoveNext()){
        $translationKey=[string]$enum.Key
        if($translationKey-ceq$editedKey -or (Test-IsProtectedNameKey $translationKey)){continue}
        $currentText=[string]$enum.Value
        $matched=$false
        foreach($needle in $needles){
            if($currentText.IndexOf($needle,[StringComparison]::Ordinal)-ge0){$matched=$true;break}
        }
        if($matched){[void]$bulkTargetKeys.Add($translationKey)}
    }
    if($bulkTargetKeys.Count-eq0){
        if($null-ne$status){$status.Text="Elle düzeltme kaydedildi (benzer satır yok): $editedKey"}
        return
    }
    $msg=@(
        'Bu satırdaki düzeltmeniz ZATEN KAYDEDİLDİ.',
        '',
        "Değişiklik:  $($change.Old)  →  $($change.New)",
        '',
        "Aynı düzeltmeyi benzer diğer $($bulkTargetKeys.Count) satıra da uygulamak ister misiniz?",
        '',
        'EVET  = Diğer benzer satırlara da uygula',
        'HAYIR = Yalnız bu satır kalsın (diğer satırlara UYGULAMA)'
    )-join"`n"
    $answer=[Windows.Forms.MessageBox]::Show($msg,'Diğer satırlara da uygula?','YesNo','Question')
    if($answer-ne[Windows.Forms.DialogResult]::Yes){
        if($null-ne$status){$status.Text="Elle düzeltme kaydedildi (toplu yayım yok): $editedKey"}
        return
    }
    if(Test-Path -LiteralPath $ProjectFile){Copy-Item -LiteralPath $ProjectFile -Destination (Join-Path $TranslationBackupDir 'wakfu_tr_ceviri.toplu_degisim_yedegi.json') -Force}
    if($null-eq$script:ManualRepairs){$script:ManualRepairs=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)}
    foreach($k in $bulkTargetKeys){
        $updated=[string]$script:Translations[$k]
        foreach($rule in $needles){$updated=$updated.Replace($rule,$rules[$rule])}
        $script:Translations[$k]=$updated
        $script:ManualRepairs[$k]=$updated
        Write-LiveTranslationRecord ([string]$k) '' $updated 'MANUEL_TOPLU' 'KAYDEDILDI' "Kaynak düzeltme anahtarı: $editedKey"
    }
    foreach($rule in $rules.Keys){$script:TermPhrases[$rule]=$rules[$rule]};Save-Terminology
    Save-Project
    Save-ManualRepairs
    Initialize-FastSearchIndex
    Sync-VisibleTranslations
    if($null-ne$status){$status.Text="Toplu düzeltme uygulandı: $($bulkTargetKeys.Count) ek satır (+ bu satır zaten kayıtlıydı)"}
}

function Queue-BulkManualCorrection([string]$oldValue,[string]$newValue,[string]$editedKey) {
    if($script:Closing -or $script:BulkPromptPending){return}
    $script:BulkPromptPending=$true
    $oldCopy=[string]$oldValue;$newCopy=[string]$newValue;$keyCopy=[string]$editedKey
    $work={
        try{Offer-BulkManualCorrection $oldCopy $newCopy $keyCopy}
        catch{Write-AppLog $_.Exception.ToString() 'ELLE-DUZELTME-HATA';[Windows.Forms.MessageBox]::Show($form,"Toplu düzeltme denetlenirken hata oluştu:`n$($_.Exception.Message)",'Düzeltme uyarısı','OK','Warning')|Out-Null}
        finally{$script:BulkPromptPending=$false}
    }.GetNewClosure()
    # Önce tek satır kaydı biter; tarama+soru UI kuyruğunda sonra çalışır.
    if($form -and -not$form.IsDisposed -and $form.IsHandleCreated){[void]$form.BeginInvoke([Action]$work)}
    else{& $work}
}

function Sync-VisibleTranslations {
    foreach($visibleEntry in $script:Visible){
        $visibleEntry.Turkish=Get-EntryTranslation $visibleEntry
    }
    if($null-ne$grid){$grid.Invalidate()}
}

function Load-VisibleEntry([int]$rowIndex) {
    if($rowIndex-lt0 -or $rowIndex-ge$script:Visible.Count){return}
    if($script:LoadingEntry){return}
    $script:LoadingEntry=$true
    try{
        Save-Current
        $selectedEntry=$script:Visible[$rowIndex]
        $script:SelectedKey=[string]$selectedEntry.Key
        $english.Text=[string]$selectedEntry.English
        Apply-TurkishEditorState (Test-IsForcedEnglishNameKey $script:SelectedKey)
        # Listede görünen etkin çeviriyi yükle. Çeviri bir anahtar/terim
        # düzeltmesinden geliyorsa yalnızca ham bellek sözlüğüne bakmak alt kutuyu
        # boş bırakıyordu.
        $turkish.Text=[string]$selectedEntry.Turkish
        $script:LoadedTurkishValue=$turkish.Text
    }finally{$script:LoadingEntry=$false}
}

function Save-Project {
    $serializer = New-Object Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    # 127 binden fazla anahtarı her elle düzenlemede yeniden sıralamak aramayı
    # bekletiyordu. Dictionary doğrudan yazılır; geçici dosya kullanılarak kayıt
    # yine güvenli ve atomik biçimde değiştirilir.
    $tempFile=$ProjectFile+'.tmp'
    [IO.File]::WriteAllText($tempFile,$serializer.Serialize($script:Translations),(New-Object Text.UTF8Encoding($true)))
    if(Test-Path -LiteralPath $ProjectFile){
        $replaceBackup=$ProjectFile+'.replace.bak'
        if(Test-Path -LiteralPath $replaceBackup){[IO.File]::Delete($replaceBackup)}
        [IO.File]::Replace($tempFile,$ProjectFile,$replaceBackup,$true)
        if(Test-Path -LiteralPath $replaceBackup){[IO.File]::Delete($replaceBackup)}
    }else{[IO.File]::Move($tempFile,$ProjectFile)}
    $script:ProjectDirty=$false
    if($null-ne$status){$status.Text = "Kaydedildi: $($script:Translations.Count) çeviri"}
}

function Flush-PersistentState {
    if($script:ProjectDirty){Save-Project}
    if($script:ManualDirty){Save-ManualRepairs}
}

function Queue-PersistentSave {
    $script:ProjectDirty=$true
    $script:ManualDirty=$true
    $script:BuildDirty=$true
    if($null-ne$script:SaveTimer -and -not$script:Closing){
        $script:SaveTimer.Stop()
        $script:SaveTimer.Start()
    }else{Flush-PersistentState}
}

function Import-PartialGpuResults([string]$path) {
    if([string]::IsNullOrWhiteSpace($path)-or-not(Test-Path -LiteralPath $path)){return 0}
    $entryByKey=@{}
    foreach($entry in $script:Entries){$entryByKey[[string]$entry.Key]=$entry}
    $accepted=0
    $reader=New-Object IO.StreamReader($path,[Text.Encoding]::UTF8)
    try{
        while(($line=$reader.ReadLine())-ne$null){
            if([string]::IsNullOrWhiteSpace($line)){continue}
            try{$result=$line|ConvertFrom-Json}catch{continue}
            $key=[string]$result.key
            $entry=$entryByKey[$key]
            $translation=[string]$result.translation
            if(($null -eq $entry) -or [string]::IsNullOrWhiteSpace($translation)){continue}
            if(-not [string]::IsNullOrWhiteSpace([string]$result.worker_quality)){continue}
            $analysis=Get-QualityAnalysis $entry $translation
            if($analysis.Status-eq'CEVRILDI'){
                $script:Translations[$key]=$translation
                $accepted++
            }
        }
    }finally{$reader.Dispose()}
    return $accepted
}

function Clear-AllTranslationMemory {
    if($script:GpuProcess -and -not$script:GpuProcess.HasExited){
        [Windows.Forms.MessageBox]::Show('Çeviri devam ederken bellek silinemez. Önce Çeviriyi Durdur düğmesine basın.','İşlem devam ediyor','OK','Warning')|Out-Null
        return
    }
    $first=[Windows.Forms.MessageBox]::Show("Kayıtlı Türkçe çeviri belleğinin TAMAMI silinecek.`n`nProgram silmeden önce tarihli bir yedek oluşturacak. Oyuna kurulu mevcut dosyalara dokunulmayacak.`n`nDevam edilsin mi?",'Tüm çevirileri sil','YesNo','Warning')
    if($first-ne[Windows.Forms.DialogResult]::Yes){return}
    $second=[Windows.Forms.MessageBox]::Show('Emin misiniz? GPU çevirisi daha sonra 154.963 metni sıfırdan işleyecek.','Son onay','YesNo','Question')
    if($second-ne[Windows.Forms.DialogResult]::Yes){return}
    Save-Current
    $backup=''
    if(Test-Path -LiteralPath $ProjectFile){
        $backup=Join-Path $TranslationBackupDir ('wakfu_tr_ceviri_silme_yedegi_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.json')
        Copy-Item -LiteralPath $ProjectFile -Destination $backup -Force
    }
    foreach($manualKey in @($script:ManualRepairs.Keys)){if($script:TermKeys.ContainsKey($manualKey)){[void]$script:TermKeys.Remove($manualKey)}}
    $script:Translations=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    $script:ManualRepairs=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    $script:ManualDirty=$true;$script:BuildDirty=$true
    $script:SelectedKey=$null;$script:LoadedTurkishValue='';$english.Clear();$turkish.Clear()
    Save-Project;Save-ManualRepairs;Initialize-FastSearchIndex
    Refresh-Results
    foreach($oldLog in @($LogFile,($LogFile+'.onceki.txt'),$LiveTsv,$StatusTsv,$IssuesTsv,$DiagnosticSummary,$LastGpuInput,$LastGpuOutput,$LastGpuContext,(Join-Path $LogDir 'Wakfu_Kalite_Kontrol_Raporu.csv'),(Join-Path $LogDir 'Wakfu_Kalite_Kontrol_Ozeti.txt'))){try{if(Test-Path -LiteralPath $oldLog){Remove-Item -LiteralPath $oldLog -Force}}catch{}}
    Initialize-LiveTranslationLog
    $message="Tüm çeviri belleği silindi. Artık GPU ile sıfırdan çevirebilirsiniz."
    if($backup){$message+="`n`nOtomatik yedek:`n$backup"}
    [Windows.Forms.MessageBox]::Show($message,'Çeviri belleği temizlendi','OK','Information')|Out-Null
}

function Escape-PropertyValue([string]$text) {
    if ($null -eq $text) { return '' }
    # Projedeki \n gibi Java-properties kaçışları zaten doğru biçimdedir.
    # Ters eğik çizgiyi tekrar kaçırmak oyunda "\n" yazısının görünmesine yol açar.
    return ($text -replace "`r?`n",'\n')
}

function Align-PropertyMarkup([string]$source,[string]$candidate) {
    if([string]::IsNullOrEmpty($candidate)){return $candidate}
    $tagPattern='<[^>]*>'
    $sourceTags=@([regex]::Matches($source,$tagPattern)|ForEach-Object{$_.Value})
    $candidateTags=@([regex]::Matches($candidate,$tagPattern)|ForEach-Object{$_.Value})
    if($sourceTags.Count-eq$candidateTags.Count){
        $tagCompatible=$true
        for($i=0;$i-lt$sourceTags.Count;$i++){
            $a=[regex]::Match($sourceTags[$i],'<\s*(/?)\s*([A-Za-z0-9]+)')
            $b=[regex]::Match($candidateTags[$i],'<\s*(/?)\s*([A-Za-z0-9]+)')
            if(-not$a.Success-or-not$b.Success-or$a.Groups[1].Value-cne$b.Groups[1].Value-or$a.Groups[2].Value.ToLowerInvariant()-cne$b.Groups[2].Value.ToLowerInvariant()){$tagCompatible=$false;break}
        }
        if($tagCompatible){
            $tagIndex=@(0)
            $candidate=[regex]::Replace($candidate,$tagPattern,[Text.RegularExpressions.MatchEvaluator]{param($m)$index=$tagIndex[0];$tagIndex[0]=$index+1;return $sourceTags[$index]})
        }
    }
    $bracketPattern='\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]'
    $sourceTokens=@([regex]::Matches($source,$bracketPattern)|ForEach-Object{$_.Value})
    $candidateTokens=@([regex]::Matches($candidate,$bracketPattern)|ForEach-Object{$_.Value})
    if($sourceTokens.Count-eq$candidateTokens.Count){
        $tokenCompatible=$true
        for($i=0;$i-lt$sourceTokens.Count;$i++){if($sourceTokens[$i].ToLowerInvariant()-cne$candidateTokens[$i].ToLowerInvariant()){$tokenCompatible=$false;break}}
        if($tokenCompatible){
            $tokenIndex=@(0)
            $candidate=[regex]::Replace($candidate,$bracketPattern,[Text.RegularExpressions.MatchEvaluator]{param($m)$index=$tokenIndex[0];$tokenIndex[0]=$index+1;return $sourceTokens[$index]})
        }
    }
    return $candidate
}

function Test-SearchMatch([string]$query,[string]$key,[string]$englishText,[string]$turkishText) {
    if([string]::IsNullOrWhiteSpace($query)){return $true}
    $culture=[Globalization.CultureInfo]::GetCultureInfo('tr-TR')
    $haystack=("$key $englishText $turkishText").ToLower($culture)
    $words=@([regex]::Split($query.Trim(),'\s+')|Where-Object {$_})
    foreach($word in $words){
        if(-not $haystack.Contains(([string]$word).ToLower($culture))){return $false}
    }
    return $true
}

function Get-EstimatedEnglishOriginal([string]$turkishText) {
    if([string]::IsNullOrWhiteSpace($turkishText)){return ''}
    if($script:ReverseSearchCache.ContainsKey($turkishText)){return [string]$script:ReverseSearchCache[$turkishText]}
    # Arama sırasında ağ/GPU kullanılmaz. İnternet bağlantısının zaman aşımına
    # uğraması daha önce pencerenin uzun süre "Yanıt Vermiyor" görünmesine
    # neden oluyordu. Bulunamayan sorgu hemen boş sonuç döndürür.
    return ''
}

function Refresh-Results {
    $searchTimer=[Diagnostics.Stopwatch]::StartNew()
    Save-Current
    $q = $search.Text.Trim()
    $onlyMissing = $missing.Checked
    $found = New-Object System.Collections.Generic.List[object]
    $exactTurkishMatch=$false
    $culture=[Globalization.CultureInfo]::GetCultureInfo('tr-TR')
    $queryWords=if($q){@([regex]::Split($q.Trim(),'\s+')|Where-Object {$_})}else{@()}
    if($q -and -not$onlyMissing -and $script:SearchKeys.Count-eq$script:Entries.Count){
        $limit=if($script:ShowAllResults){[int]::MaxValue}else{1000}
        $indexes=[WakfuFastSearch]::Find($script:SearchKeys,$script:SearchEnglish,$script:SearchTurkish,[string[]]$queryWords,$limit)
        foreach($index in $indexes){
            $e=$script:Entries[$index];$tr=Get-EntryTranslation $e
            if([string]::Equals($tr.Trim(),$q,[StringComparison]::CurrentCultureIgnoreCase)){$exactTurkishMatch=$true}
            $found.Add([pscustomobject]@{Key=$e.Key;English=$e.English;Turkish=$tr})
        }
    }else{
        foreach ($e in $script:Entries) {
            if ($onlyMissing -and -not (Test-IsUntranslated $e)) { continue }
            $key=[string]$e.Key;$source=[string]$e.English;$tr=Get-EntryTranslation $e
            if($q){
                $isMatch=$true
                foreach($word in $queryWords){
                    if($key.IndexOf($word,[StringComparison]::CurrentCultureIgnoreCase)-lt0 -and
                       $source.IndexOf($word,[StringComparison]::CurrentCultureIgnoreCase)-lt0 -and
                       $tr.IndexOf($word,[StringComparison]::CurrentCultureIgnoreCase)-lt0){$isMatch=$false;break}
                }
                if(-not$isMatch){continue}
            }
            if($q -and [string]::Equals($tr.Trim(),$q,[StringComparison]::CurrentCultureIgnoreCase)){$exactTurkishMatch=$true}
            $found.Add([pscustomobject]@{ Key=$e.Key; English=$e.English; Turkish=$tr })
            if (-not $script:ShowAllResults -and $found.Count -ge 1000) { break }
        }
    }
    $normalResults=@($found.ToArray())
    $composedMatch=$false
    # Bazı XUL arayüz yazıları tek bir çeviri anahtarı değildir. Örneğin
    # "Select Your character", selection + yourCharacter anahtarları birleştirilerek
    # oluşturulur. Birleşik Türkçe ifade doğrudan bulunamazsa onu oluşturan
    # gerçek ve düzenlenebilir satırları göster.
    if($q -and $normalResults.Count-eq0){
        $compositeWords=@([regex]::Split($q.Trim(),'\s+')|Where-Object {$_.Length-ge2})
        if($compositeWords.Count-ge2){
            $parts=New-Object System.Collections.Generic.List[object]
            $seenPartKeys=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
            foreach($word in $compositeWords){
                foreach($index in [WakfuFastSearch]::FindExactTurkish($script:SearchTurkish,[string]$word,30)){
                    $e=$script:Entries[$index];$tr=Get-EntryTranslation $e
                    if($seenPartKeys.Add([string]$e.Key)){$parts.Add([pscustomobject]@{Key=$e.Key;English=$e.English;Turkish=$tr})}
                }
            }
            # Sorgudaki her kelime için ayrı bir tam çeviri satırı bulunduysa,
            # uzun açıklamalardaki tesadüfi eşleşmeleri ve tahmini satırı bastır.
            $matchedWords=@($parts|ForEach-Object {([string]$_.Turkish).Trim().ToLower($culture)}|Select-Object -Unique)
            $wantedWords=@($compositeWords|ForEach-Object {([string]$_).Trim().ToLower($culture)}|Select-Object -Unique)
            if($parts.Count-ge2 -and $matchedWords.Count-eq$wantedWords.Count){
                # Aynı Türkçe karşılığa sahip Pick/Choose/Select gibi farklı
                # anahtarları, birleşik ifadenin İngilizce karşılığıyla ayırt et.
                $estimatedComposite=Get-EstimatedEnglishOriginal $q
                if($estimatedComposite){
                    $englishHaystack=(' '+$estimatedComposite.Trim().ToLowerInvariant()+' ')
                    $filteredParts=@($parts|Where-Object {
                        $candidate=(' '+([string]$_.English).Trim().ToLowerInvariant()+' ')
                        $englishHaystack.Contains($candidate)
                    })
                    $filteredTurkish=@($filteredParts|ForEach-Object {([string]$_.Turkish).Trim().ToLower($culture)}|Select-Object -Unique)
                    if($filteredParts.Count-ge2 -and $filteredTurkish.Count-eq$wantedWords.Count){
                        $parts.Clear()
                        foreach($part in $filteredParts){$parts.Add($part)}
                    }
                }
                $normalResults=@($parts.ToArray())
                $composedMatch=$true
            }
        }
    }
    if($q){
        $normalResults=@($normalResults|Sort-Object @{Expression={if([string]::Equals(([string]$_.Turkish).Trim(),$q,[StringComparison]::CurrentCultureIgnoreCase)){0}elseif(([string]$_.Turkish).IndexOf($q,[StringComparison]::CurrentCultureIgnoreCase)-ge0){1}else{2}}},@{Expression={([string]$_.Turkish).Length}})
    }
    # Gerçek sonuç bulunduysa ters çeviri servisini çağırma. Önceki davranış
    # her aramada ağı beklediği için pencerenin "Yanıt Vermiyor" görünmesine yol açıyordu.
    if($q -and $normalResults.Count-eq0 -and -not$exactTurkishMatch -and -not$composedMatch){
        $estimated=Get-EstimatedEnglishOriginal $q
        if($estimated){
            $fallback=[pscustomobject]@{Key='__fallback__';English="[Tahmini orijinal] $estimated";Turkish=$q}
            $script:Visible=@($fallback)+$normalResults
        }else{$script:Visible=$normalResults}
    }else{$script:Visible=$normalResults}
    $grid.RowCount=$script:Visible.Count
    $grid.Invalidate()
    if($script:Visible.Count-eq1){
        # Tek sonuçta kullanıcı ayrıca satıra tıklamak zorunda kalmasın.
        # VirtualMode satırı mavi gösterebildiği hâlde SelectionChanged olayı
        # her aramadan sonra yeniden çalışmıyordu.
        try{
            $grid.ClearSelection()
            $grid.CurrentCell=$grid.Rows[0].Cells[0]
            $grid.Rows[0].Selected=$true
            Load-VisibleEntry 0
        }catch{Write-AppLog $_.Exception.ToString() 'TEK-SONUC-SECIM-HATA'}
    }elseif($script:Visible.Count-eq0){
        $script:SelectedKey=$null;$script:LoadedTurkishValue='';$english.Clear();$turkish.Clear()
    }
    if($script:ShowAllResults){
        $status.Text = "$($script:Visible.Count) sonucun tamamı gösteriliyor. Toplam metin: $($script:Entries.Count)"
    } else {
        $status.Text = "$($script:Visible.Count) sonuç gösteriliyor (en fazla 1000). Toplam metin: $($script:Entries.Count)"
    }
    if($composedMatch){$status.Text="Birleşik arayüz metnini oluşturan $($script:Visible.Count) gerçek satır gösteriliyor."}
    $searchTimer.Stop()
    $status.Text += (' — arama: {0:N2} sn' -f $searchTimer.Elapsed.TotalSeconds)
}

function Save-Current {
    if ($script:SelectedKey -and $script:SelectedKey-ne'__fallback__') {
        if(Test-IsForcedEnglishNameKey ([string]$script:SelectedKey)){
            $script:LoadedTurkishValue=$english.Text
            $status.Text="Özel ad kilitli (canavar/NPC İngilizce kalır): $($script:SelectedKey)"
            return
        }
        $v = $turkish.Text.Trim()
        $old=[string]$script:LoadedTurkishValue
        if ($v) { $script:Translations[$script:SelectedKey] = $v }
        elseif ($script:Translations.ContainsKey($script:SelectedKey)) { $script:Translations.Remove($script:SelectedKey) }
        if($v-cne$old){
            Sync-VisibleTranslations
            if($null-eq$script:ManualRepairs){$script:ManualRepairs=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)}
            if($v){
                $script:ManualRepairs[$script:SelectedKey]=$v
                $script:TermKeys[$script:SelectedKey]=$v
            }else{
                if($script:ManualRepairs.ContainsKey($script:SelectedKey)){[void]$script:ManualRepairs.Remove($script:SelectedKey)}
                if($script:TermKeys.ContainsKey($script:SelectedKey)){[void]$script:TermKeys.Remove($script:SelectedKey)}
            }
            $searchValue=$v
            if(-not$searchValue -and $script:EntryEnglish.ContainsKey($script:SelectedKey)){
                $searchSource=[string]$script:EntryEnglish[$script:SelectedKey]
                if($script:TermValues.ContainsKey($searchSource)){$searchValue=[string]$script:TermValues[$searchSource]}
            }
            if($script:SearchKeys.Count-gt0){[WakfuFastSearch]::Update($script:SearchKeys,$script:SearchTurkish,[string]$script:SelectedKey,[string]$searchValue)}
            # 1) Bu satır her zaman hemen kaydedilir (Hayır ≠ vazgeç).
            # 2) Benzer satır taraması + Evet/Hayır sorusu kayıttan SONRA,
            #    UI kuyruğunda çalışır; bekleme kaydı geciktirmez.
            Queue-PersistentSave
            Write-AppLog "Elle çeviri kaydedildi | Anahtar=$($script:SelectedKey)"
            $manualState=if($v){'KAYDEDILDI'}else{'SILINDI'}
            Write-LiveTranslationRecord ([string]$script:SelectedKey) ([string]$english.Text) $v 'MANUEL' $manualState 'Arayüzden anında kaydedildi'
            $status.Text="Elle düzeltme alındı; otomatik kaydediliyor: $($script:SelectedKey)"
            if($v -and $old){Queue-BulkManualCorrection $old $v ([string]$script:SelectedKey)}
        }
        $script:LoadedTurkishValue=$v
    }
}

function Test-IsUntranslated($entry) {
    if(Test-IsProtectedNameKey ([string]$entry.Key)){return $false}
    $analysis=Get-QualityAnalysis $entry (Get-EntryTranslation $entry)
    return ($analysis.Status-in@('EKSIK','BICIM_HATASI','INGILIZCE_KALDI'))
}

function Rewrite-PropertyEntry($zip, [string]$entryName, [hashtable]$translations) {
    $entry = $zip.GetEntry($entryName)
    if (-not $entry) { return }
    $reader = New-Object IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8, $true)
    try { $content = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines = $content -split "`r?`n", -1
    for ($i=0; $i -lt $lines.Length; $i++) {
        $pos = $lines[$i].IndexOf('=')
        if ($pos -lt 1) { continue }
        $key = $lines[$i].Substring(0,$pos)
        $sourceValue=$lines[$i].Substring($pos+1)
        if (Test-IsProtectedNameKey $key) { continue }
        $letterCount=[regex]::Matches($sourceValue,'\p{L}').Count
        $symbolHeavyGibberish=($sourceValue.Length-ge12-and$letterCount-le6-and$sourceValue-notmatch'[A-Za-z]{2,}')
        if($symbolHeavyGibberish){continue}
        $candidate=$null;$applyPhraseRules=$true
        if ($script:TermKeys.ContainsKey($key)-and-not$script:ManualRepairs.ContainsKey($key)) { $candidate=[string]$script:TermKeys[$key];$applyPhraseRules=$false }
        elseif ((Test-IsWorldTermOverrideKey $key)-and$script:TermValues.ContainsKey($sourceValue)) { $candidate=[string]$script:TermValues[$sourceValue];$applyPhraseRules=$false }
        elseif ($script:ManualRepairs.ContainsKey($key)) { $candidate=[string]$script:ManualRepairs[$key];$applyPhraseRules=$false }
        elseif ($script:TermKeys.ContainsKey($key)) { $candidate=[string]$script:TermKeys[$key];$applyPhraseRules=$false }
        elseif ($script:TermValues.ContainsKey($sourceValue)) { $candidate=[string]$script:TermValues[$sourceValue];$applyPhraseRules=$false }
        elseif ($translations.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($translations[$key])) { $candidate=[string]$translations[$key] }
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            if($applyPhraseRules){$candidate=Apply-TermPhrases $candidate}
            $candidate=Align-PropertyMarkup $sourceValue $candidate
            if (Test-FormatTokens $sourceValue $candidate) {
                $lines[$i] = $key + '=' + (Escape-PropertyValue $candidate)
            } else { $script:BuildSkipped++ }
        }
    }
    $entry.Delete()
    $newEntry = $zip.CreateEntry($entryName,[IO.Compression.CompressionLevel]::Optimal)
    $writer = New-Object IO.StreamWriter($newEntry.Open(), (New-Object Text.UTF8Encoding($false)))
    try { $writer.Write([string]::Join($newline,$lines)) } finally { $writer.Dispose() }
}

function Build-Jar([switch]$Silent) {
    if(-not $BuildOnly){Save-Current;Flush-PersistentState}
    Load-Terminology
    $buildUpdates=@(Sync-GameUpdates)
    if($buildUpdates.Count-gt0){$script:BuildDirty=$true}
    $cache=Read-BuildCache
    $i18nFingerprint=Get-TextFingerprint ('i18n-v5|'+$AppVersion+'|'+(Get-FileFingerprint $SourceJar)+'|'+(Get-FileFingerprint $ProjectFile)+'|'+(Get-FileFingerprint $TerminologyFile)+'|'+(Get-FileFingerprint $ManualRepairsFile)+'|'+(Get-FileFingerprint $JarBuilder)+'|'+(Get-FileFingerprint $AuditWorker))
    $fontParts=New-Object Collections.Generic.List[string]
    foreach($font in Get-ChildItem -LiteralPath $FontPatchDir -Filter '*.ttf' -File -ErrorAction SilentlyContinue|Sort-Object Name){[void]$fontParts.Add($font.Name+':'+(Get-FileFingerprint $font.FullName))}
    $guiSourceForFingerprint=if(Test-Path -LiteralPath $CurrentGuiJar){$CurrentGuiJar}else{$OriginalGuiJar}
    $guiFingerprint=Get-TextFingerprint ('gui-v2|'+(Get-FileFingerprint $guiSourceForFingerprint)+'|'+($fontParts-join'|'))
    $clientSource=if(Test-Path -LiteralPath $CurrentClientJar){$CurrentClientJar}elseif(Test-Path -LiteralPath $OriginalClientJar){$OriginalClientJar}else{$InstalledClientJar}
    $fontProfile=Get-OverheadFontProfile
    $clientFingerprint=Get-TextFingerprint ('client-v11|'+(Get-FileFingerprint $clientSource)+'|'+(Get-FileFingerprint $AlmanaxPatchClass)+'|weather-tr-TR|battleground-tr-TR|achievement-total|persistent-name-toggle-stackmap-safe|overhead-font-profile='+$fontProfile.Key+'-'+$fontProfile.Main+'-'+$fontProfile.Title)
    $dataSource=if(Test-Path -LiteralPath $CurrentDataJar){$CurrentDataJar}elseif(Test-Path -LiteralPath $OriginalDataJar){$OriginalDataJar}else{$InstalledDataJar}
    $dataFingerprint=Get-TextFingerprint ('data-v3|'+(Get-FileFingerprint $dataSource)+'|press-only-name-overheads-toggle')
    $script:BuildSkipped=0
    $i18nReady=(Test-I18nJar $OutputJar)-and([string]$cache.i18n-eq$i18nFingerprint)-and-not$script:BuildDirty
    if($i18nReady){
        Write-AppLog 'Türkçe JAR güncel; yeniden oluşturma atlandı.'
    }else{
        $builderPython=''
        if(Test-Path -LiteralPath $AuditPython){
            $builderPython=$AuditPython
        }elseif(Test-Path -LiteralPath $GpuPython){
            $builderPython=$GpuPython
        }else{
            $pythonCommand=Get-Command python.exe -ErrorAction SilentlyContinue
            if($pythonCommand -and $pythonCommand.Source -notmatch '(?i)\\WindowsApps\\python(?:3)?\.exe$' -and (Test-Path -LiteralPath $pythonCommand.Source)){$builderPython=$pythonCommand.Source}
        }
        if($builderPython-and(Test-Path -LiteralPath $JarBuilder)-and(Test-Path -LiteralPath $ManualRepairsFile)){
            $result=@(& $builderPython $JarBuilder '--source-jar' $SourceJar '--output-jar' $OutputJar '--project' $ProjectFile '--terminology' $TerminologyFile '--manual-repairs' $ManualRepairsFile 2>&1)
            if($LASTEXITCODE-ne0-or-not(Test-Path -LiteralPath $OutputJar)){throw ($result-join"`n")}
            $resultText=$result-join"`n"
            if($resultText-match'SKIPPED=(\d+)'){$script:BuildSkipped=[int]$Matches[1]}
            Write-AppLog "Hızlı güvenli JAR oluşturuldu | $resultText"
        }else{
            Copy-Item -LiteralPath $SourceJar -Destination $OutputJar -Force
            $zip = [IO.Compression.ZipFile]::Open($OutputJar,[IO.Compression.ZipArchiveMode]::Update)
            try {
                Rewrite-PropertyEntry $zip 'texts_en.properties' $script:Translations
                Rewrite-PropertyEntry $zip 'texts_en_cleaned.properties' $script:Translations
            } finally { $zip.Dispose() }
        }
    }
    if(-not((Test-GuiJar $OutputGuiJar)-and([string]$cache.gui-eq$guiFingerprint))){Build-GuiPatch}
    if(-not((Test-ClientJar $OutputClientJar)-and(Test-PersistentNameOverheadJar $OutputClientJar)-and([string]$cache.client-eq$clientFingerprint))){Build-ClientPatch}
    if(-not((Test-DataJar $OutputDataJar)-and(Test-NameToggleShortcutJar $OutputDataJar)-and([string]$cache.data-eq$dataFingerprint))){Build-DataPatch}
    Save-BuildCache $i18nFingerprint $guiFingerprint $clientFingerprint $dataFingerprint
    $script:BuildDirty=$false
    if($null-ne$status){$status.Text = "Paket hazır: $OutputJar — bozuk biçim nedeniyle İngilizce bırakılan: $script:BuildSkipped"}
    if($BuildOnly){
        Write-Output "BUILD_OK|$OutputJar|SKIPPED=$script:BuildSkipped"
    }elseif(-not$Silent){
        [Windows.Forms.MessageBox]::Show("Türkçe paket oluşturuldu:`n$OutputJar`n`nBiçim kodu güvenli olmadığı için İngilizce bırakılan giriş: $script:BuildSkipped",'Tamam','OK','Information') | Out-Null
    }
}

function Build-SetupInstaller {
    try{
        $dialog=New-Object Windows.Forms.SaveFileDialog
        $dialog.Title='Wakfu Türkçe Yama Kurulum EXE dosyasını kaydet'
        $dialog.Filter='Windows uygulaması (*.exe)|*.exe'
        $dialog.FileName='Wakfu_Turkce_Yama_Setup.exe'
        $dialog.InitialDirectory=$ProjectRoot
        $dialog.OverwritePrompt=$true
        if($dialog.ShowDialog()-ne[Windows.Forms.DialogResult]::OK){$setupStatus.Text='EXE oluşturma iptal edildi.';return}
        $selectedOutput=[IO.Path]::GetFullPath($dialog.FileName)
        Build-Jar -Silent
        if(-not(Test-Path -LiteralPath $SetupBuilder)){throw 'Kurulum EXE oluşturucu dosyası bulunamadı.'}
        $btnSetupBuild.Enabled=$false;$setupStatus.Text='Kurulum EXE hazırlanıyor…';[Windows.Forms.Application]::DoEvents()
        $result=@(& $SetupBuilder -OutputPath $selectedOutput 2>&1)
        if(-not(Test-Path -LiteralPath $selectedOutput)){throw ($result-join"`n")}
        $size=[Math]::Round((Get-Item -LiteralPath $selectedOutput).Length/1MB,1);$hash=(Get-FileHash -LiteralPath $selectedOutput -Algorithm SHA256).Hash
        $setupStatus.Text="Hazır: $selectedOutput — $size MB"
        $setupPath.Text=$selectedOutput
        [Windows.Forms.MessageBox]::Show("Bağımsız kurulum EXE hazırlandı:`n$selectedOutput`n`nBoyut: $size MB`nSHA-256: $hash`n`nSetup başka Windows bilgisayarlarda Steam veya Wakfu klasörü seçilerek kullanılabilir.",'Kurulum EXE hazır','OK','Information')|Out-Null
    }catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Kurulum EXE hatası','OK','Error')|Out-Null}finally{$btnSetupBuild.Enabled=$true}
}

function Install-Jar {
    if(-not(Ensure-WakfuGameDir)){return}
    Build-Jar -Silent
    $fontProfile=Get-OverheadFontProfile
    if(-not(Ensure-OriginalBackupForInstall)){
        if($script:NonInteractiveMode){throw 'Temiz i18n_en.jar yedeği bulunamadı; güvenli kurulum başlatılmadı.'}
        [Windows.Forms.MessageBox]::Show('Temiz i18n_en.jar yedeği bulunamadı. Oyun dosyaları temiz İngilizce değilse önce Oyundaki Yamayı Temizle veya Orijinali Yedekle düğmesini kullanın.','Yedek gerekli','OK','Warning') | Out-Null
        return
    }
    if(-not(Test-Path -LiteralPath $OriginalClientJar) -and (Test-Path -LiteralPath $InstalledClientJar)){
        New-Item -ItemType Directory -Path $BackupDir -Force|Out-Null
        Copy-Item -LiteralPath $InstalledClientJar -Destination $OriginalClientJar -Force
    }
    if(-not(Test-Path -LiteralPath $OriginalDataJar) -and (Test-Path -LiteralPath $InstalledDataJar)){
        New-Item -ItemType Directory -Path $BackupDir -Force|Out-Null
        Copy-Item -LiteralPath $InstalledDataJar -Destination $OriginalDataJar -Force
    }
    $i18nDir = Join-Path $GameDir 'contents\i18n'
    $destEnglish = Join-Path $i18nDir 'i18n_en.jar'
    $destActive = Join-Path $i18nDir 'i18n.jar'
    foreach($requiredOutput in @($OutputJar,$OutputGuiJar,$OutputClientJar,$OutputDataJar)){if(-not(Test-Path -LiteralPath $requiredOutput)){throw "Kurulum paketi eksik; işlem başlamadan durduruldu: $requiredOutput"}}
    if(-not(Test-PersistentNameOverheadJar $OutputClientJar)){throw 'V oyuncu adı ve seçilen baş üstü yazı profili kurulumdan önce doğrulanamadı.'}
    if(-not(Test-ClientJvmVerification $OutputClientJar)){throw 'V oyuncu adı sınıfı kurulumdan önce Java doğrulamasından geçmedi.'}
    if(-not(Test-NameToggleShortcutJar $OutputDataJar)){throw 'V tuşunun tek basış aç/kapat ayarı kurulumdan önce doğrulanamadı.'}
    $transaction=Join-Path $env:TEMP ('WakfuKurulum_'+[Guid]::NewGuid().ToString('N'));$rollback=Join-Path $transaction 'rollback';$payload=Join-Path $transaction 'payload';New-Item -ItemType Directory -Path $rollback,$payload -Force|Out-Null
    $installItems=New-Object Collections.Generic.List[object]
    $pairIndex=0
    try{
        foreach($pair in @(@($OutputJar,$destEnglish),@($OutputJar,$destActive),@($OutputGuiJar,$InstalledGuiJar),@($OutputClientJar,$InstalledClientJar),@($OutputDataJar,$InstalledDataJar))){
            $expected=(Get-FileHash -LiteralPath $pair[0] -Algorithm SHA256).Hash;$stagedSource=Join-Path $payload (("{0:D2}_"-f$pairIndex)+[IO.Path]::GetFileName($pair[0]));Copy-Item -LiteralPath $pair[0] -Destination $stagedSource -Force
            if((Get-FileHash -LiteralPath $stagedSource -Algorithm SHA256).Hash-ne$expected){throw "Kurulum kaynağı geçici alana eksiksiz alınamadı: $($pair[0])"}
            [void]$installItems.Add([pscustomobject]@{Source=[IO.Path]::GetFullPath($stagedSource);Target=[IO.Path]::GetFullPath($pair[1]);Expected=$expected});$pairIndex++
        }
    }catch{Remove-Item -LiteralPath $transaction -Recurse -Force -ErrorAction SilentlyContinue;throw}
    $rows=New-Object Collections.Generic.List[string];$index=0
    foreach($item in $installItems){$source=$item.Source.Replace("'","''");$target=$item.Target.Replace("'","''");$expected=$item.Expected;$old=(Join-Path $rollback (("{0:D2}_" -f $index)+[IO.Path]::GetFileName($item.Target))).Replace("'","''");[void]$rows.Add("@{Source='$source';Target='$target';Expected='$expected';Old='$old'}");$index++}
    $errorFile=(Join-Path $transaction 'hata.txt').Replace("'","''")
    $transactionScript=Join-Path $transaction 'kur.ps1'
    $scriptText=@"
`$ErrorActionPreference='Stop'
`$items=@(
$($rows -join ",`r`n")
)
`$committed=New-Object Collections.Generic.List[object]
try{
    foreach(`$item in `$items){
        New-Item -ItemType Directory -Path (Split-Path -Parent `$item.Target) -Force|Out-Null
        if(Test-Path -LiteralPath `$item.Target){Copy-Item -LiteralPath `$item.Target -Destination `$item.Old -Force}
        [void]`$committed.Add(`$item)
        Copy-Item -LiteralPath `$item.Source -Destination `$item.Target -Force
        if((Get-FileHash -LiteralPath `$item.Target -Algorithm SHA256).Hash-ne`$item.Expected){throw "Dosya özeti eşleşmedi: `$(`$item.Target)"}
    }
}catch{
    `$message=`$_.Exception.Message
    for(`$i=`$committed.Count-1;`$i-ge0;`$i--){`$item=`$committed[`$i];try{if(Test-Path -LiteralPath `$item.Old){Copy-Item -LiteralPath `$item.Old -Destination `$item.Target -Force}else{Remove-Item -LiteralPath `$item.Target -Force -ErrorAction SilentlyContinue}}catch{}}
    [IO.File]::WriteAllText('$errorFile',`$message,(New-Object Text.UTF8Encoding(`$false)));exit 31
}
"@
    # Windows PowerShell 5.1, BOM'suz UTF-8 komut dosyalarında İ/Ç gibi yol
    # karakterlerini ANSI olarak okuyabilir. BOM zorunlu tutularak Türkçe veya
    # başka Unicode klasör adlarında var olan kaynakların kaybolmuş görünmesi önlenir.
    [IO.File]::WriteAllText($transactionScript,$scriptText,(New-Object Text.UTF8Encoding($true)))
    try {
        foreach($item in $installItems){if(-not(Test-Path -LiteralPath $item.Source)-or(Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash-ne$item.Expected){throw "Kurulum başlamadan geçici kaynak doğrulaması başarısız: $($item.Source)"}}
        $p = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList @('-NoProfile','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',$transactionScript)
        if ($p.ExitCode -ne 0) {$detail=if(Test-Path -LiteralPath (Join-Path $transaction 'hata.txt')){Get-Content -LiteralPath (Join-Path $transaction 'hata.txt') -Raw -Encoding UTF8}else{"işlem kodu $($p.ExitCode)"};throw "Kurulum uygulanamadı; değiştirilen oyun dosyaları otomatik geri alındı. Ayrıntı: $detail"}
        $expected=[string]$installItems[0].Expected
        $englishHash=(Get-FileHash -LiteralPath $destEnglish -Algorithm SHA256).Hash
        $activeHash=(Get-FileHash -LiteralPath $destActive -Algorithm SHA256).Hash
        if ($expected -ne $englishHash -or $expected -ne $activeHash) { throw 'Dosyalar kopyalandı ancak doğrulama özeti eşleşmedi.' }
        if((Get-FileHash -LiteralPath $InstalledGuiJar -Algorithm SHA256).Hash-ne[string]$installItems[2].Expected){throw 'Font paketi kurulum doğrulamasından geçmedi.'}
        if((Get-FileHash -LiteralPath $InstalledClientJar -Algorithm SHA256).Hash-ne[string]$installItems[3].Expected){throw 'Arayüz metni düzeltmesi kurulum doğrulamasından geçmedi.'}
        if(-not(Test-PersistentNameOverheadJar $InstalledClientJar)){throw 'V oyuncu adı ve seçilen baş üstü yazı profili kurulum doğrulamasından geçmedi.'}
        if((Get-FileHash -LiteralPath $InstalledDataJar -Algorithm SHA256).Hash-ne[string]$installItems[4].Expected){throw 'V oyuncu adı kısayolu geri yüklemesi kurulum doğrulamasından geçmedi.'}
        if(-not(Test-NameToggleShortcutJar $InstalledDataJar)){throw 'V tuşunun basış başına tek aç/kapat davranışı kurulum doğrulamasından geçmedi.'}
        Write-InstallState
        Write-AppLog "Yama doğrulanarak kuruldu | Baş üstü yazı=$($fontProfile.Label) | i18n SHA256=$expected | Hedef=$GameDir"
        Write-DiagnosticBundle 'Oyuna kurulum'
        if(-not$script:NonInteractiveMode){[Windows.Forms.MessageBox]::Show("Türkçe paket doğrulanarak kuruldu:`n• i18n_en.jar (İngilizce dil paketi)`n• i18n.jar (etkin paket)`n• gui.jar (Türkçe ş/Ş/İ font yaması)`n• wakfu-client.jar ve data.jar (V bir kez: kalıcı açık, V yeniden: kapalı)`n• Baş üstü oyuncu yazıları: $($fontProfile.Label)`n`nOyun güncellemesi dosyaları değiştirirse araç yeni temiz dosyaları algılar ve bir sonraki Oyuna Kur işleminde yamayı yeniden üretir. Temiz orijinaller ayrı yedek klasöründe korunuyor.",'Kurulum doğrulandı','OK','Information') | Out-Null}
    } catch {if($script:NonInteractiveMode){throw};[Windows.Forms.MessageBox]::Show("Kurulum tamamlanamadı:`n$($_.Exception.Message)",'Hata','OK','Error') | Out-Null }finally{Remove-Item -LiteralPath $transaction -Recurse -Force -ErrorAction SilentlyContinue}
}

function Invoke-InstallJarSafe {
    if(($null-ne$btnInstall-and-not$btnInstall.Enabled)-or($null-ne$btnInstallSetup-and-not$btnInstallSetup.Enabled)){return}
    if($null-ne$btnInstall){$btnInstall.Enabled=$false};if($null-ne$btnInstallSetup){$btnInstallSetup.Enabled=$false}
    try{Install-Jar}catch{Write-AppLog $_.Exception.ToString() 'KURULUM-HATA';[Windows.Forms.MessageBox]::Show("Kurulum başlatılamadı:`n$($_.Exception.Message)",'Kurulum hatası','OK','Error')|Out-Null}
    finally{if($null-ne$btnInstall){$btnInstall.Enabled=$true};if($null-ne$btnInstallSetup){$btnInstallSetup.Enabled=$true}}
}

function Test-OriginalBackupComplete {
    if(-not(Test-Path -LiteralPath $OriginalEnglishJar)){return $false}
    return (Test-I18nJar $OriginalEnglishJar) -and (Test-IsEnglishI18nJar $OriginalEnglishJar)
}

function Test-IsCleanInstalledGame {
    if(-not(Test-Path -LiteralPath $InstalledEnglishJar)){return $false}
    if(Test-Path -LiteralPath $OutputJar){
        $installedHash=(Get-FileHash -LiteralPath $InstalledEnglishJar -Algorithm SHA256).Hash
        $outputHash=(Get-FileHash -LiteralPath $OutputJar -Algorithm SHA256).Hash
        if($installedHash-eq$outputHash){return $false}
    }
    if(Test-OriginalBackupComplete){
        $installedHash=(Get-FileHash -LiteralPath $InstalledEnglishJar -Algorithm SHA256).Hash
        $backupHash=(Get-FileHash -LiteralPath $OriginalEnglishJar -Algorithm SHA256).Hash
        if($installedHash-eq$backupHash){return $true}
    }
    return (Test-IsEnglishI18nJar $InstalledEnglishJar)
}

function Sync-MirrorOriginalBackup {
    if(-not(Test-Path -LiteralPath $MirrorBackupRoot)){return}
    $mirrorDir=Join-Path $MirrorBackupRoot 'Oyun_Kaynaklari\Orijinal_Yedek'
    if([IO.Path]::GetFullPath($mirrorDir).TrimEnd('\')-eq[IO.Path]::GetFullPath($BackupDir).TrimEnd('\')){return}
    New-Item -ItemType Directory -Path $mirrorDir -Force|Out-Null
    foreach($item in Get-ChildItem -LiteralPath $BackupDir -File -ErrorAction SilentlyContinue){
        $dest=Join-Path $mirrorDir $item.Name
        if(-not(Test-Path -LiteralPath $dest) -or ((Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash-ne(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash)){
            Copy-Item -LiteralPath $item.FullName -Destination $dest -Force
        }
    }
}

function Invoke-OriginalBackupCore([switch]$FillMissingOnly) {
    New-Item -ItemType Directory -Path $BackupDir -Force|Out-Null
    $i18nDir = Join-Path $GameDir 'contents\i18n'
    foreach ($name in @('i18n_en.jar','i18n_es.jar','i18n_fr.jar','i18n_pt.jar')) {
        $source = Join-Path $i18nDir $name
        $dest = Join-Path $BackupDir $name
        if(-not(Test-Path -LiteralPath $source)){continue}
        $replace=$false
        if(-not(Test-Path -LiteralPath $dest)){$replace=$true}
        elseif($name-eq'i18n_en.jar' -and -not(Test-IsEnglishI18nJar $dest)){$replace=$true}
        if(-not$FillMissingOnly -or $replace){Copy-Item -LiteralPath $source -Destination $dest -Force}
    }
    $active = Join-Path $i18nDir 'i18n.jar'
    $backupActive = Join-Path $BackupDir 'i18n.jar'
    if(-not(Test-Path -LiteralPath $backupActive)){
        if (Test-Path -LiteralPath $active) { Copy-Item -LiteralPath $active -Destination $backupActive -Force }
        elseif (Test-Path -LiteralPath $SourceJar) { Copy-Item -LiteralPath $SourceJar -Destination $backupActive -Force }
    }
    $infoFile = Join-Path $BackupDir 'YEDEK_BILGISI.txt'
    if(-not(Test-Path -LiteralPath $infoFile)){
        @('Wakfu orijinal dil dosyaları yedeği',('Yedek tarihi: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),('Oyun klasörü: ' + $GameDir))|Set-Content -LiteralPath $infoFile -Encoding UTF8
    }
    if((Test-Path -LiteralPath $InstalledGuiJar) -and (-not$FillMissingOnly -or -not(Test-Path -LiteralPath $OriginalGuiJar))){Copy-Item -LiteralPath $InstalledGuiJar -Destination $OriginalGuiJar -Force}
    if((Test-Path -LiteralPath $InstalledClientJar) -and (-not$FillMissingOnly -or -not(Test-Path -LiteralPath $OriginalClientJar))){Copy-Item -LiteralPath $InstalledClientJar -Destination $OriginalClientJar -Force}
    if((Test-Path -LiteralPath $InstalledDataJar) -and (-not$FillMissingOnly -or -not(Test-Path -LiteralPath $OriginalDataJar))){Copy-Item -LiteralPath $InstalledDataJar -Destination $OriginalDataJar -Force}
    Sync-MirrorOriginalBackup
}

function Ensure-OriginalBackupForInstall {
    if(-not(Test-Path -LiteralPath $OriginalEnglishJar)){
        New-Item -ItemType Directory -Path $BackupDir -Force|Out-Null
        $legacyEnglish=if((Test-Path -LiteralPath $CurrentEnglishJar)-and(Test-IsEnglishI18nJar $CurrentEnglishJar)){$CurrentEnglishJar}elseif((Test-Path -LiteralPath $PackagedBaseEnglishJar)-and(Test-IsEnglishI18nJar $PackagedBaseEnglishJar)){$PackagedBaseEnglishJar}else{$null}
        if($legacyEnglish){Copy-Item -LiteralPath $legacyEnglish -Destination $OriginalEnglishJar -Force;if(-not(Test-Path -LiteralPath (Join-Path $BackupDir 'i18n.jar'))){Copy-Item -LiteralPath $legacyEnglish -Destination (Join-Path $BackupDir 'i18n.jar') -Force}}
        foreach($pair in @(@($CurrentGuiJar,$OriginalGuiJar),@($CurrentClientJar,$OriginalClientJar),@($CurrentDataJar,$OriginalDataJar))){if((Test-Path -LiteralPath $pair[0])-and-not(Test-Path -LiteralPath $pair[1])){Copy-Item -LiteralPath $pair[0] -Destination $pair[1] -Force}}
    }
    if(Test-OriginalBackupComplete){return $true}
    if(-not(Test-IsCleanInstalledGame)){
        Write-AppLog 'Otomatik yedek alınamadı: oyun temiz İngilizce durumda değil veya yedek eksik.' 'UYARI'
        return $false
    }
    $wasPartial=(Test-Path -LiteralPath $BackupDir)
    Invoke-OriginalBackupCore -FillMissingOnly:$wasPartial
    if(-not(Test-OriginalBackupComplete)){
        Write-AppLog 'Otomatik yedek tamamlanamadı: i18n_en.jar doğrulanamadı.' 'HATA'
        return $false
    }
    $msg=if($wasPartial){'Eksik orijinal yedek, temiz oyun dosyalarından otomatik tamamlandı.'}else{'İlk kurulum için orijinal oyun dosyaları otomatik yedeklendi.'}
    Write-AppLog "$msg | $BackupDir"
    [Windows.Forms.MessageBox]::Show("$msg`n`n$BackupDir",'Otomatik yedek alındı','OK','Information')|Out-Null
    return $true
}

function Backup-Original {
    if(-not(Ensure-WakfuGameDir)){return}
    if(Test-OriginalBackupComplete){
        if(-not(Test-Path -LiteralPath $OriginalGuiJar) -and (Test-Path -LiteralPath $InstalledGuiJar)){Copy-Item -LiteralPath $InstalledGuiJar -Destination $OriginalGuiJar}
        if(-not(Test-Path -LiteralPath $OriginalClientJar) -and (Test-Path -LiteralPath $InstalledClientJar)){Copy-Item -LiteralPath $InstalledClientJar -Destination $OriginalClientJar}
        if(-not(Test-Path -LiteralPath $OriginalDataJar) -and (Test-Path -LiteralPath $InstalledDataJar)){Copy-Item -LiteralPath $InstalledDataJar -Destination $OriginalDataJar}
        Sync-MirrorOriginalBackup
        [Windows.Forms.MessageBox]::Show("Orijinal yedek zaten var ve güvenlik için üzerine yazılmadı:`n$BackupDir",'Yedek mevcut','OK','Information') | Out-Null
        return
    }
    if(-not(Test-IsCleanInstalledGame)){
        [Windows.Forms.MessageBox]::Show('Yedeklenecek temiz İngilizce oyun dosyası bulunamadı. Oyun kapalı ve Türkçe yama kurulu değil olmalıdır.','Temiz oyun gerekli','OK','Warning') | Out-Null
        return
    }
    Invoke-OriginalBackupCore -FillMissingOnly:(Test-Path -LiteralPath $BackupDir)
    [Windows.Forms.MessageBox]::Show("Orijinal dil paketleri güvenli biçimde yedeklendi:`n$BackupDir",'Yedek tamam','OK','Information') | Out-Null
}

function Restore-Original([switch]$NoConfirm) {
    if(-not(Ensure-WakfuGameDir)){return}
    if (-not (Test-Path -LiteralPath (Join-Path $BackupDir 'i18n.jar'))) {
        [Windows.Forms.MessageBox]::Show('Geri yüklenecek orijinal yedek bulunamadı. Önce Orijinali Yedekle düğmesini kullanın.','Yedek yok','OK','Warning') | Out-Null
        return
    }
    if(-not$NoConfirm){$answer = [Windows.Forms.MessageBox]::Show('Yedeklenen orijinal dil dosyaları oyuna geri yüklensin mi? Oyun ve launcher kapalı olmalıdır.','Geri yükleme onayı','YesNo','Question');if ($answer -ne [Windows.Forms.DialogResult]::Yes) { return }}
    $destDir = Join-Path $GameDir 'contents\i18n'
    $safeBackup = $BackupDir.Replace("'","''"); $safeDestDir = $destDir.Replace("'","''")
    $safeGuiBackup=$OriginalGuiJar.Replace("'","''");$safeGuiDest=$InstalledGuiJar.Replace("'","''")
    $safeClientBackup=$OriginalClientJar.Replace("'","''");$safeClientDest=$InstalledClientJar.Replace("'","''")
    $safeDataBackup=$OriginalDataJar.Replace("'","''");$safeDataDest=$InstalledDataJar.Replace("'","''")
    $cmd = "Get-ChildItem -LiteralPath '$safeBackup' -Filter 'i18n*.jar' | ForEach-Object { Copy-Item -LiteralPath `$_.FullName -Destination (Join-Path '$safeDestDir' `$_.Name) -Force }; if(Test-Path -LiteralPath '$safeGuiBackup'){Copy-Item -LiteralPath '$safeGuiBackup' -Destination '$safeGuiDest' -Force}; if(Test-Path -LiteralPath '$safeClientBackup'){Copy-Item -LiteralPath '$safeClientBackup' -Destination '$safeClientDest' -Force}; if(Test-Path -LiteralPath '$safeDataBackup'){Copy-Item -LiteralPath '$safeDataBackup' -Destination '$safeDataDest' -Force}"
    try {
        $p = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList @('-NoProfile','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-Command',$cmd)
        if ($p.ExitCode -ne 0) { throw "Geri yükleme işlemi $($p.ExitCode) koduyla bitti." }
        if(Test-Path -LiteralPath $InstallStateFile){Remove-Item -LiteralPath $InstallStateFile -Force -ErrorAction SilentlyContinue}
        [Windows.Forms.MessageBox]::Show('Orijinal dil dosyaları geri yüklendi.','Geri yükleme tamam','OK','Information') | Out-Null
    } catch { [Windows.Forms.MessageBox]::Show("Geri yükleme tamamlanamadı:`n$($_.Exception.Message)",'Hata','OK','Error') | Out-Null }
}

function Clear-InstalledGameTranslation {
    $answer=[Windows.Forms.MessageBox]::Show("Oyundaki Türkçe yama dosyaları temizlenecek ve yedekteki orijinal oyun dosyaları geri yüklenecek.`n`nÇeviri projeniz ve çeviri belleğiniz SİLİNMEYECEK.`nOyun ve Ankama Launcher kapalı olmalıdır.`n`nDevam edilsin mi?",'Oyundaki yamayı temizle','YesNo','Warning')
    if($answer-ne[Windows.Forms.DialogResult]::Yes){return}
    Restore-Original -NoConfirm
    foreach($generated in @($OutputJar,$OutputGuiJar,$OutputClientJar,$OutputDataJar)){if(Test-Path -LiteralPath $generated){Remove-Item -LiteralPath $generated -Force -ErrorAction SilentlyContinue}}
    Write-AppLog 'Oyundaki Türkçe yama temizlendi; orijinal oyun dosyaları geri yüklendi. Çeviri belleği korundu.'
    $status.Text='Oyundaki Türkçe yama temizlendi; çeviri projesi korundu.'
}

function Get-FormatTokens([string]$text) {
    if ([string]::IsNullOrEmpty($text)) { return @() }
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

function Get-ConditionalHeaders([string]$text) {
    $headers=New-Object Collections.Generic.List[string]
    $headerPattern=New-Object Text.RegularExpressions.Regex('\G\{\[[^\]]+\]\?',[Text.RegularExpressions.RegexOptions]::CultureInvariant)
    for($start=0;$start-lt$text.Length;$start++){
        if($text[$start]-ne'{'){continue}
        $header=$headerPattern.Match($text,$start)
        if(-not$header.Success){continue}
        $depth=1;$separatorFound=$false;$closed=$false
        for($i=$header.Index+$header.Length;$i-lt$text.Length;$i++){
            $char=$text[$i]
            if($char-eq'{'){$depth++}
            elseif($char-eq'}'){$depth--;if($depth-eq0){$closed=$true;break}}
            elseif($char-eq':'-and$depth-eq1){$separatorFound=$true}
        }
        if(-not$closed-or-not$separatorFound){return $null}
        [void]$headers.Add($header.Value)
    }
    return @($headers)
}

function Test-FormatTokens([string]$source, [string]$translated) {
    $a = @(Get-FormatTokens $source)
    $b = @(Get-FormatTokens $translated)
    $exact=$a.Count-eq$b.Count
    if($exact){for($i=0;$i-lt$a.Count;$i++){if($a[$i]-cne$b[$i]){$exact=$false;break}}}
    if($exact){return $true}

    # İç içe koşullarda çevrilebilir metnin doğal ?/: işaretlerini biçim
    # kodu sanmamak için Python denetçisiyle aynı yapısal karşılaştırma.
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
    foreach($marker in @('{','}')){
        $countA=[regex]::Matches($source,[regex]::Escape($marker)).Count
        $countB=[regex]::Matches($translated,[regex]::Escape($marker)).Count
        if($countA-ne$countB){return $false}
    }
    $conditionsA=@(Get-ConditionalHeaders $source);$conditionsB=@(Get-ConditionalHeaders $translated)
    if($null-eq$conditionsA-or$null-eq$conditionsB-or$conditionsA.Count-ne$conditionsB.Count){return $false}
    for($i=0;$i-lt$conditionsA.Count;$i++){if($conditionsA[$i]-cne$conditionsB[$i]){return $false}}
    return $true
}

function Test-TranslationCompleteness([string]$source,[string]$translated) {
    if([string]::IsNullOrWhiteSpace($source)-or[string]::IsNullOrWhiteSpace($translated)){return $false}
    $cleanSource=[regex]::Replace($source,'\{[^{}]*\}|\\[ntr]|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|<[^>]*>|%[A-Za-z_][A-Za-z0-9_.-]*%',' ')
    $cleanTranslated=[regex]::Replace($translated,'\{[^{}]*\}|\\[ntr]|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|<[^>]*>|%[A-Za-z_][A-Za-z0-9_.-]*%',' ')
    $sourceWords=[regex]::Matches($cleanSource,"[\p{L}']+").Count
    $translatedWords=[regex]::Matches($cleanTranslated,"[\p{L}']+").Count
    # Türkçe eklemeli bir dil olduğu için aynı anlam İngilizceden belirgin
    # biçimde daha az sözcükle kurulabilir. %25 altı gerçek kesilmeleri yakalar.
    if($sourceWords-ge8-and$translatedWords-lt[Math]::Ceiling($sourceWords*0.25)){return $false}
    if($cleanSource.Length-ge45-and$cleanTranslated.Length-lt[Math]::Ceiling($cleanSource.Length*0.35)){return $false}
    return $true
}

function Get-TranslationProvider([string]$key,[string]$source){
    if(Test-IsForcedEnglishNameKey $key){return 'ORIJINAL_WAKFU_ADI'}
    if($script:TermKeys.ContainsKey($key)-and-not$script:ManualRepairs.ContainsKey($key)){return 'TERIM_ANAHTARI'}
    if(Test-IsProtectedNameKey $key){return 'ORIJINAL_WAKFU_ADI'}
    if((Test-IsWorldTermOverrideKey $key)-and$script:TermValues.ContainsKey($source)){return 'TERIM_SOZLUGU'}
    if($script:ManualRepairs.ContainsKey($key)){return 'ELLE_DOGRULANMIS_DUZELTME'}
    if($script:TermKeys.ContainsKey($key)){return 'TERIM_ANAHTARI'}
    if($script:TermValues.ContainsKey($source)){return 'TERIM_SOZLUGU'}
    if($script:Translations.ContainsKey($key)){return 'CEVIRI_BELLEGI'}
    return 'YOK'
}

function Get-QualityAnalysis($entry,[string]$value){
    $key=[string]$entry.Key;$source=[string]$entry.English
    if($script:CanonicalUiTranslations.ContainsKey($key)-and$value-cne[string]$script:CanonicalUiTranslations[$key]){return [pscustomobject]@{Status='YANLIS_TERIM';Reason="Doğrulanmış arayüz karşılığı kullanılmalı: $($script:CanonicalUiTranslations[$key])";Issue=$true}}
    $questionSafeValue=[regex]::Replace($value,'https?://\S+',' ')
    if($questionSafeValue-match"(?iu)[^\W\d_]\?'[a-zçğıöşü]"){return [pscustomobject]@{Status='BOZUK_KODLAMA';Reason="Soru işareti Türkçe ekin önüne sızmış; kaynak ad ve ek yeniden kurulmalı";Issue=$true}}
    if($questionSafeValue-match'(?iu)[^\W\d_]\?[^\W\d_]'){return [pscustomobject]@{Status='BOZUK_NOKTALAMA';Reason="Soru işaretinden sonra boşluk eksik veya Türkçe karakter '?' işaretine bozulmuş";Issue=$true}}
    if($source-match'(?i)(?:action|skill|specialty|experience|movement|wakfu|mastery|agility|ability|aptitude|characteristic|conquest|score|citizenship|health|life)\s+points?|\bpoints?\s+(?:to distribute|available|remaining|earned|gained|lost|spent|bonus|penalty)'-and$value-match'(?i)\b(?:nokta\w*|skor\w*)\b'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason="Oyun mekaniğindeki point/points terimi 'puan' olarak çevrilmeli";Issue=$true}}
    if($value-match'(?i)(?:\[#\d+\]|\b\d+)\s+puanlar\b'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason="Sayıdan sonra gereksiz çoğul kullanılmış; 'puan' olmalı";Issue=$true}}
    if($value-match'(?i)\bpenaltiler\b'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason="Penalty terimi Türkçede 'ceza' olarak çevrilmeli";Issue=$true}}
    if($value-match'(?i)\b(?:monstrolar?|monstre|monsta)\b'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason='Canavar terimi bozuk makine çevirisiyle yazılmış';Issue=$true}}
    if($value-match'(?i)\bdönüş\s+(?:başına|sonunda|başlangıcında)\b'-and$source-match'(?i)\bturn\b'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason='Turn sözcüğü tur yerine dönüş olarak çevrilmiş';Issue=$true}}
    if($value-match'(?i)\b(?:heceler?|yazılımlar?)\b'-and$source-match'(?i)\bspells?\b'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason='Spell sözcüğü yanlışlıkla hece/yazılım olarak çevrilmiş';Issue=$true}}
    if($value-match'(?i)\bharvest\w*\b'-and$value.Trim()-cne$source.Trim()){return [pscustomobject]@{Status='INGILIZCE_KALINTISI';Reason='Hasat/toplama metninde çevrilmemiş Harvest kökü kaldı';Issue=$true}}
    if($source-match'(?i)\bdragoturkey\b'-and$value-match'(?i)dragotürkiye|drag\s+turk\w*|drag\s+turkey|dragot(?:uck|uğ|uş)\w*|sürükleyici\s+hindi|atlı\s+hindi|\bhindi(?:''|y|n|ler|nin|yi|ye)'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason='Dragoturkey özel yaratık adı makine çevirisine uğramış';Issue=$true}}
    if($source-match'(?i)(?:^|\\n)\s*-?\s*Defeat\s+[^-\s]'-and$value-match'(?i)(?:^|\\n)\s*-?\s*Yenilgi\s+'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason="Görev emri olan Defeat, ad biçimindeki 'Yenilgi' değil '-i yen' olarak çevrilmeli";Issue=$true}}
    if($source-match'(?i)^\s*Kill\s+[^,!]'-and$value-match'(?i)^\s*Öldür\s+'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason="Kill görevi Türkçede hedef önce, '-i öldür' yüklemi sonda olacak biçimde yazılmalı";Issue=$true}}
    if($source-match'(?i)^\s*(?:Get|Take)\b'-and$value-match'(?i)^\s*Al şunu\.'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason="Get/Take görevi bağlamsız 'Al şunu' kalıbına dönüşmüş";Issue=$true}}
    if($value-match'(?i)\b(?:bir|için)\s+a\b'){return [pscustomobject]@{Status='INGILIZCE_KALINTISI';Reason="Belirsiz tanımlık 'a' bozuk İngilizce-Türkçe karışımı olarak kalmış";Issue=$true}}
    if($value-match'(?i)\b(?:Experienceve|Hasarve|Eşyalar?ve|puanve|seviyeve)\b'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason='İngilizce sözcük veya Türkçe bağlaç önceki sözcükle hatalı biçimde birleşmiş';Issue=$true}}
    if($source-match'(?i)\b(?:account|guild|house|manor|treasure|golden|large|big|hidden|locked|mystery|reward|vault)\s+chests?\b|\bchests?\s+(?:locked|room|contains?|contents?|capacity|slots?|rewards?|is\s+(?:empty|open|closed|locked))\b|\b(?:open|unlock|find|search|access|examine|interact\s+with|remove\s+.+?\s+from|deposit\s+.+?\s+in|take\s+.+?\s+from|get\s+.+?\s+from)\s+(?:the\s+|a\s+)?chests?\b'-and$value-match'(?i)\bgöğs'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason='Depolama/hazine anlamındaki chest sözcüğü göğüs değil, sandık olmalı';Issue=$true}}
    if($value-match'(?i)yazılım'-and$source-match'(?i)\brunes?\b'){return [pscustomobject]@{Status='YANLIS_TERIM';Reason='Rune sözcüğü rün yerine yazılım olarak çevrilmiş';Issue=$true}}
    $reviewedLore=@('chat.help','quest.DD.cambriolage.rules.desc03','content.4.4718','content.13.380056','content.24.-1657','content.24.-1656','content.24.-1655','content.24.-1654','content.67.445','content.67.606','content.67.609','content.67.849')
    if($reviewedLore-contains$key-and-not[string]::IsNullOrWhiteSpace($value)){
        if(-not(Test-FormatTokens $source $value)){return [pscustomobject]@{Status='BICIM_HATASI';Reason='Değişken, etiket veya koşul kodları kaynakla eşleşmiyor';Issue=$true}}
        return [pscustomobject]@{Status='CEVRILDI';Reason='İnsan denetimli çeviri; Wakfu büyü ve özel adları bilinçli korundu';Issue=$false}
    }
    if($key-eq'quest.chuchoku.04.06'){return [pscustomobject]@{Status='TEKNIK_KORUNAN';Reason='Karakter adıyla yapılan kısa hitap bilinçli korundu';Issue=$false}}
    if($key-eq'content.67.659'-and$value-ceq$source){return [pscustomobject]@{Status='TEKNIK_KORUNAN';Reason='Ters yazılmış oyun içi bilmece özgün biçimiyle korundu';Issue=$false}}
    if(Test-IsProtectedNameKey $key){return [pscustomobject]@{Status='KORUNAN_AD';Reason='Wakfu özel adı bilinçli olarak İngilizce tutuldu';Issue=$false}}
    if([string]::IsNullOrWhiteSpace($value)){
        $sourceLetterCount=[regex]::Matches($source,'\p{L}').Count
        $symbolHeavyTechnical=($source.Length-ge12-and$sourceLetterCount-le6-and$source-notmatch'[A-Za-z]{2,}')
        if($source-match'^(https?://|www\.)' -or $source-notmatch'\p{L}' -or $symbolHeavyTechnical -or ($source.Length-le12 -and $source-match'^[A-Z0-9_.+/% -]+$')){
            return [pscustomobject]@{Status='TEKNIK_KORUNAN';Reason='Kısaltma, sayı, adres veya teknik kod';Issue=$false}
        }
        return [pscustomobject]@{Status='EKSIK';Reason='Çeviri üretilmemiş';Issue=$true}
    }
    $visibleSource=[regex]::Replace($source,'\{[^{}]*\}|\[[^\]]*\]|<[^>]*>|\\[ntr]',' ').Trim()
    $sourceLetters=[regex]::Matches($visibleSource,'\p{L}').Count
    if($sourceLetters-eq0 -or $visibleSource-match'^[A-Z0-9_.+/% -]{1,12}$' -or $visibleSource-match'^(https?://|www\.)'){
        return [pscustomobject]@{Status='TEKNIK_KORUNAN';Reason='Kısaltma, sayı, adres veya teknik kod';Issue=$false}
    }
    if(-not(Test-FormatTokens $source $value)){return [pscustomobject]@{Status='BICIM_HATASI';Reason='Değişken, etiket veya koşul kodları kaynakla eşleşmiyor';Issue=$true}}
    if($value.Trim()-ceq$source.Trim()){
        $letters=[regex]::Matches(([regex]::Replace($source,'\{[^{}]*\}|\[[^\]]*\]|<[^>]*>|\\[ntr]',' ')),'\p{L}').Count
        $technical=($source-match'^[A-Z0-9_.+/% -]{1,12}$' -or $letters-eq0)
        if($technical){return [pscustomobject]@{Status='TEKNIK_KORUNAN';Reason='Kısaltma, sayı veya teknik kod';Issue=$false}}
        return [pscustomobject]@{Status='INGILIZCE_KALDI';Reason='Çevrilebilir metin İngilizceyle aynı kaldı';Issue=$true}
    }
    if(-not(Test-TranslationCompleteness $source $value)){return [pscustomobject]@{Status='EKSIK_CUMLE';Reason='Çeviri kaynağa göre aşırı kısa veya cümle atlanmış';Issue=$true}}
    if($value-cmatch'Ã|Ä|Å|â€|�'){return [pscustomobject]@{Status='KODLAMA_HATASI';Reason='Bozuk karakter dizisi bulundu';Issue=$true}}
    if($value-match'(?i)\b(yanlız|herşey|birşey|hiçbirşey|şuan|orjinal|değilmi|yalnış|ne oldu\d+|yeterince iyileştim|kullanıcı adınız|satın alma fırsatı|sıfırsa sahip|zerosa sahip|görüşüm açıldı|pencerem ekleyemezsiniz|pencerem kayıt|kilitedeki|onaylıyormusunuz|dağıttiniz|güvenlikler|emin misiniz ki|pazar yeri[\x27\u2019]de|savaş alanı katıl|satırsınız|yapı et)\b' -or $value-match'(?i)\b\p{L}+(?:y?[ıiuü])\s+sahip\b'){return [pscustomobject]@{Status='YAZIM_ANLAM_SUPHESI';Reason="Şüpheli ifade: $($Matches[0])";Issue=$true}}
    if($value-match'(?i)^\s*(translation|turkish|türkçe|çeviri|here is|işte)\s*:'){return [pscustomobject]@{Status='MODEL_ACIKLAMASI';Reason='Model yalnız çeviri yerine açıklama/etiket ekledi';Issue=$true}}
    $visible=[regex]::Replace($value,'\{[^{}]*\}|\[[^\]]*\]|<[^>]*>|\\[ntr]',' ')
    $englishHits=[regex]::Matches($visible,'(?i)\b(the|and|you|your|with|from|into|must|cannot|available|unavailable|default|damage|mastery|characteristics|recommended|rarity|pockets|page|click|level|search|current|challenge|item|items|build|resistance|earth|water|fire|air|exact|ones|following|remove|purchase|sale|window|offer|remaining|team|are|is|was|were|has|have|reach|access|juice|key(?!-keeper))\b').Count
    if($englishHits-ge1){return [pscustomobject]@{Status='INGILIZCE_KALINTISI';Reason='Çeviri içinde yaygın İngilizce sözcük kaldı';Issue=$true}}
    return [pscustomobject]@{Status='CEVRILDI';Reason='Biçim ve temel kalite denetimlerinden geçti';Issue=$false}
}

function Convert-ToTsvField([string]$value){
    if($null-eq$value){return ''}
    return ($value-replace'\\','\\\\'-replace"`t",'\t'-replace"`r",'\r'-replace"`n",'\n')
}

function Write-DiagnosticBundle([string]$stage){
    if((Test-Path -LiteralPath $AuditPython)-and(Test-Path -LiteralPath $AuditWorker)){
        try{
            $auditArgs=@('--source-jar',$SourceJar,'--project',$ProjectFile,'--terminology',$TerminologyFile,'--live-log',$LiveTsv,'--output-dir',$LogDir,'--stage',$stage)
            $auditResult=@(& $AuditPython $AuditWorker @auditArgs 2>&1)
            if($LASTEXITCODE-ne0){throw ($auditResult-join[Environment]::NewLine)}
            $auditLine=[string]($auditResult|Where-Object{[string]$_-like'AUDIT|*'}|Select-Object -Last 1)
            if(-not(Test-Path -LiteralPath $StatusTsv)-or-not(Test-Path -LiteralPath $IssuesTsv)){throw 'Hızlı tanı dosyaları üretilemedi.'}
            Write-AppLog "Hızlı tanı paketi güncellendi | Aşama=$stage | Sonuç=$auditLine"
            return
        }catch{Write-AppLog "Hızlı tanı kullanılamadı; PowerShell denetimine geçiliyor | $($_.Exception.Message)" 'TANI-UYARI'}
    }
    try{
        $encoding=New-Object Text.UTF8Encoding($true)
        $statusTemp=$StatusTsv+'.tmp';$issuesTemp=$IssuesTsv+'.tmp'
        $statusWriter=New-Object IO.StreamWriter($statusTemp,$false,$encoding)
        $issueWriter=New-Object IO.StreamWriter($issuesTemp,$false,$encoding)
        $header="Anahtar`tKategori`tDurum`tYontem`tSon_Guncelleme`tIngilizce`tTurkce`tNeden`tBicim_OK`tButunluk_OK"
        $statusWriter.WriteLine($header);$issueWriter.WriteLine($header)
        $counts=@{};$issueCount=0
        try{
            foreach($entry in $script:Entries){
                $key=[string]$entry.Key;$source=[string]$entry.English;$category=Get-WakfuTextCategory $entry
                $value=if(Test-IsProtectedNameKey $key){$source}else{Get-EntryTranslation $entry}
                $analysis=Get-QualityAnalysis $entry $value
                if(-not$counts.ContainsKey($analysis.Status)){$counts[$analysis.Status]=0};$counts[$analysis.Status]++
                $formatOk=Test-FormatTokens $source $value;$complete=Test-TranslationCompleteness $source $value
                $fields=@($key,$category,$analysis.Status,(Get-TranslationProvider $key $source),'',$source,$value,$analysis.Reason,[string]$formatOk,[string]$complete)|ForEach-Object{Convert-ToTsvField ([string]$_)}
                $row=$fields-join"`t";$statusWriter.WriteLine($row)
                if($analysis.Issue){$issueWriter.WriteLine($row);$issueCount++}
            }
        }finally{$statusWriter.Dispose();$issueWriter.Dispose()}
        Move-Item -LiteralPath $statusTemp -Destination $StatusTsv -Force
        Move-Item -LiteralPath $issuesTemp -Destination $IssuesTsv -Force
        $summary=New-Object Collections.Generic.List[string]
        $summary.Add('WAKFU TÜRKÇE ÇEVİRİ DURUMU');$summary.Add("Aşama: $stage");$summary.Add("Tarih: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')");$summary.Add("Toplam metin: $($script:Entries.Count)");$summary.Add("İncelenmesi gereken: $issueCount");$summary.Add('')
        foreach($name in($counts.Keys|Sort-Object)){$summary.Add("${name}: $($counts[$name])")}
        $summary.Add('');$summary.Add("Tüm satırlar: $StatusTsv");$summary.Add("Sorunlu/eksik satırlar: $IssuesTsv");$summary.Add("Olay ve hata günlüğü: $LogFile")
        [IO.File]::WriteAllLines($DiagnosticSummary,$summary,$encoding)
        Write-AppLog "Tanı paketi güncellendi | Aşama=$stage | Toplam=$($script:Entries.Count) | Sorun=$issueCount"
    }catch{Write-AppLog $_.Exception.ToString() 'TANI-PAKETI-HATA'}
}

function Enforce-ProtectedNames {
    $removed=0
    foreach($entry in $script:Entries){$key=[string]$entry.Key;if((Test-IsProtectedNameKey $key)-and$script:Translations.ContainsKey($key)){[void]$script:Translations.Remove($key);$removed++}}
    if($removed-gt0){Save-Project;Write-AppLog "Korunan Wakfu adlarından eski çeviri kaldırıldı | Adet=$removed"}
    return $removed
}

function Invoke-QualityCheck([switch]$Silent) {
    Save-Current; Save-Project; Load-Terminology
    $report = New-Object System.Collections.Generic.List[object]
    $counts=@{}
    foreach($entry in $script:Entries) {
        $key=[string]$entry.Key; $source=[string]$entry.English
        if($key-in@('content.67.660','content.156.7')){continue}
        $value=Get-EntryTranslation $entry
        $analysis=Get-QualityAnalysis $entry $value
        if(-not$counts.ContainsKey($analysis.Status)){$counts[$analysis.Status]=0};$counts[$analysis.Status]++
        if($analysis.Issue){$report.Add([pscustomobject]@{Tur=$analysis.Status;Kategori=(Get-WakfuTextCategory $entry);Anahtar=$key;Ingilizce=$source;Turkce=$value;Aciklama=$analysis.Reason})}
    }
    $reportPath=Join-Path $LogDir 'Wakfu_Kalite_Kontrol_Raporu.csv'
    $summaryPath=Join-Path $LogDir 'Wakfu_Kalite_Kontrol_Ozeti.txt'
    $report | Export-Csv -LiteralPath $reportPath -NoTypeInformation -Encoding UTF8
    $summary=@(
        'WAKFU TÜRKÇE KALİTE KONTROLÜ',
        "Tarih: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "Taranan ana metin: $($script:Entries.Count)",
        "İncelenmesi gereken: $($report.Count)",
        'Özel ad koruması: Zorunlu (eşya, yetenek, buff/durum, yaratık, NPC ve sınıf adları)',
        '',
        (($counts.Keys|Sort-Object|ForEach-Object{('{0}: {1}'-f$_,$counts[$_])})-join [Environment]::NewLine),
        '',
        'Not: Korunan adlar sorun sayılmaz; açıklamaları doğal Türkçe çevrilir.'
    )
    [IO.File]::WriteAllLines($summaryPath,$summary,(New-Object Text.UTF8Encoding($true)))
    Write-DiagnosticBundle 'Kalite kontrolü'
    $status.Text="Kalite kontrolü tamamlandı: $($report.Count) inceleme kaydı"
    if(-not$Silent){[Windows.Forms.MessageBox]::Show("Kalite kontrolü tamamlandı.`n`nİncelenmesi gereken: $($report.Count)`n`nRapor: $reportPath`nSorunlu satırlar: $IssuesTsv",'Kalite Kontrolü','OK','Information')|Out-Null}
}

function Google-TranslateAll {
    Save-Current
    $targets = @($script:Entries | Where-Object { Test-IsUntranslated $_ })
    if ($targets.Count -eq 0) {
        [Windows.Forms.MessageBox]::Show('Bütün metinler zaten çevrilmiş.','Google Çeviri','OK','Information') | Out-Null
        return
    }
    $answer = [Windows.Forms.MessageBox]::Show("Yerel modelin İngilizce bıraktığı veya boş olan $($targets.Count) metin Google ile düzeltilecek.`nAynı anda $GoogleWorkerCount işçi kullanılacak. İlerleme düzenli kaydedilir.`n`nDevam edilsin mi?",'İngilizce kalanları Google ile düzelt','YesNo','Question')
    if ($answer -ne [Windows.Forms.DialogResult]::Yes) { return }
    Write-TranslationLogSnapshot 'Google çeviri başladı' "Hedef=$($targets.Count); İşçi=$GoogleWorkerCount"

    $script:CancelTranslation = $false
    $btnGoogle.Enabled = $false
    $btnStop.Enabled = $true
    $pool = [RunspaceFactory]::CreateRunspacePool(1,$GoogleWorkerCount)
    $pool.Open()
    $jobs = New-Object System.Collections.Generic.List[object]
    $worker = {
        param($key,$source)
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $encoded = [Uri]::EscapeDataString($source)
            $uri = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=tr&dt=t&q=$encoded"
            $response = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 30
            $translated = (($response[0] | ForEach-Object { [string]$_[0] }) -join '')
            [pscustomobject]@{Key=$key; Source=$source; Translation=$translated; Error=''}
        } catch {
            [pscustomobject]@{Key=$key; Source=$source; Translation=''; Error=$_.Exception.Message}
        }
    }
    try {
        $next=0; $done=0; $saved=0; $formatErrors=0; $requestErrors=0; $nextSave=250
        while (($next -lt $targets.Count -and -not $script:CancelTranslation) -or $jobs.Count -gt 0) {
            while (-not $script:CancelTranslation -and $next -lt $targets.Count -and $jobs.Count -lt $GoogleWorkerCount) {
                $item = $targets[$next]
                $ps = [PowerShell]::Create()
                $ps.RunspacePool = $pool
                [void]$ps.AddScript($worker).AddArgument($item.Key).AddArgument($item.English)
                $handle = $ps.BeginInvoke()
                $jobs.Add([pscustomobject]@{ PowerShell=$ps; Handle=$handle })
                $next++
            }
            for ($i=$jobs.Count-1; $i -ge 0; $i--) {
                $job=$jobs[$i]
                if (-not $job.Handle.IsCompleted) { continue }
                try {
                    $result = @($job.PowerShell.EndInvoke($job.Handle))[0]
                    if ($result.Error -or [string]::IsNullOrWhiteSpace($result.Translation)) { $requestErrors++ }
                    elseif (Test-FormatTokens $result.Source $result.Translation) {
                        $script:Translations[[string]$result.Key] = [string]$result.Translation
                        Write-LiveTranslationRecord ([string]$result.Key) ([string]$result.Source) ([string]$result.Translation) 'OTOMATIK_GOOGLE' 'KAYDEDILDI' ''
                        $saved++
                    } else { $formatErrors++ }
                } catch { $requestErrors++ }
                finally { $job.PowerShell.Dispose(); $jobs.RemoveAt($i); $done++ }
            }
            if ($done -ge $nextSave) { Sync-VisibleTranslations; Save-Project; while ($nextSave -le $done) { $nextSave += 250 } }
            $status.Text = "Tümü çevriliyor: $done / $($targets.Count) — kaydedilen: $saved — çalışan işçi: $($jobs.Count)"
            [Windows.Forms.Application]::DoEvents()
            if ($jobs.Count -gt 0) { Start-Sleep -Milliseconds 60 }
        }
        Save-Project
        Initialize-FastSearchIndex
        Refresh-Results
        Write-TranslationLogSnapshot 'Google çeviri bitti' "İşlenen=$done; Kaydedilen=$saved; BiçimAtlanan=$formatErrors; ServisHatası=$requestErrors; Durduruldu=$($script:CancelTranslation)" $true
        $resultTitle = if ($script:CancelTranslation) { 'Çeviri durduruldu' } else { 'Google Çeviri tamamlandı' }
        [Windows.Forms.MessageBox]::Show("$resultTitle.`nİşlenen: $done / $($targets.Count)`nKaydedilen: $saved`nBiçim işareti değiştiği için atlanan: $formatErrors`nBağlantı/servis hatası: $requestErrors`n`nKaydedilenler sonraki çalıştırmada tekrar çevrilmez.",$resultTitle,'OK','Information') | Out-Null
    } finally {
        foreach ($job in $jobs) { try { $job.PowerShell.Stop(); $job.PowerShell.Dispose() } catch {} }
        $pool.Close(); $pool.Dispose(); $btnGoogle.Enabled = $true; $btnStop.Enabled = $false
    }
}

function Invoke-GpuSetupProcess([string]$file,[string]$arguments,[string]$stage) {
    $status.Text=$stage
    [Windows.Forms.Application]::DoEvents()
    $psi=New-Object Diagnostics.ProcessStartInfo
    $psi.FileName=$file; $psi.Arguments=$arguments; $psi.WorkingDirectory=$GpuRuntimeDir
    $psi.UseShellExecute=$false; $psi.CreateNoWindow=$true; $psi.WindowStyle='Hidden'
    $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true
    $process=New-Object Diagnostics.Process; $process.StartInfo=$psi
    if(-not $process.Start()){throw "$stage başlatılamadı."}
    $outTask=$process.StandardOutput.ReadToEndAsync();$errTask=$process.StandardError.ReadToEndAsync()
    while(-not $process.HasExited){[Windows.Forms.Application]::DoEvents();Start-Sleep -Milliseconds 200}
    $output=$outTask.Result+"`n"+$errTask.Result;$exitCode=$process.ExitCode;$process.Dispose()
    if($exitCode-ne0){
        if($output.Length-gt1800){$output=$output.Substring($output.Length-1800)}
        throw "$stage başarısız oldu (kod $exitCode).`n`n$output"
    }
}

function Ensure-GpuRuntime {
    if((Test-Path -LiteralPath $GpuPython) -and (Test-Path -LiteralPath $GpuWorker)){
        & $GpuPython -c "import os,torch; os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__),'lib')); import llama_cpp,huggingface_hub,transformers,sentencepiece,sacremoses" 2>$null
        if($LASTEXITCODE-eq0){return $true}
    }
    $answer=[Windows.Forms.MessageBox]::Show("GPU çeviri bileşenleri otomatik bulunamadı.`n`nEVET: Bileşenleri internetten indir (yaklaşık 8-15 GB).`nHAYIR: Bilgisayardaki mevcut gpu_runtime klasörünü seç.`nİPTAL: İşlemi kapat.",'GPU bileşenleri','YesNoCancel','Question')
    if($answer-eq[Windows.Forms.DialogResult]::Cancel){return $false}
    if($answer-eq[Windows.Forms.DialogResult]::No){
        $picker=New-Object Windows.Forms.FolderBrowserDialog
        $picker.Description='İçinde venv\Scripts\python.exe bulunan gpu_runtime klasörünü seçin.'
        if($picker.ShowDialog()-ne[Windows.Forms.DialogResult]::OK){return $false}
        $chosen=$picker.SelectedPath
        if(-not(Test-Path -LiteralPath (Join-Path $chosen 'venv\Scripts\python.exe'))){
            [Windows.Forms.MessageBox]::Show('Seçilen klasörde venv\Scripts\python.exe bulunamadı. Lütfen doğrudan gpu_runtime klasörünü seçin.','Geçersiz GPU klasörü','OK','Error')|Out-Null
            return $false
        }
        $script:GpuRuntimeDir=$chosen;$script:GpuPython=Join-Path $chosen 'venv\Scripts\python.exe'
        [IO.File]::WriteAllText($GpuPathFile,$chosen,(New-Object Text.UTF8Encoding($false)))
        & $script:GpuPython -c "import os,torch; os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__),'lib')); import llama_cpp,huggingface_hub,transformers,sentencepiece,sacremoses" 2>$null
        if($LASTEXITCODE-ne0){throw 'Seçilen GPU ortamındaki bileşenler eksik veya çalışmıyor.'}
        $gpuText.Text='NVIDIA GPU — Hızlı OPUS + Qwen kalite düzeltme';$gpuPathTip=New-Object Windows.Forms.ToolTip;$gpuPathTip.SetToolTip($gpuText,"Bulunan GPU ortamı: $chosen")
        return $true
    }
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    New-Item -ItemType Directory -Path $GpuRuntimeDir -Force|Out-Null
    $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($GpuRuntimeDir))
    if($drive.AvailableFreeSpace-lt12GB){
        $free=[Math]::Round($drive.AvailableFreeSpace/1GB,1)
        throw "GPU bileşenleri için yeterli boş alan yok. En az 12 GB önerilir; kullanılabilir alan: $free GB."
    }
    $uvExe=Join-Path $GpuRuntimeDir 'uv.exe'
    if(-not(Test-Path -LiteralPath $uvExe)){
        $zipPath=Join-Path $GpuRuntimeDir 'uv-download.zip';$extractPath=Join-Path $GpuRuntimeDir 'uv-download'
        $status.Text='GPU kurulumu: güvenli Python yöneticisi indiriliyor…';[Windows.Forms.Application]::DoEvents()
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile $zipPath
        if(Test-Path -LiteralPath $extractPath){Remove-Item -LiteralPath $extractPath -Recurse -Force}
        [IO.Compression.ZipFile]::ExtractToDirectory($zipPath,$extractPath)
        $downloadedUv=Get-ChildItem -LiteralPath $extractPath -Filter uv.exe -Recurse|Select-Object -First 1
        if(-not $downloadedUv){throw 'İndirilen pakette uv.exe bulunamadı.'}
        Copy-Item -LiteralPath $downloadedUv.FullName -Destination $uvExe -Force
        Remove-Item -LiteralPath $zipPath -Force;Remove-Item -LiteralPath $extractPath -Recurse -Force
    }
    Invoke-GpuSetupProcess $uvExe "venv `"$($GpuRuntimeDir)\venv`" --python 3.11 --seed" 'GPU kurulumu: Python hazırlanıyor…'
    Invoke-GpuSetupProcess $GpuPython '-m pip install --disable-pip-version-check torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121' 'GPU kurulumu: NVIDIA PyTorch indiriliyor…'
    Invoke-GpuSetupProcess $uvExe "pip install --python `"$GpuPython`" huggingface-hub llama-cpp-python transformers==4.57.6 sentencepiece sacremoses --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu125" 'GPU kurulumu: hızlı OPUS ve Qwen kalite bileşenleri indiriliyor…'
    & $GpuPython -c "import os,torch; os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__),'lib')); import llama_cpp,huggingface_hub,transformers,sentencepiece,sacremoses" 2>$null
    if($LASTEXITCODE-ne0){throw 'GPU bileşenleri kuruldu ancak doğrulama başarısız oldu.'}
    [IO.File]::WriteAllText($GpuPathFile,$GpuRuntimeDir,(New-Object Text.UTF8Encoding($false)))
    $gpuText.Text='NVIDIA GPU — Hızlı OPUS + Qwen kalite düzeltme'
    [Windows.Forms.MessageBox]::Show('GPU çeviri bileşenleri başarıyla kuruldu. Hızlı İngilizce-Türkçe OPUS modeli ve gerektiğinde Qwen3 kalite düzelticisi ilk çeviride bir kez indirilecek.','GPU kurulumu tamamlandı','OK','Information')|Out-Null
    return $true
}

function Get-EntryTranslation($entry) {
    $key=[string]$entry.Key; $source=[string]$entry.English
    if(Test-IsProtectedNameKey $key){return $source}
    $value=''
    $applyPhraseRules=$true
    if($script:TermKeys.ContainsKey($key)-and-not$script:ManualRepairs.ContainsKey($key)){$value=[string]$script:TermKeys[$key];$applyPhraseRules=$false}
    elseif((Test-IsWorldTermOverrideKey $key)-and$script:TermValues.ContainsKey($source)){$value=[string]$script:TermValues[$source];$applyPhraseRules=$false}
    elseif($script:ManualRepairs.ContainsKey($key)){$value=[string]$script:ManualRepairs[$key];$applyPhraseRules=$false}
    elseif($script:TermKeys.ContainsKey($key)){$value=[string]$script:TermKeys[$key];$applyPhraseRules=$false}
    elseif($script:TermValues.ContainsKey($source)){$value=[string]$script:TermValues[$source];$applyPhraseRules=$false}
    elseif($script:Translations.ContainsKey($key)){$value=[string]$script:Translations[$key]}
    if($applyPhraseRules){$value=Apply-TermPhrases $value}
    return $value
}

function Test-GpuQualityCandidate($entry) {
    $key=[string]$entry.Key
    if(Test-IsProtectedNameKey $key -or $key-in@('content.67.660','content.156.7')){return $false}
    return [bool](Get-QualityAnalysis $entry (Get-EntryTranslation $entry)).Issue
}

function Local-GpuTranslateAll {
    Save-Current
    if(-not(Ensure-GpuRuntime)){return}
    $inputFile = Join-Path $GpuRuntimeDir 'wakfu_llama3_input.jsonl'
    $resultFile = Join-Path $GpuRuntimeDir 'wakfu_llama3_results.jsonl'
    $script:GpuResultFile=$resultFile
    $contextFile = Join-Path $GpuRuntimeDir 'wakfu_llama3_context.json'
    $attemptRevision='wakfu-human-reviewed-context-v14'
    $revisionFile=Join-Path $GpuRuntimeDir 'wakfu_gpu_revision.txt'
    $targets=@($script:Entries|Where-Object{(Test-IsUntranslated $_)-or(Test-GpuQualityCandidate $_)})
    if ($targets.Count -eq 0) {
        Invoke-QualityCheck -Silent
        [Windows.Forms.MessageBox]::Show('Eksik veya düzeltilmesi gereken bir metin bulunamadı.','ÇEVİRİ','OK','Information') | Out-Null
        return
    }
    $answer = [Windows.Forms.MessageBox]::Show("Eksik ve şüpheli bulunan $($targets.Count) metin çevrilecek.`n`nÇeviri belleği boşsa seçiminize göre oyunun tamamı çevrilir. RTX 2080 Super'da hızlı İngilizce-Türkçe OPUS modeli toplu çeviri yapacak; yalnız kalite reddi alan satırları Qwen3 düzeltecek. İşlem sonunda kayıt ve kalite kontrolü otomatik yapılır.`n`nDevam edilsin mi?",'ÇEVİRİ','YesNo','Question')
    if ($answer -ne [Windows.Forms.DialogResult]::Yes) { return }
    Write-TranslationLogSnapshot 'GPU çeviri başladı' "Hedef=$($targets.Count); GPU=$($gpuText.Text)"

    # Qwen modeli daha önce bu ortak önbelleğe indirildiyse tekrar indirme.
    # Tek kök kullanılır: OPUS ve Qwen mevcut dosyalarını doğru yerde bulur;
    # klasör taşındığında bile gereksiz indirme uyarısı göstermez.
    $modelCache = $GpuRuntimeDir
    $protectedNames=New-Object Collections.Generic.List[string]
    $seenNames=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach($entry in $script:Entries){
        if(Test-IsProtectedNameKey ([string]$entry.Key)){
            $name=([string]$entry.English).Trim()
            if($name -and $seenNames.Add($name)){$protectedNames.Add($name)}
        }
    }
    $glossary=[ordered]@{}
    foreach($term in($script:TermValues.Keys|Sort-Object)){
        $sourceTerm=[string]$term;$targetTerm=[string]$script:TermValues[$term]
        if($sourceTerm -and $targetTerm){$glossary[$sourceTerm]=$targetTerm}
    }
    foreach($term in($script:TermPhrases.Keys|Sort-Object)){
        $sourceTerm=[string]$term;$targetTerm=[string]$script:TermPhrases[$term]
        if($sourceTerm -and $targetTerm -and-not$glossary.Contains($sourceTerm)){$glossary[$sourceTerm]=$targetTerm}
    }
    $context=[ordered]@{
        version=$attemptRevision
        language='tr-TR'
        protected_names=$protectedNames.ToArray()
        glossary=$glossary
        policy='Wakfu özel adları ve biçim işaretleri korunur. Arayüz, görev, diyalog, öğretici, pazar ve açıklamalar kategoriye uygun doğal Türkçeyle çevrilir. Toplu GPU çevirisi yalnız doğrulanmış sözlük, ad koruması, biçim denetimi ve Qwen kalite düzeltmesiyle kabul edilir.'
    }
    [IO.File]::WriteAllText($contextFile,($context|ConvertTo-Json -Depth 6 -Compress),(New-Object Text.UTF8Encoding($false)))
    $writer = New-Object IO.StreamWriter($inputFile,$false,(New-Object Text.UTF8Encoding($false)))
    try {
        foreach ($item in $targets) {
            $line = [ordered]@{key=$item.Key;english=$item.English;category=(Get-WakfuTextCategory $item)} | ConvertTo-Json -Compress
            $writer.WriteLine($line)
        }
    } finally { $writer.Dispose() }
    Copy-Item -LiteralPath $inputFile -Destination $LastGpuInput -Force
    Copy-Item -LiteralPath $contextFile -Destination $LastGpuContext -Force
    if (Test-Path -LiteralPath $resultFile) { Remove-Item -LiteralPath $resultFile -Force }

    $script:CancelTranslation = $false
    $btnGpu.Enabled=$false; $btnStop.Enabled=$true
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $GpuPython
    $psi.Arguments = "`"$GpuWorker`" --input `"$inputFile`" --output `"$resultFile`" --cache `"$modelCache`" --context `"$contextFile`" --live-log `"$LiveTsv`" --batch 32 --qwen-model 8b-q4"
    $psi.WorkingDirectory = $ToolDir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
    $psi.EnvironmentVariables['PYTHONUTF8']='1'
    $psi.EnvironmentVariables['HF_HUB_DISABLE_PROGRESS_BARS']='1'
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $psi
    $script:GpuProcess = $process
    try {
        if (-not $process.Start()) { throw 'GPU çeviri işlemi başlatılamadı.' }
        $errorTask=$process.StandardError.ReadToEndAsync()
        $lastGpuSignal=[DateTime]::UtcNow
        $gpuTimedOut=$false
        while (-not $process.HasExited) {
            $readTask = $process.StandardOutput.ReadLineAsync()
            while (-not $readTask.IsCompleted -and -not $process.HasExited) {
                [Windows.Forms.Application]::DoEvents()
                if ($script:CancelTranslation) { try { $process.Kill() } catch {}; break }
                if(([DateTime]::UtcNow-$lastGpuSignal).TotalSeconds-gt180){
                    $gpuTimedOut=$true
                    try{$process.Kill()}catch{}
                    break
                }
                Start-Sleep -Milliseconds 100
            }
            if ($readTask.IsCompleted) {
                $line = $readTask.Result
                if($line){$lastGpuSignal=[DateTime]::UtcNow}
                if ($line -like 'DEVICE|*') {
                    $parts=$line.Split('|'); $status.Text="GPU hazır: $($parts[1]) — bellek: $($parts[2])"
                } elseif ($line -like 'STATUS|*') {
                    $status.Text=$line.Substring(7)
                } elseif ($line -like 'ITEM_START|*') {
                    $parts=$line.Split('|');$status.Text="Yerel GPU: $($parts[2]) / $($parts[3]) — çevriliyor: $($parts[1])"
                } elseif ($line -like 'HEARTBEAT|*') {
                    $status.Text=$status.Text.TrimEnd('.')+'.'
                } elseif ($line -like 'DEDUP|*') {
                    $parts=$line.Split('|');$status.Text="Hızlandırma: $($parts[1]) satır, $($parts[2]) benzersiz metne ve $($parts[3]) GPU paketine indirildi"
                } elseif ($line -like 'BATCH_RETRY|*') {
                    Write-AppLog $line 'GPU-PAKET-YENIDEN-DENE'
                } elseif ($line -like 'PROGRESS|*') {
                    $parts=$line.Split('|')
                    if([int]$parts[1]-lt100){
                        $status.Text="Yerel GPU: $($parts[1]) / $($parts[2]) — hız ölçülüyor; ilk tahmin gösterilmiyor"
                    }else{
                        $mins=[Math]::Ceiling([int]$parts[4]/60)
                        $status.Text="Yerel GPU: $($parts[1]) / $($parts[2]) — $($parts[3]) metin/sn — yaklaşık $mins dk kaldı"
                    }
                } elseif ($line -like 'ITEM_ERROR|*') {
                    Write-AppLog $line 'GPU-SATIR-HATA'
                } elseif ($line -like 'ERROR|*') { throw $line.Substring(6) }
            }
        }
        $process.WaitForExit()
        if($gpuTimedOut){throw 'GPU modeli 3 dakika boyunca yanıt üretmedi. İşlem otomatik durduruldu; daha önce tamamlanan satırlar korunmuştur.'}
        $gpuError=[string]$errorTask.Result
        if(-not$script:CancelTranslation -and $process.ExitCode-ne0){
            if($gpuError.Length-gt3500){$gpuError=$gpuError.Substring($gpuError.Length-3500)}
            Write-AppLog $gpuError 'GPU-ALT-SUREC-HATA'
            throw "Qwen GPU işlemi başarısız oldu:`n$gpuError"
        }
        $imported=0; $formatErrors=0; $qualityRejected=0
        $entryByKey=@{}
        foreach($entry in $script:Entries){$entryByKey[$entry.Key]=$entry}
        if (Test-Path -LiteralPath $resultFile) {
            $reader = New-Object IO.StreamReader($resultFile,[Text.Encoding]::UTF8)
            Initialize-LiveTranslationLog
            $gpuLogWriter = New-Object IO.StreamWriter($LiveTsv,$true,(New-Object Text.UTF8Encoding($false)))
            try {
                while (($line=$reader.ReadLine()) -ne $null) {
                    if (-not $line.Trim()) { continue }
                    try{$result=$line | ConvertFrom-Json}catch{$qualityRejected++;Write-AppLog "GPU sonuç satırı JSON olmadığı için reddedildi | $line" 'GPU-RED';continue}
                    $key=[string]$result.key;$entry=$entryByKey[$key];$translation=[string]$result.translation
                    if($null-eq$entry){$qualityRejected++;Write-AppLog "GPU sonucu bilinmeyen anahtar nedeniyle reddedildi | Anahtar=$key" 'GPU-RED';continue}
                    $workerQuality=[string]$result.worker_quality
                    if(-not[string]::IsNullOrWhiteSpace($workerQuality)){$qualityRejected++;$gpuLogWriter.WriteLine((Convert-ToLiveTsvLine $key ([string]$entry.English) $translation 'OTOMATIK_GPU' 'REDDEDILDI' $workerQuality));Write-AppLog "GPU işçi kalite reddi | Anahtar=$key | Neden=$workerQuality" 'GPU-RED';continue}
                    $analysis=Get-QualityAnalysis $entry $translation
                    if($analysis.Status-eq'CEVRILDI'){$script:Translations[$key]=$translation;$gpuLogWriter.WriteLine((Convert-ToLiveTsvLine $key ([string]$entry.English) $translation 'OTOMATIK_GPU' 'KAYDEDILDI' 'PowerShell kalite denetiminden geçti'));$imported++}
                    elseif($analysis.Status-eq'BICIM_HATASI'){$formatErrors++;$gpuLogWriter.WriteLine((Convert-ToLiveTsvLine $key ([string]$entry.English) $translation 'OTOMATIK_GPU' 'REDDEDILDI' $analysis.Reason));Write-AppLog "GPU biçim hatası reddedildi | Anahtar=$key | Neden=$($analysis.Reason)" 'GPU-RED'}
                    else{$qualityRejected++;$gpuLogWriter.WriteLine((Convert-ToLiveTsvLine $key ([string]$entry.English) $translation 'OTOMATIK_GPU' 'REDDEDILDI' $analysis.Reason));Write-AppLog "GPU kalite sonucu reddedildi | Anahtar=$key | Durum=$($analysis.Status) | Neden=$($analysis.Reason)" 'GPU-RED'}
                    if (($imported % 500) -eq 0) { Sync-VisibleTranslations; $status.Text="GPU sonuçları kaydediliyor: $imported"; [Windows.Forms.Application]::DoEvents() }
                }
            } finally { $gpuLogWriter.Dispose();$reader.Dispose() }
        }
        Save-Project; Initialize-FastSearchIndex; Refresh-Results
        if(-not$script:CancelTranslation -and $process.ExitCode-eq0){
            [IO.File]::WriteAllText($revisionFile,$attemptRevision,(New-Object Text.UTF8Encoding($false)))
            Invoke-QualityCheck -Silent
        }
        $title=if($script:CancelTranslation){'GPU çevirisi durduruldu'}elseif($process.ExitCode -eq 0){'GPU çevirisi tamamlandı'}else{"GPU işlemi hata koduyla bitti: $($process.ExitCode)"}
        Write-TranslationLogSnapshot 'GPU çeviri bitti' "Hedef=$($targets.Count); Kaydedilen=$imported; BiçimAtlanan=$formatErrors; KaliteReddedilen=$qualityRejected; ÇıkışKodu=$($process.ExitCode); Durduruldu=$($script:CancelTranslation)" $true
        [Windows.Forms.MessageBox]::Show("$title.`nKaydedilen: $imported`nBiçim denetiminde atlanan: $formatErrors`nKalite denetiminde reddedilen: $qualityRejected`n`nReddedilen satırlar sorun listesinde kalır ve sonraki ÇEVİRİ işleminde yeniden düzeltilir.",$title,'OK','Information') | Out-Null
    } finally {
        if(Test-Path -LiteralPath $resultFile){try{Copy-Item -LiteralPath $resultFile -Destination $LastGpuOutput -Force}catch{}}
        $script:GpuProcess=$null; $script:GpuResultFile=$null; $process.Dispose(); $btnGpu.Enabled=$true; $btnStop.Enabled=$false
    }
}

$form = New-Object Windows.Forms.Form
$form.Text = "Wakfu Türkçe Çeviri Aracı — Wakfu Kalite Sistemi $AppVersion"
$form.Size = New-Object Drawing.Size(1400,850)
$form.MinimumSize = New-Object Drawing.Size(1100,700)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object Drawing.Font('Segoe UI',10)
$form.KeyPreview=$true

$top = New-Object Windows.Forms.Panel; $top.Dock='Top'; $top.Height=215; $top.Padding=New-Object Windows.Forms.Padding(10)
$search = New-Object Windows.Forms.TextBox; $search.SetBounds(10,10,470,28); $search.Text=''
$btnSearch = New-Object Windows.Forms.Button; $btnSearch.Text='Ara'; $btnSearch.SetBounds(490,8,75,32)
$missing = New-Object Windows.Forms.CheckBox; $missing.Text='Yalnız çevrilmemişler'; $missing.SetBounds(580,12,175,25)
$chkDarkTheme = New-Object Windows.Forms.CheckBox; $chkDarkTheme.Text='Koyu Tema'; $chkDarkTheme.SetBounds(770,12,110,25); $chkDarkTheme.Checked=$script:DarkThemeEnabled
$btnInstall = New-Object Windows.Forms.Button; $btnInstall.Text='Oyuna Kur'; $btnInstall.SetBounds(280,48,170,50); $btnInstall.Font=New-Object Drawing.Font('Segoe UI',12,[Drawing.FontStyle]::Bold); $btnInstall.BackColor=[Drawing.Color]::Gold
$btnBackup = New-Object Windows.Forms.Button; $btnBackup.Text='Orijinali Yedekle'; $btnBackup.SetBounds(1015,48,155,32); $btnBackup.Anchor='Top,Right'
$btnRestore = New-Object Windows.Forms.Button; $btnRestore.Text='Orijinali Geri Yükle'; $btnRestore.SetBounds(1180,48,200,32); $btnRestore.Anchor='Top,Right'
$btnGpu = New-Object Windows.Forms.Button; $btnGpu.Text='ÇEVİRİ'; $btnGpu.SetBounds(10,48,260,50); $btnGpu.Font=New-Object Drawing.Font('Segoe UI',14,[Drawing.FontStyle]::Bold); $btnGpu.BackColor=[Drawing.Color]::PaleGreen
$btnStop = New-Object Windows.Forms.Button; $btnStop.Text='Çeviriyi Durdur'; $btnStop.SetBounds(460,56,140,34); $btnStop.Enabled=$false
$allText = New-Object Windows.Forms.Label; $allText.Text='Eksik ve kalitesiz metinleri belirler; gerekirse oyunun tamamını çevirir, kaydeder ve kalite kontrolü yapar.'; $allText.SetBounds(610,54,390,42)
$gpuText = New-Object Windows.Forms.Label; $gpuText.Text='NVIDIA GPU — Hızlı OPUS + Qwen kalite düzeltme • Wakfu ad koruması'; $gpuText.SetBounds(10,108,700,25)
if(Test-Path -LiteralPath $GpuPython){
    $gpuText.Text='NVIDIA GPU — Hızlı OPUS + Qwen kalite düzeltme • Wakfu ad koruması'
}
$keepNames = New-Object Windows.Forms.CheckBox; $keepNames.Text='Wakfu adları zorunlu korunur: eşya, NPC, yaratık, sınıf ve yetenek'; $keepNames.SetBounds(780,91,600,28); $keepNames.Checked=$true; $keepNames.Enabled=$false; $keepNames.Anchor='Top,Right'
$btnShowAll = New-Object Windows.Forms.Button; $btnShowAll.Text='Tümünü Göster'; $btnShowAll.SetBounds(535,124,175,32)
$lblOverheadScale=New-Object Windows.Forms.Label;$lblOverheadScale.Text='Baş üstü yazı boyutu:';$lblOverheadScale.TextAlign='MiddleLeft';$lblOverheadScale.SetBounds(205,139,145,32)
$cmbOverheadScale=New-Object Windows.Forms.ComboBox;$cmbOverheadScale.DropDownStyle='DropDownList';$cmbOverheadScale.SetBounds(350,138,270,32)
[void]$cmbOverheadScale.Items.AddRange([object[]]@('Normal (28 / 24)','Küçük (24 / 20)','Çok küçük (20 / 16) — Önerilen'))
$cmbOverheadScale.SelectedIndex=switch([string]$script:OverheadTextScaleProfile){'normal'{0}'tiny'{2}default{1}}
$logText = New-Object Windows.Forms.Label; $logText.Text='Kayıtlar: EXE klasöründe İngilizce ↔ Türkçe canlı günlük, tam durum ve sorun raporu'; $logText.SetBounds(10,171,790,24)
$btnClearMemory = New-Object Windows.Forms.Button; $btnClearMemory.Text='Tüm Çevirileri Sil'; $btnClearMemory.SetBounds(1180,124,200,32); $btnClearMemory.BackColor=[Drawing.Color]::MistyRose; $btnClearMemory.Anchor='Top,Right'
$btnClearGamePatch = New-Object Windows.Forms.Button; $btnClearGamePatch.Text='Oyundaki Yamayı Temizle'; $btnClearGamePatch.SetBounds(905,166,475,32); $btnClearGamePatch.BackColor=[Drawing.Color]::LightGoldenrodYellow; $btnClearGamePatch.Anchor='Top,Right'
$script:ShowAllResults=$false
$top.Controls.AddRange(@($search,$btnSearch,$missing,$chkDarkTheme,$btnInstall,$btnBackup,$btnRestore,$btnStop,$allText,$btnGpu,$gpuText,$keepNames,$btnShowAll,$lblOverheadScale,$cmbOverheadScale,$logText,$btnClearMemory,$btnClearGamePatch))

$split = New-Object Windows.Forms.SplitContainer; $split.Dock='Fill'; $split.Orientation='Horizontal'; $split.SplitterDistance=390; $split.SplitterWidth=6; $split.Panel1MinSize=220; $split.Panel2MinSize=150
$grid = New-Object Windows.Forms.DataGridView; $grid.Dock='Fill'; $grid.ReadOnly=$false; $grid.AllowUserToAddRows=$false; $grid.SelectionMode='FullRowSelect'; $grid.MultiSelect=$false; $grid.AutoSizeColumnsMode='Fill'; $grid.VirtualMode=$true; $grid.ShowCellToolTips=$false; $grid.EditMode='EditOnKeystrokeOrF2'
$grid.RowHeadersWidth=34; $grid.RowTemplate.Height=28; $grid.ColumnHeadersHeight=32; $grid.ColumnHeadersHeightSizeMode='DisableResizing'; $grid.AutoSizeRowsMode='None'; $grid.DefaultCellStyle.Padding=New-Object Windows.Forms.Padding(4,2,4,2)
[void]$grid.Columns.Add('Key','Anahtar'); [void]$grid.Columns.Add('English','İngilizce'); [void]$grid.Columns.Add('Turkish','Türkçe')
$grid.Columns[0].FillWeight=30; $grid.Columns[1].FillWeight=45; $grid.Columns[2].FillWeight=45
$grid.Columns[0].ReadOnly=$true; $grid.Columns[1].ReadOnly=$true; $grid.Columns[2].ReadOnly=$false
$split.Panel1.Controls.Add($grid)

$edit = New-Object Windows.Forms.TableLayoutPanel; $edit.Dock='Fill'; $edit.ColumnCount=2; $edit.RowCount=3; [void]$edit.ColumnStyles.Add((New-Object Windows.Forms.ColumnStyle('Percent',50))); [void]$edit.ColumnStyles.Add((New-Object Windows.Forms.ColumnStyle('Percent',50))); [void]$edit.RowStyles.Add((New-Object Windows.Forms.RowStyle('Absolute',28))); [void]$edit.RowStyles.Add((New-Object Windows.Forms.RowStyle('Percent',100))); [void]$edit.RowStyles.Add((New-Object Windows.Forms.RowStyle('Absolute',34)))
$l1=New-Object Windows.Forms.Label; $l1.Text='İngilizce (salt okunur)'; $l1.Dock='Fill'
$l2=New-Object Windows.Forms.Label; $l2.Text='Türkçe çeviri'; $l2.Dock='Fill'
$english=New-Object Windows.Forms.TextBox; $english.Multiline=$true; $english.ReadOnly=$true; $english.Dock='Fill'; $english.ScrollBars='Vertical'
$turkish=New-Object Windows.Forms.TextBox; $turkish.Multiline=$true; $turkish.Dock='Fill'; $turkish.ScrollBars='Vertical'; $turkish.ShortcutsEnabled=$true; $turkish.AcceptsReturn=$true
$btnSaveRow=New-Object Windows.Forms.Button; $btnSaveRow.Text='Kaydet'; $btnSaveRow.Dock='Fill'
$hint=New-Object Windows.Forms.Label; $hint.Text='[#1], {…}, %…% ve \n gibi işaretleri aynen koruyun. Satır anında veya Kaydet / Ctrl+S ile yazılır. Hayır = yalnızca diğer satırlara uygulama. Canavar/NPC adları kilitli kalır.'; $hint.Dock='Fill'
$edit.Controls.Add($l1,0,0); $edit.Controls.Add($l2,1,0); $edit.Controls.Add($english,0,1); $edit.Controls.Add($turkish,1,1); $edit.Controls.Add($hint,0,2); $edit.Controls.Add($btnSaveRow,1,2)
$split.Panel2.Controls.Add($edit)
$statusStrip = New-Object Windows.Forms.StatusStrip; $statusLabel = New-Object Windows.Forms.ToolStripStatusLabel; $statusLabel.Spring=$true; $statusLabel.TextAlign='MiddleLeft'; $authorLabel=New-Object Windows.Forms.ToolStripStatusLabel; $authorLabel.Text='Yapım Relactive'; $authorLabel.Font=New-Object Drawing.Font('Segoe UI',9,[Drawing.FontStyle]::Bold); [void]$statusStrip.Items.Add($statusLabel); [void]$statusStrip.Items.Add($authorLabel); $script:status=$statusLabel
$tabs=New-Object Windows.Forms.TabControl;$tabs.Dock='Fill'
$tabs.Add_DrawItem({
    param($sender,$e)
    if(-not$script:DarkThemeEnabled){return}
    $g=$e.Graphics
    $page=$sender.TabPages[$e.Index]
    $bounds=$e.Bounds
    $selected=(($e.State -band [Windows.Forms.DrawItemState]::Selected) -ne 0)
    $back=if($selected){[Drawing.Color]::FromArgb(55,62,74)}else{[Drawing.Color]::FromArgb(36,40,48)}
    $fore=[Drawing.Color]::FromArgb(232,235,240)
    $brush=New-Object Drawing.SolidBrush $back
    $textBrush=New-Object Drawing.SolidBrush $fore
    try{
        $g.FillRectangle($brush,$bounds)
        $sf=New-Object Drawing.StringFormat
        $sf.Alignment=[Drawing.StringAlignment]::Center
        $sf.LineAlignment=[Drawing.StringAlignment]::Center
        # PowerShell DrawString binder: Rectangle alone binds to PointF overload and crashes;
        # use RectangleF + StringFormat (or float x,y) so owner-draw tabs stay stable.
        $rectF=[Drawing.RectangleF]::new([float]$bounds.X,[float]$bounds.Y,[float]$bounds.Width,[float]$bounds.Height)
        $g.DrawString([string]$page.Text,$sender.Font,$textBrush,$rectF,$sf)
        $sf.Dispose()
    }finally{$brush.Dispose();$textBrush.Dispose()}
})
$translationPage=New-Object Windows.Forms.TabPage;$translationPage.Text='Çeviri'
$setupPage=New-Object Windows.Forms.TabPage;$setupPage.Text='Kurulum EXE'
$translationPage.Controls.Add($split);$translationPage.Controls.Add($top);$translationPage.Controls.Add($statusStrip)
$setupTitle=New-Object Windows.Forms.Label;$setupTitle.Text='Bağımsız Wakfu Türkçe Yama Kurulumu';$setupTitle.Font=New-Object Drawing.Font('Segoe UI',18,[Drawing.FontStyle]::Bold);$setupTitle.SetBounds(35,35,700,42)
$setupInfo=New-Object Windows.Forms.Label;$setupInfo.Text="Mevcut çeviriyi tek dosyalık Windows setup olarak hazırlar. Düğmeye bastığınızda EXE'nin adını ve kaydedileceği klasörü seçebilirsiniz.`nSetup; Steam klasörü veya doğrudan Wakfu klasörü seçebilir, temiz dosyaları yedekler, yamayı yükler ve geri yükleyebilir.";$setupInfo.SetBounds(38,90,1050,65)
$btnInstallSetup=New-Object Windows.Forms.Button;$btnInstallSetup.Text='Oyuna Kur';$btnInstallSetup.SetBounds(38,175,240,48);$btnInstallSetup.Font=New-Object Drawing.Font('Segoe UI',12,[Drawing.FontStyle]::Bold);$btnInstallSetup.BackColor=[Drawing.Color]::Gold
$btnSetupBuild=New-Object Windows.Forms.Button;$btnSetupBuild.Text='Kurulum EXE Oluştur';$btnSetupBuild.SetBounds(288,175,240,48);$btnSetupBuild.BackColor=[Drawing.Color]::PaleGreen
$setupPath=New-Object Windows.Forms.TextBox;$setupPath.ReadOnly=$true;$setupPath.SetBounds(38,245,900,30);$setupPath.Text='Kurulum EXE oluştururken kaydetme konumu seçilecek.'
$setupStatus=New-Object Windows.Forms.Label;$setupStatus.Text='Windows 10/11 ve Steam Wakfu için taşınabilir kurulum.';$setupStatus.SetBounds(38,290,950,28)
$setupAuthor=New-Object Windows.Forms.Label;$setupAuthor.Text='Yapım Relactive';$setupAuthor.AutoSize=$true;$setupAuthor.Anchor='Bottom,Right';$setupAuthor.Location=New-Object Drawing.Point(1030,640);$setupAuthor.Font=New-Object Drawing.Font('Segoe UI',9,[Drawing.FontStyle]::Bold)
$setupPage.Controls.AddRange(@($setupTitle,$setupInfo,$btnInstallSetup,$btnSetupBuild,$setupPath,$setupStatus,$setupAuthor))
$tabs.TabPages.Add($translationPage)|Out-Null;$tabs.TabPages.Add($setupPage)|Out-Null;$form.Controls.Add($tabs)

function Update-ResponsiveLayout {
    if($null-eq$top -or $top.IsDisposed){return}
    $w=[Math]::Max(1050,$top.ClientSize.Width)
    $right=$w-12
    $searchWidth=[Math]::Max(260,[Math]::Min(500,$w-690))
    $search.SetBounds(12,10,$searchWidth,30)
    $btnSearch.SetBounds(22+$searchWidth,9,78,32)
    $missing.SetBounds(112+$searchWidth,12,190,26)
    $chkDarkTheme.SetBounds($right-112,12,112,26)

    $btnGpu.SetBounds(12,49,230,48)
    $btnInstall.SetBounds(252,49,150,48)
    $btnStop.SetBounds(412,56,138,34)
    $btnRestore.SetBounds($right-195,49,195,34)
    $btnBackup.SetBounds($right-355,49,150,34)
    $allText.SetBounds(565,52,[Math]::Max(105,($right-365)-565),43)

    $gpuText.SetBounds(12,108,[Math]::Max(420,[int]($w*0.52)),25)
    $keepNames.SetBounds([Math]::Max(565,[int]($w*0.55)),105,[Math]::Max(300,$right-[Math]::Max(565,[int]($w*0.55))),28)
    $btnShowAll.SetBounds(12,139,175,32)
    $lblOverheadScale.SetBounds(205,139,145,32)
    $cmbOverheadScale.SetBounds(350,138,270,32)
    $btnClearMemory.SetBounds($right-195,135,195,32)
    $logText.SetBounds(12,180,[Math]::Max(300,$right-405),24)
    $btnClearGamePatch.SetBounds($right-385,174,385,32)

    if($null-ne$setupPage){
        $pageWidth=[Math]::Max(900,$setupPage.ClientSize.Width)
        $setupInfo.SetBounds(38,90,$pageWidth-76,65)
        $setupPath.SetBounds(38,245,$pageWidth-76,30)
        $setupStatus.SetBounds(38,290,$pageWidth-76,28)
        $setupAuthor.Location=New-Object Drawing.Point([Math]::Max(38,$pageWidth-$setupAuthor.Width-38),[Math]::Max(330,$setupPage.ClientSize.Height-$setupAuthor.Height-30))
    }
}
$top.Add_Resize({Update-ResponsiveLayout})
$setupPage.Add_Resize({Update-ResponsiveLayout})
Update-ResponsiveLayout

$grid.Add_CellValueNeeded({
    param($sender,$eventArgs)
    if($eventArgs.RowIndex-lt0 -or $eventArgs.RowIndex-ge$script:Visible.Count){return}
    $entry=$script:Visible[$eventArgs.RowIndex]
    switch($eventArgs.ColumnIndex){0{$eventArgs.Value=$entry.Key}1{$eventArgs.Value=$entry.English}2{$eventArgs.Value=$entry.Turkish}}
})
$searchDebounce=New-Object Windows.Forms.Timer;$searchDebounce.Interval=280
$searchDebounce.Add_Tick({$searchDebounce.Stop();try{Refresh-Results}catch{Write-AppLog $_.Exception.ToString() 'ARAMA-HATA'}})
$btnSearch.Add_Click({$searchDebounce.Stop();Refresh-Results})
$missing.Add_CheckedChanged({$searchDebounce.Stop();Refresh-Results})
$search.Add_TextChanged({$searchDebounce.Stop();$searchDebounce.Start()})
$search.Add_KeyDown({if($_.KeyCode-eq'Enter'){$_.SuppressKeyPress=$true;$searchDebounce.Stop();Refresh-Results}})
$btnShowAll.Add_Click({
    Save-Current
    $script:ShowAllResults=-not $script:ShowAllResults
    $btnShowAll.Text=if($script:ShowAllResults){"İlk 1000'i Göster"}else{'Tümünü Göster'}
    Refresh-Results
})
$btnClearMemory.Add_Click({ Clear-AllTranslationMemory })
$btnInstall.Add_Click({ Invoke-InstallJarSafe })
$btnInstallSetup.Add_Click({ Invoke-InstallJarSafe })
$btnBackup.Add_Click({ try { Backup-Original } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message,'Yedekleme hatası','OK','Error') | Out-Null } })
$btnRestore.Add_Click({ Restore-Original })
$btnClearGamePatch.Add_Click({ try{Clear-InstalledGameTranslation}catch{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Yama temizleme hatası','OK','Error')|Out-Null} })
$btnGpu.Add_Click({ try { Local-GpuTranslateAll } catch { Write-AppLog $_.Exception.ToString() 'GPU-HATA';$btnGpu.Enabled=$true; $btnStop.Enabled=$false; [Windows.Forms.MessageBox]::Show($_.Exception.Message,'Çeviri hatası','OK','Error') | Out-Null } })
$btnSetupBuild.Add_Click({Build-SetupInstaller})
$btnStop.Add_Click({ $script:CancelTranslation=$true; $btnStop.Enabled=$false; if($script:GpuProcess -and -not $script:GpuProcess.HasExited){try{$script:GpuProcess.Kill()}catch{}}; $status.Text='Çeviri güvenli biçimde durduruluyor…' })
$cmbOverheadScale.Add_SelectedIndexChanged({
    $script:OverheadTextScaleProfile=switch($cmbOverheadScale.SelectedIndex){0{'normal'}2{'tiny'}default{'small'}}
    Save-UiSettings
    if($null-ne$status){$status.Text="Baş üstü yazı boyutu seçildi: $((Get-OverheadFontProfile).Label). Oyuna Kur ile uygulanacak."}
})
$chkDarkTheme.Add_CheckedChanged({
    $script:DarkThemeEnabled=[bool]$chkDarkTheme.Checked
    Set-AppTheme $script:DarkThemeEnabled
    Save-UiSettings
})
Set-AppTheme $script:DarkThemeEnabled
$script:SaveTimer=New-Object Windows.Forms.Timer;$script:SaveTimer.Interval=650
$script:SaveTimer.Add_Tick({
    $script:SaveTimer.Stop()
    try{Flush-PersistentState;if($null-ne$status){$status.Text="Kaydedildi: $($script:Translations.Count) çeviri"}}
    catch{Write-AppLog $_.Exception.ToString() 'OTOMATIK-KAYIT-HATA';if($null-ne$status){$status.Text='Otomatik kayıt başarısız; Ctrl+S ile yeniden deneyin.'}}
})
$grid.Add_CellBeginEdit({
    param($sender,$eventArgs)
    if($eventArgs.RowIndex-lt0){$eventArgs.Cancel=$true;return}
    if($eventArgs.ColumnIndex-ne2){$eventArgs.Cancel=$true;return}
    $entry=$script:Visible[$eventArgs.RowIndex]
    if(Test-IsForcedEnglishNameKey ([string]$entry.Key)){$eventArgs.Cancel=$true;$status.Text="Özel ad kilitli: $($entry.Key)"}
})
$grid.Add_CellValuePushed({
    param($sender,$eventArgs)
    if($eventArgs.RowIndex-lt0 -or $eventArgs.ColumnIndex-ne2){return}
    try{
        $entry=$script:Visible[$eventArgs.RowIndex]
        $script:SelectedKey=[string]$entry.Key
        $english.Text=[string]$entry.English
        Apply-TurkishEditorState $false
        $turkish.Text=[string]$eventArgs.Value
        Save-Current
        $entry.Turkish=Get-EntryTranslation $entry
    }catch{Write-AppLog $_.Exception.ToString() 'GRID-DUZENLEME-HATA'}
})
$grid.Add_SelectionChanged({
    try{
        if ($grid.SelectedRows.Count -eq 0) { return }
        $rowIndex=$grid.SelectedRows[0].Index
        Load-VisibleEntry $rowIndex
    }catch{Write-AppLog $_.Exception.ToString() 'ELLE-KAYIT-HATA';$status.Text='Elle çeviri kaydedilemedi; ayrıntı loga yazıldı.'}
})
$turkish.Add_Leave({
    try{Save-Current}
    catch{Write-AppLog $_.Exception.ToString() 'ELLE-KAYIT-HATA';$status.Text='Elle çeviri kaydedilemedi; ayrıntı loga yazıldı.'}
})
$turkish.Add_KeyDown({
    if($_.Control -and $_.KeyCode -eq 'S'){
        $_.SuppressKeyPress=$true
        try{Save-Current;Flush-PersistentState}catch{Write-AppLog $_.Exception.ToString() 'ELLE-KAYIT-HATA'}
    }
})
$btnSaveRow.Add_Click({
    try{Save-Current;Flush-PersistentState}catch{Write-AppLog $_.Exception.ToString() 'ELLE-KAYIT-HATA';$status.Text='Elle çeviri kaydedilemedi; ayrıntı loga yazıldı.'}
})
$form.Add_KeyDown({
    if($_.Control -and $_.KeyCode -eq 'S'){
        $_.SuppressKeyPress=$true
        try{Save-Current;Flush-PersistentState}catch{Write-AppLog $_.Exception.ToString() 'ELLE-KAYIT-HATA'}
    }
})
$form.Add_FormClosing({
    # Kapanış sırasında olası bir kayıt hatası pencerenin kapanmasını
    # engellemesin. Kullanıcıya bilgi verip uygulamanın kapanmasına izin ver.
    $script:Closing=$true
    try {
        if($null-ne$searchDebounce){$searchDebounce.Stop()}
        if($null-ne$script:SaveTimer){$script:SaveTimer.Stop()}
        Save-UiSettings
        Save-Current
        if($script:GpuProcess -and -not$script:GpuProcess.HasExited){
            $script:CancelTranslation=$true
            try{$script:GpuProcess.Kill()}catch{}
            try{[void]$script:GpuProcess.WaitForExit(5000)}catch{}
        }
        # Çeviri yarıda kapatılsa bile sonuç JSONL dosyasına yazılmış ve kalite
        # denetiminden geçen bütün satırları ana belleğe al. Böylece kapanışta
        # boş/eski sözlükle proje dosyasının üzerine yazılmaz.
        [void](Import-PartialGpuResults $script:GpuResultFile)
        Flush-PersistentState
    }
    catch { [Windows.Forms.MessageBox]::Show("Son değişiklik kaydedilemedi:`n$($_.Exception.Message)",'Kayıt uyarısı','OK','Warning') | Out-Null }
    finally {
        try{if($null-ne$searchDebounce){$searchDebounce.Dispose()}}catch{}
        try{if($null-ne$script:SaveTimer){$script:SaveTimer.Dispose()}}catch{}
        try{if($null-ne$script:GpuProcess){$script:GpuProcess.Dispose()}}catch{}
    }
})

try {
    $detectedUpdates=if($AuditOnly -or $BuildOnly){@()}else{@(Sync-GameUpdates)}
    $script:Entries = Read-PropertiesFromJar
    $script:EntryEnglish=New-Object 'Collections.Generic.Dictionary[string,string]' ([StringComparer]::Ordinal)
    foreach($entry in $script:Entries){$script:EntryEnglish[[string]$entry.Key]=[string]$entry.English}
    $script:SkillTitleValues=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    $script:ItemTitleValues=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    foreach($entry in $script:Entries){
        if(([string]$entry.Key)-match'^content\.3\.'){
            $skillTitle=([string]$entry.English).Trim()
            if($skillTitle){[void]$script:SkillTitleValues.Add($skillTitle)}
        }
        if(([string]$entry.Key)-match'^content\.15\.'){
            $itemTitle=([string]$entry.English).Trim()
            if($itemTitle){[void]$script:ItemTitleValues.Add($itemTitle)}
        }
    }
    $script:ProtectedNameValues=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    foreach($name in [WakfuFastSearch]::ProtectedNames($script:SearchKeys,$script:SearchEnglish)){[void]$script:ProtectedNameValues.Add($name)}
    if($AuditOnly -and $AuditLimit-gt0 -and $script:Entries.Count-gt$AuditLimit){$script:Entries=@($script:Entries|Select-Object -First $AuditLimit)}
    Load-Project
    Load-Terminology
    Initialize-FastSearchIndex
    # 154 bin satırın tamamında ad korumasını ve ayrıntılı durum günlüğünü
    # pencere açılmadan önce çalıştırmak iki dakikaya varan sahte bir "donma"
    # görüntüsü oluşturuyordu. Koruma; arama, elle düzenleme, GPU hedef seçimi ve
    # paket üretimi sırasında zaten zorunlu olarak uygulanıyor. Açılışta projeyi
    # baştan tarayıp yeniden yazmak bu nedenle gerekli değil.
    $removedProtected=0
    if($BuildOnly){Build-Jar;return}
    if($InstallOnly){Install-Jar;$installedState=Read-InstallState;if($null-eq$installedState-or[string]$installedState.version-ne$AppVersion){throw 'Kurulum tamamlandı ancak sürüm durumu doğrulanamadı.'};Write-Output "INSTALL_OK|$AppVersion|$GameDir";return}
    Refresh-Results
    Initialize-LiveTranslationLog
    Write-AppLog "Program açıldı | Sürüm=$AppVersion | EXE klasörü=$LogDir | Kaynak=$SourceJar"
    if($removedProtected-gt0){Write-AppLog "Açılışta ad koruması uygulandı | Temizlenen eski ad çevirisi=$removedProtected"}
    Write-AppLog "Açılış hazır | Toplam=$($script:Entries.Count) | Ayrıntılı durum raporu çeviri/kalite işlemi sonunda güncellenecek"
    if($UiSmokeTest){
        $checks=[ordered]@{}
        $form.Show();[Windows.Forms.Application]::DoEvents();Update-ResponsiveLayout
        $checks.FormAcildi=$form.Visible
        $checks.AcilisMs=[Math]::Round($script:ProgramStopwatch.Elapsed.TotalMilliseconds)
        $checks.GridSatirSayisi=$grid.RowCount
        $editableIndex=-1
        for($i=0;$i-lt$script:Visible.Count;$i++){if(-not(Test-IsForcedEnglishNameKey ([string]$script:Visible[$i].Key))){$editableIndex=$i;break}}
        if($editableIndex-ge0){
            $grid.ClearSelection();$grid.CurrentCell=$grid.Rows[$editableIndex].Cells[0];$grid.Rows[$editableIndex].Selected=$true
            Load-VisibleEntry $editableIndex
            [Windows.Forms.Application]::DoEvents()
            $checks.SatirSecimi=($script:SelectedKey-ceq[string]$script:Visible[$editableIndex].Key -and $english.Text-ceq[string]$script:Visible[$editableIndex].English)
            $beforeSave=[string]$turkish.Text
            $saveWatch=[Diagnostics.Stopwatch]::StartNew()
            $btnSaveRow.PerformClick();[Windows.Forms.Application]::DoEvents()
            $saveWatch.Stop();$checks.DegisikliksizKaydetMs=[Math]::Round($saveWatch.Elapsed.TotalMilliseconds)
            $checks.DegisikliksizKaydet=($turkish.Text-ceq$beforeSave)
        }else{$checks.SatirSecimi=$false;$checks.DegisikliksizKaydet=$false}
        $search.Text='backToGame';$searchWatch=[Diagnostics.Stopwatch]::StartNew();$btnSearch.PerformClick();[Windows.Forms.Application]::DoEvents();$searchWatch.Stop();$checks.AramaMs=[Math]::Round($searchWatch.Elapsed.TotalMilliseconds)
        $checks.Arama=(@($script:Visible|Where-Object{$_.Key-ceq'backToGame'}).Count-gt0)
        $themeBefore=[bool]$chkDarkTheme.Checked
        $chkDarkTheme.Checked=-not$themeBefore;[Windows.Forms.Application]::DoEvents()
        $checks.TemaDegisimi=([bool]$chkDarkTheme.Checked-ne$themeBefore)
        $chkDarkTheme.Checked=$themeBefore;[Windows.Forms.Application]::DoEvents()
        $tabs.SelectedTab=$setupPage;[Windows.Forms.Application]::DoEvents();$checks.KurulumSekmesi=($tabs.SelectedTab-eq$setupPage)
        $tabs.SelectedTab=$translationPage;[Windows.Forms.Application]::DoEvents()
        $profile=Get-OverheadFontProfile
        $checks.BasUstuYaziSecimi=($cmbOverheadScale.Items.Count-eq3 -and $cmbOverheadScale.SelectedIndex-in@(0,1,2) -and $profile.Key-in@('normal','small','tiny'))
        $checks.OrantiliYerlesim=($btnRestore.Right-le$top.ClientSize.Width -and $btnGpu.Right-lt$btnInstall.Left -and $cmbOverheadScale.Right-lt$btnClearGamePatch.Left -and $btnClearGamePatch.Right-le$top.ClientSize.Width)
        $checks.GuvenliDugmeler=@($btnSearch,$btnSaveRow,$btnShowAll,$btnGpu,$btnInstall,$btnBackup,$btnRestore,$btnSetupBuild)|Where-Object{$null-ne$_}|ForEach-Object{$_.Text}
        $checks.Basarili=($checks.FormAcildi -and $checks.SatirSecimi -and $checks.DegisikliksizKaydet -and $checks.Arama -and $checks.TemaDegisimi -and $checks.KurulumSekmesi -and $checks.BasUstuYaziSecimi -and $checks.OrantiliYerlesim -and $checks.AramaMs-lt1500)
        if([string]::IsNullOrWhiteSpace($SmokeOutput)){$SmokeOutput=Join-Path $ReportsDir 'ARAYUZ_DUMAN_TESTI.json'}
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($SmokeOutput),($checks|ConvertTo-Json -Depth 4),(New-Object Text.UTF8Encoding($true)))
        $form.Hide();$form.Dispose()
        Write-Output ("UI_SMOKE|{0}|{1}"-f$checks.Basarili,[IO.Path]::GetFullPath($SmokeOutput))
        return
    }
    if($AuditOnly){Write-DiagnosticBundle 'Başsız tam denetim';return}
    if($detectedUpdates.Count-gt0){
        [Windows.Forms.MessageBox]::Show("Oyun güncellemesi algılandı:`n• "+($detectedUpdates-join"`n• ")+"`n`nEski çeviriler korundu. Yeni veya yapısı değişen metinler çevrilmemiş olarak listelenecek.",'Oyun güncellemesi alındı','OK','Information')|Out-Null
    }
    [void]$form.ShowDialog()
}
catch {
    Write-AppLog $_.Exception.ToString() 'BASLATMA-HATA'
    if($AuditOnly -or $BuildOnly -or $InstallOnly -or $UiSmokeTest){Write-Error $_.Exception.Message;exit 1}
    [Windows.Forms.MessageBox]::Show($_.Exception.Message,'Başlatma hatası','OK','Error') | Out-Null
}
