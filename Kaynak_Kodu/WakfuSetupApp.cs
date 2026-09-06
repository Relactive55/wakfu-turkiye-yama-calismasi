using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using Microsoft.Win32;

[assembly: AssemblyTitle("Wakfu Türkçe Yama")]
[assembly: AssemblyDescription("WAKFU için Türkçe çeviri kurulumu ve güvenli geri yükleme aracı")]
[assembly: AssemblyCompany("Wakfu Türkçe Yama Topluluğu")]
[assembly: AssemblyProduct("Wakfu Türkçe Yama")]
[assembly: AssemblyCopyright("Copyright © 2026 Wakfu Türkçe Yama Topluluğu")]
[assembly: AssemblyVersion("6.5.9.0")]
[assembly: AssemblyFileVersion("6.5.9.0")]
[assembly: AssemblyInformationalVersion("Wakfu Türkçe Yama")]

static class WakfuSetupApp {
    static readonly string[] Fonts={"asul.ttf","asulb.ttf","bagnard.ttf","coprgtb.ttf","coprgtl.ttf","droidsansfallbackfull.ttf","fzlibian.ttf","londrina.ttf","lucidacally.ttf"};
    static string StateRoot { get { string isolated=Environment.GetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT");return String.IsNullOrWhiteSpace(isolated)?Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"WakfuTurkceYama"):Path.GetFullPath(isolated); } }
    static string BackupDir { get { return Path.Combine(StateRoot,"Yedekler","Resmi_Oyun_Dosyalari"); } }
    static string ArchiveDir { get { return Path.Combine(StateRoot,"Yedekler","Arsiv"); } }
    static string InstallStatePath { get { return Path.Combine(StateRoot,"kurulum_durumu.json"); } }
    static string InstalledPatchStatePath { get { return Path.Combine(StateRoot,"installed_patch.json"); } }
    static string ReleaseBackupRoot { get { return Path.Combine(StateRoot,"Yedekler","Release_Guncellemeleri"); } }
    static string OverheadPreferencePath { get { return Path.Combine(StateRoot,"bas_ustu_yazi_boyutu.txt"); } }

    [STAThread] static void Main(string[] args){
        if(args!=null&&args.Length>0){try{string game=null,profile=null;for(int i=0;i<args.Length;i++){if(String.Equals(args[i],"--install",StringComparison.OrdinalIgnoreCase)&&i+1<args.Length)game=args[++i];else if(String.Equals(args[i],"--overhead-size",StringComparison.OrdinalIgnoreCase)&&i+1<args.Length)profile=args[++i];else throw new ArgumentException("Kullanım: --install <Wakfu klasörü> --overhead-size <normal|small|tiny>");}if(String.IsNullOrWhiteSpace(game))throw new ArgumentException("Wakfu klasörü belirtilmedi.");Install(game,NormalizeOverheadProfile(profile));}catch(Exception ex){Console.Error.WriteLine(ex.Message);Environment.ExitCode=1;}return;}
        TryInstallerSelfUpdate();
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new SetupForm());
    }
    static void TryInstallerSelfUpdate(){
        try{
            string exe=Assembly.GetExecutingAssembly().Location;if(String.IsNullOrWhiteSpace(exe)||!File.Exists(exe)||Environment.GetEnvironmentVariable("WAKFU_INSTALLER_UPDATE_CHILD")=="1")return;
            ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
            var req=(HttpWebRequest)WebRequest.Create("https://api.github.com/repos/Relactive/wakfu-turkiye-yama-calismasi/releases?per_page=100");req.UserAgent="WakfuTurkceYamaSetup/1.0";req.Accept="application/vnd.github+json";req.Timeout=5000;
            string json;using(var res=(HttpWebResponse)req.GetResponse())using(var reader=new StreamReader(res.GetResponseStream(),Encoding.UTF8))json=reader.ReadToEnd();
            var list=new JavaScriptSerializer{MaxJsonLength=8*1024*1024}.DeserializeObject(json) as System.Collections.ArrayList;if(list==null)return;Version current=InstallerVersion(System.Diagnostics.FileVersionInfo.GetVersionInfo(exe).FileVersion);Dictionary<string,object> chosen=null;Version best=null;
            foreach(object raw in list){var r=raw as Dictionary<string,object>;if(r==null||Bool(r,"draft")||Bool(r,"prerelease"))continue;string tag=Text(r,"tag_name");Match m=Regex.Match(tag??"","^installer-(\\d+)\\.(\\d+)\\.(\\d+)$");if(!m.Success)continue;Version v=new Version(Int32.Parse(m.Groups[1].Value),Int32.Parse(m.Groups[2].Value),0);if(current!=null&&v<=current)continue;if(best==null||v>best){best=v;chosen=r;}}
            if(chosen==null)return;var assets=chosen["assets"] as System.Collections.ArrayList;if(assets==null)return;Dictionary<string,object> asset=null;foreach(object raw in assets){var a=raw as Dictionary<string,object>;if(a!=null&&Regex.IsMatch(Text(a,"name"),"^Wakfu.*\\.exe$",RegexOptions.IgnoreCase)){asset=a;break;}}if(asset==null)return;long size=Long(asset,"size");string digest=Text(asset,"digest");if(size<=0||size>100*1024*1024||!Regex.IsMatch(digest??"","^sha256:[0-9a-fA-F]{64}$"))return;
            string tagName=Text(chosen,"tag_name"),name=Text(asset,"name");Uri uri=new Uri("https://github.com/Relactive/wakfu-turkiye-yama-calismasi/releases/download/"+Uri.EscapeDataString(tagName)+"/"+Uri.EscapeDataString(name));if(uri.Scheme!="https"||uri.Host!="github.com")return;string temp=exe+"."+Guid.NewGuid().ToString("N")+".update";var dl=(HttpWebRequest)WebRequest.Create(uri);dl.UserAgent=req.UserAgent;dl.Timeout=30000;using(var res=(HttpWebResponse)dl.GetResponse())using(var input=res.GetResponseStream())using(var output=new FileStream(temp,FileMode.CreateNew))input.CopyTo(output);if(new FileInfo(temp).Length!=size||!String.Equals("sha256:"+LowerHash(temp),digest,StringComparison.OrdinalIgnoreCase)){try{File.Delete(temp);}catch{}return;}
            string backup=exe+".previous",cmd="/d /c timeout /t 2 /nobreak >nul & move /Y \""+exe+"\" \""+backup+"\" >nul & move /Y \""+temp+"\" \""+exe+"\" >nul & start \"\" \""+exe+"\"";var start=new System.Diagnostics.ProcessStartInfo{FileName=Environment.GetEnvironmentVariable("ComSpec"),Arguments=cmd,UseShellExecute=false,CreateNoWindow=true};start.EnvironmentVariables["WAKFU_INSTALLER_UPDATE_CHILD"]="1";System.Diagnostics.Process.Start(start);Environment.Exit(0);
        }catch{}
    }
    static Version InstallerVersion(string s){Match m=Regex.Match(s??"","^(\\d+)\\.(\\d+)\\.(\\d+)");return m.Success?new Version(Int32.Parse(m.Groups[1].Value),Int32.Parse(m.Groups[2].Value),0):null;}
    static string Text(Dictionary<string,object> m,string k){object v;return m!=null&&m.TryGetValue(k,out v)&&v!=null?Convert.ToString(v):"";}
    static bool Bool(Dictionary<string,object> m,string k){object v;return m!=null&&m.TryGetValue(k,out v)&&v!=null&&Convert.ToBoolean(v);}
    static long Long(Dictionary<string,object> m,string k){long v;return Int64.TryParse(Text(m,k),out v)?v:0;}
    static string LowerHash(string p){using(var sha=SHA256.Create())using(var f=File.OpenRead(p)){var b=sha.ComputeHash(f);var s=new StringBuilder();foreach(byte x in b)s.Append(x.ToString("x2"));return s.ToString();}}
    static bool IsWakfu(string p){return !String.IsNullOrWhiteSpace(p)&&File.Exists(Path.Combine(p,"contents","i18n","i18n_en.jar"));}
    static string FromSteam(string steam){
        if(IsWakfu(steam))return steam; string direct=Path.Combine(steam,"steamapps","common","Wakfu");if(IsWakfu(direct))return direct;
        string vdf=Path.Combine(steam,"steamapps","libraryfolders.vdf");if(File.Exists(vdf))foreach(Match m in Regex.Matches(File.ReadAllText(vdf),"\"path\"\\s+\"([^\"]+)\"")){string p=Path.Combine(m.Groups[1].Value.Replace("\\\\","\\"),"steamapps","common","Wakfu");if(IsWakfu(p))return p;}return "";
    }
    static string FindGame(){
        var roots=new List<string>();roots.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),"Steam"));roots.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"Steam"));
        foreach(var hive in new[]{Registry.CurrentUser,Registry.LocalMachine})foreach(var keyName in new[]{@"Software\Valve\Steam",@"Software\WOW6432Node\Valve\Steam"})try{using(var k=hive.OpenSubKey(keyName)){if(k!=null){object v=k.GetValue("SteamPath")??k.GetValue("InstallPath");if(v!=null)roots.Add(v.ToString());}}}catch{}
        foreach(string root in roots){string found=FromSteam(root);if(found!="")return found;}return "";
    }
    static Stream Resource(string name){Stream s=Assembly.GetExecutingAssembly().GetManifestResourceStream("WakfuPatch."+name);if(s==null)throw new Exception("Kurulum bileşeni bulunamadı: "+name);return s;}
    static void WriteResource(string name,string destination){using(Stream s=Resource(name))using(FileStream f=File.Create(destination))s.CopyTo(f);}
    static string HashFile(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(f)).Replace("-","");}
    static string HashStream(Stream stream){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","");}
    static string HashBytes(byte[] data){using(var memory=new MemoryStream(data))return HashStream(memory);}
    static string HashResource(string name){using(Stream s=Resource(name))return HashStream(s);}
    static Dictionary<string,object> ReadJsonResource(string name){var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};using(var reader=new StreamReader(Resource(name),Encoding.UTF8,true))return serializer.Deserialize<Dictionary<string,object>>(reader.ReadToEnd());}
    static Dictionary<string,object> ReadInstallState(){try{if(!File.Exists(InstallStatePath))return null;var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};return serializer.Deserialize<Dictionary<string,object>>(File.ReadAllText(InstallStatePath,Encoding.UTF8));}catch{return null;}}
    static Dictionary<string,object> ReadInstalledPatchState(){try{if(!File.Exists(InstalledPatchStatePath))return null;var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};return serializer.Deserialize<Dictionary<string,object>>(File.ReadAllText(InstalledPatchStatePath,Encoding.UTF8));}catch{return null;}}
    static Dictionary<string,string> StringDictionary(object value){var result=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);var map=value as Dictionary<string,object>;if(map!=null)foreach(var pair in map)result[pair.Key]=Convert.ToString(pair.Value);return result;}
    static string NormalizeOverheadProfile(string profile){profile=(profile??"").Trim().ToLowerInvariant();if(profile=="normal"||profile=="small"||profile=="tiny")return profile;throw new ArgumentException("Geçersiz baş üstü yazı boyutu. Normal, Küçük veya Çok küçük seçin.");}
    static string ReadOverheadPreference(){try{if(File.Exists(OverheadPreferencePath))return NormalizeOverheadProfile(File.ReadAllText(OverheadPreferencePath,Encoding.UTF8));var state=ReadInstallState();object raw;if(state!=null&&state.TryGetValue("overheadScaleProfile",out raw))return NormalizeOverheadProfile(Convert.ToString(raw));}catch{}return "tiny";}
    static void WriteOverheadPreference(string profile){profile=NormalizeOverheadProfile(profile);Directory.CreateDirectory(StateRoot);string temp=OverheadPreferencePath+"."+Guid.NewGuid().ToString("N")+".tmp";File.WriteAllText(temp,profile,new UTF8Encoding(false));if(File.Exists(OverheadPreferencePath))File.Replace(temp,OverheadPreferencePath,null);else File.Move(temp,OverheadPreferencePath);}
    static string OverheadProfileLabel(string profile){switch(NormalizeOverheadProfile(profile)){case "normal":return "Normal (28 / 24)";case "tiny":return "Çok küçük (20 / 16)";default:return "Küçük (24 / 20)";}}
    static string DistributionVersion(){try{var manifest=ReadJsonResource("distribution_manifest.json");return manifest.ContainsKey("version")?Convert.ToString(manifest["version"]):"bilinmiyor";}catch{return "bilinmiyor";}}
    static void VerifyEmbeddedPackage(){
        var manifest=ReadJsonResource("distribution_manifest.json");object raw;if(!manifest.TryGetValue("resources",out raw))throw new Exception("Dağıtım doğrulama listesi bulunamadı.");
        var expected=StringDictionary(raw);foreach(var pair in expected)if(!String.Equals(HashResource(pair.Key),pair.Value,StringComparison.OrdinalIgnoreCase))throw new Exception("Kurulum EXE bileşeni bozuk veya eksik: "+pair.Key);
    }
    static bool StateMatchesPatched(Dictionary<string,object> state,string game,string key,string livePath){
        if(state==null||!File.Exists(livePath))return false;object rawGame;if(!state.TryGetValue("gameDir",out rawGame))return false;try{if(!String.Equals(Path.GetFullPath(Convert.ToString(rawGame)).TrimEnd('\\'),Path.GetFullPath(game).TrimEnd('\\'),StringComparison.OrdinalIgnoreCase))return false;}catch{return false;}
        object rawPatched;if(!state.TryGetValue("patched",out rawPatched))return false;var patched=StringDictionary(rawPatched);string expected;return patched.TryGetValue(key,out expected)&&String.Equals(HashFile(livePath),expected,StringComparison.OrdinalIgnoreCase);
    }
    static bool IsFullyCurrentInstallation(string game,string overheadProfile){
        overheadProfile=NormalizeOverheadProfile(overheadProfile);
        var state=ReadInstallState();if(state==null)return false;object rawVersion;if(!state.TryGetValue("version",out rawVersion)||!String.Equals(Convert.ToString(rawVersion),DistributionVersion(),StringComparison.OrdinalIgnoreCase))return false;
        object rawProfile;if(!state.TryGetValue("overheadScaleProfile",out rawProfile)||!String.Equals(Convert.ToString(rawProfile),overheadProfile,StringComparison.OrdinalIgnoreCase))return false;
        foreach(var pair in GameFiles(game))if(!StateMatchesPatched(state,game,pair.Key,pair.Value))return false;
        try{var files=GameFiles(game);VerifyPersistentNameOverheadJar(files["client"],overheadProfile);VerifyNameToggleShortcutJar(files["data"]);}catch{return false;}
        return true;
    }
    static void WriteInstallState(string game,Dictionary<string,string> official,Dictionary<string,string> patched,string overheadProfile){
        Directory.CreateDirectory(StateRoot);var record=new Dictionary<string,object>{{"version",DistributionVersion()},{"gameDir",Path.GetFullPath(game)},{"installedAt",DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")},{"overheadScaleProfile",NormalizeOverheadProfile(overheadProfile)},{"official",official},{"patched",patched}};
        var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};string temp=InstallStatePath+"."+Guid.NewGuid().ToString("N")+".tmp";File.WriteAllText(temp,serializer.Serialize(record),new UTF8Encoding(false));if(File.Exists(InstallStatePath))File.Replace(temp,InstallStatePath,null);else File.Move(temp,InstallStatePath);
    }
    static string StateText(Dictionary<string,object> state,string name){object value;return state!=null&&state.TryGetValue(name,out value)&&value!=null?Convert.ToString(value):"";}
    static bool SameGameDirectory(string first,string second){try{return String.Equals(Path.GetFullPath(first).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),Path.GetFullPath(second).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),StringComparison.OrdinalIgnoreCase);}catch{return false;}}
    static int ComparePatchVersions(string left,string right){string[] a=left.Split('.'),b=right.Split('.');for(int i=0;i<4;i++){long x=Int64.Parse(a[i],System.Globalization.CultureInfo.InvariantCulture),y=Int64.Parse(b[i],System.Globalization.CultureInfo.InvariantCulture);if(x!=y)return x<y?-1:1;}return 0;}
    static bool IsReleasedPatchInstalled(string game,PatchManifest manifest){
        var state=ReadInstalledPatchState();if(state==null||!SameGameDirectory(StateText(state,"game_dir"),game)||!String.Equals(StateText(state,"patch_version"),manifest.PatchVersion,StringComparison.Ordinal)||!String.Equals(StateText(state,"sha256"),manifest.Sha256,StringComparison.OrdinalIgnoreCase))return false;
        var files=GameFiles(game);return File.Exists(files["i18n_en"])&&File.Exists(files["i18n"])&&String.Equals(HashFile(files["i18n_en"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase)&&String.Equals(HashFile(files["i18n"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase);
    }
    static void UpdateLegacyInstallStateI18n(string game,string hash){
        var state=ReadInstallState();if(state==null||!SameGameDirectory(StateText(state,"gameDir"),game))return;object raw;var patched=state.TryGetValue("patched",out raw)?raw as Dictionary<string,object>:null;if(patched==null)return;
        patched["i18n_en"]=hash;patched["i18n"]=hash;Directory.CreateDirectory(StateRoot);var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};string temp=InstallStatePath+"."+Guid.NewGuid().ToString("N")+".tmp";File.WriteAllText(temp,serializer.Serialize(state),new UTF8Encoding(false));if(File.Exists(InstallStatePath))File.Replace(temp,InstallStatePath,null);else File.Move(temp,InstallStatePath);
    }
    static string VerifyReleaseBaseline(string game,PatchManifest manifest){
        string live=GameFiles(game)["i18n_en"];
        var candidates=new List<string>();
        var installed=ReadInstalledPatchState();
        string releaseBackup=StateText(installed,"backup_dir");
        if(!String.IsNullOrWhiteSpace(releaseBackup))candidates.Add(Path.Combine(releaseBackup,"i18n_en.jar"));
        candidates.Add(Path.Combine(BackupDir,"i18n_en.jar"));
        candidates.Add(live);
        foreach(string candidate in candidates)
            if(File.Exists(candidate)&&String.Equals(HashFile(candidate),manifest.SourceI18nSha256,StringComparison.OrdinalIgnoreCase))return candidate;
        throw new ReleaseUpdateException("Bu Release, seçilen WAKFU sürümünün temiz i18n_en.jar kaynağıyla uyumlu değil. Oyun güncellemesi için doğru yamayı bekleyin.");
    }
    static string BackupReleaseTargets(Dictionary<string,string> live,PatchManifest manifest){
        string folder=Path.Combine(ReleaseBackupRoot,DateTime.Now.ToString("yyyyMMdd_HHmmss")+"_"+manifest.PatchVersion.Replace('.','_')+"_"+Guid.NewGuid().ToString("N").Substring(0,6));Directory.CreateDirectory(folder);
        foreach(string key in new[]{"i18n_en","i18n"})if(File.Exists(live[key]))File.Copy(live[key],Path.Combine(folder,BackupName(key)),true);
        return folder;
    }
    static void WriteReleasedPatchState(string game,LatestPatchRelease release,PatchManifest manifest,string backup){
        var state=new Dictionary<string,object>{{"game_version",manifest.GameVersion},{"patch_version",manifest.PatchVersion},{"release_id",release.Id},{"release_tag",release.Tag},{"file",manifest.File},{"sha256",manifest.Sha256},{"size",manifest.Size},{"source_i18n_sha256",manifest.SourceI18nSha256},{"game_dir",Path.GetFullPath(game)},{"backup_dir",backup},{"installed_at",DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ssK")}};
        WakfuReleaseUpdater.WriteInstalledPatchState(InstalledPatchStatePath,state);
    }
    static readonly string TokenPattern=@"\\[ntr]|<[^>]*>|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|%[A-Za-z_][A-Za-z0-9_.-]*%";
    static List<string> Tokens(string text){var list=new List<string>();foreach(Match m in Regex.Matches(text??"",TokenPattern))list.Add(m.Value);return list;}
    static List<string> ConditionalShape(string text){var list=new List<string>();text=text??"";int depth=0;for(int i=0;i<text.Length;i++){if(i+1<text.Length&&text[i]=='{'&&text[i+1]=='['){int end=text.IndexOf("]?",i+2,StringComparison.Ordinal);if(end>=0){list.Add(text.Substring(i,end+2-i));depth++;i=end+1;continue;}}if(depth>0&&text[i]==':'&&(i==0||text[i-1]!='\\'))list.Add(":");else if(depth>0&&text[i]=='}'){list.Add("}");depth--;}}if(depth!=0)list.Add("!UNBALANCED:"+depth);return list;}
    static bool SameTokens(List<string>a,List<string>b){if(a.Count!=b.Count)return false;for(int i=0;i<a.Count;i++)if(!String.Equals(a[i],b[i],StringComparison.OrdinalIgnoreCase))return false;return true;}
    static bool SafeFormat(string source,string translated){return SameTokens(Tokens(source),Tokens(translated))&&SameTokens(ConditionalShape(source),ConditionalShape(translated));}
    static string MatchSourceTokenCasing(string source,string translated){var expected=Tokens(source);int index=0;return Regex.Replace(translated??"",TokenPattern,m=>{if(index>=expected.Count)return m.Value;string sourceToken=expected[index++];return String.Equals(sourceToken,m.Value,StringComparison.OrdinalIgnoreCase)?sourceToken:m.Value;});}
    static Dictionary<string,string> ResourceProperties(string resourceName,string entryName){var result=new Dictionary<string,string>(StringComparer.Ordinal);using(Stream resource=Resource(resourceName))using(var jar=new ZipArchive(resource,ZipArchiveMode.Read,false)){ZipArchiveEntry entry=jar.GetEntry(entryName);if(entry==null)return result;using(var reader=new StreamReader(entry.Open(),Encoding.UTF8,true)){string line;while((line=reader.ReadLine())!=null){int pos=line.IndexOf('=');if(pos>0)result[line.Substring(0,pos)]=line.Substring(pos+1);}}}return result;}
    static Dictionary<string,string> StringMap(object value){var result=new Dictionary<string,string>(StringComparer.Ordinal);var map=value as Dictionary<string,object>;if(map!=null)foreach(var p in map)result[p.Key]=Convert.ToString(p.Value);return result;}
    static void RewriteProperties(ZipArchive zip,string entryName,Dictionary<string,string> prepared,Dictionary<string,string> baseline,Dictionary<string,string> translations,Dictionary<string,string> manual,Dictionary<string,string> termKeys,Dictionary<string,string> termValues,Dictionary<string,string> phrases){
        ZipArchiveEntry old=zip.GetEntry(entryName);if(old==null)return;string content;using(var reader=new StreamReader(old.Open(),Encoding.UTF8,true))content=reader.ReadToEnd();string newline=content.Contains("\r\n")?"\r\n":"\n";string[] lines=Regex.Split(content,"\r?\n");
        var phraseKeys=new List<string>(phrases.Keys);phraseKeys.Sort((a,b)=>b.Length.CompareTo(a.Length));
        for(int i=0;i<lines.Length;i++){
            int pos=lines[i].IndexOf('=');if(pos<1)continue;
            string key=lines[i].Substring(0,pos),source=lines[i].Substring(pos+1),candidate=null;bool applyPhrases=true;
            string preparedValue,baselineValue;if(prepared.TryGetValue(key,out preparedValue)&&baseline.TryGetValue(key,out baselineValue)&&source==baselineValue){lines[i]=key+"="+preparedValue;continue;}
            bool protectedName=Regex.IsMatch(key,@"^content\.(3|6|7|8|12|15|20|33|34|35|38|48|54|61|62|77|78|82|89|130|157|159)\.")
                || Regex.IsMatch(key,@"^breed\.\d+$")
                || Regex.IsMatch(key,@"(^|\.)boussole\.")
                || Regex.IsMatch(key,@"^worldName\.")
                || Regex.IsMatch(key,@"^(item|monster|mob|npc|spell|skill|pet|mount)\..*\.name$",RegexOptions.IgnoreCase);
            // Genel değer sözlüğü (Heal -> İyileştir gibi) gerçek eşya,
            // yetenek, NPC ve yaratık adlarını asla geçersiz kılmaz. Yalnız
            // anahtarın kendisine atanmış insan onaylı istisna uygulanabilir.
            if(protectedName&&!manual.ContainsKey(key)&&!termKeys.ContainsKey(key))continue;
            if(manual.ContainsKey(key)){candidate=manual[key];applyPhrases=false;}
            else if(termKeys.ContainsKey(key)){candidate=termKeys[key];applyPhrases=false;}
            else if(termValues.ContainsKey(source)){candidate=termValues[source];applyPhrases=false;}
            else if(translations.ContainsKey(key))candidate=translations[key];
            if(String.IsNullOrWhiteSpace(candidate))continue;
            if(applyPhrases)foreach(string phrase in phraseKeys)candidate=Regex.Replace(candidate,@"(?<![\w])"+Regex.Escape(phrase)+@"(?![\w])",m=>phrases[phrase],RegexOptions.CultureInvariant);
            if(SafeFormat(source,candidate)){candidate=MatchSourceTokenCasing(source,candidate);lines[i]=key+"="+candidate.Replace("\r\n",@"\n").Replace("\n",@"\n");}
        }
        old.Delete();ZipArchiveEntry replacement=zip.CreateEntry(entryName,CompressionLevel.Optimal);using(var writer=new StreamWriter(replacement.Open(),new UTF8Encoding(false)))writer.Write(String.Join(newline,lines));
    }
    static string BuildAdaptivePatch(string officialJar){
        string temp=Path.Combine(Path.GetTempPath(),"WakfuTurkce_"+Guid.NewGuid().ToString("N")+".jar");File.Copy(officialJar,temp,true);var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};Dictionary<string,string> translations;using(var r=new StreamReader(Resource("translations.json"),Encoding.UTF8,true))translations=serializer.Deserialize<Dictionary<string,string>>(r.ReadToEnd());Dictionary<string,string> manual;using(var r=new StreamReader(Resource("manual.json"),Encoding.UTF8,true))manual=serializer.Deserialize<Dictionary<string,string>>(r.ReadToEnd());Dictionary<string,object> terms;using(var r=new StreamReader(Resource("terms.json"),Encoding.UTF8,true))terms=serializer.Deserialize<Dictionary<string,object>>(r.ReadToEnd());var keys=terms.ContainsKey("keys")?StringMap(terms["keys"]):new Dictionary<string,string>();var values=terms.ContainsKey("values")?StringMap(terms["values"]):new Dictionary<string,string>();var phrases=terms.ContainsKey("phrases")?StringMap(terms["phrases"]):new Dictionary<string,string>();var preparedMain=ResourceProperties("i18n.jar","texts_en.properties");var baselineMain=ResourceProperties("base_i18n.jar","texts_en.properties");var preparedClean=ResourceProperties("i18n.jar","texts_en_cleaned.properties");var baselineClean=ResourceProperties("base_i18n.jar","texts_en_cleaned.properties");using(ZipArchive zip=ZipFile.Open(temp,ZipArchiveMode.Update)){RewriteProperties(zip,"texts_en.properties",preparedMain,baselineMain,translations,manual,keys,values,phrases);RewriteProperties(zip,"texts_en_cleaned.properties",preparedClean,baselineClean,translations,manual,keys,values,phrases);}return temp;
    }
    static bool IsUpdatedGame(string game){string installed=Path.Combine(game,"contents","i18n","i18n_en.jar");if(!File.Exists(installed))return false;var state=ReadInstallState();if(StateMatchesPatched(state,game,"i18n_en",installed))return false;string hash=HashFile(installed);return hash!=HashResource("i18n.jar")&&hash!=HashResource("base_i18n.jar");}
    static void EnsureNameToggleShortcut(string dataJar){
        if(!File.Exists(dataJar))throw new Exception("data.jar bulunamadı.");
        const string pattern=@"(?s)(<shortcut\b(?=[^>]*\bid=""showHideNameOverheadsCommand"")[^>]*\bonKeyReleased\s*=\s*"")true("")";
        const string alreadyPattern=@"(?s)<shortcut\b(?=[^>]*\bid=""showHideNameOverheadsCommand"")(?=[^>]*\bkeyCode\s*=\s*""86"")[^>]*\bonKeyReleased\s*=\s*""false""";
        using(ZipArchive zip=ZipFile.Open(dataJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("shortcuts.xml");if(entry==null)throw new Exception("shortcuts.xml bulunamadı.");string text;using(var reader=new StreamReader(entry.Open(),Encoding.UTF8,true))text=reader.ReadToEnd();
            MatchCollection matches=Regex.Matches(text,pattern,RegexOptions.CultureInvariant);if(matches.Count>1)throw new Exception("V oyuncu adı kısayolu birden çok kez bulundu; güvenli geri yükleme yapılmadı.");string restored;
            if(matches.Count==1)restored=Regex.Replace(text,pattern,"${1}false${2}",RegexOptions.CultureInvariant);else if(Regex.IsMatch(text,alreadyPattern,RegexOptions.CultureInvariant))restored=text;else throw new Exception("V oyuncu adı kısayolunun tek basış davranışı bulunamadı.");
            if(restored!=text){entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("shortcuts.xml",CompressionLevel.Optimal);using(var writer=new StreamWriter(replacement.Open(),new UTF8Encoding(false)))writer.Write(restored);}
        }
        VerifyNameToggleShortcutJar(dataJar);
    }
    static int FindUtf8Constant(byte[] data,byte[] value){for(int i=2;i<=data.Length-value.Length;i++){if((((int)data[i-2]<<8)|data[i-1])!=value.Length)continue;bool same=true;for(int j=0;j<value.Length;j++)if(data[i+j]!=value[j]){same=false;break;}if(same)return i;}return -1;}
    static int U2(byte[] data,int offset){return (data[offset]<<8)|data[offset+1];}
    static void PutU2(Stream stream,int value){stream.WriteByte((byte)(value>>8));stream.WriteByte((byte)value);}
    static void PutUtf8(Stream stream,string value){byte[] bytes=Encoding.UTF8.GetBytes(value);stream.WriteByte(1);PutU2(stream,bytes.Length);stream.Write(bytes,0,bytes.Length);}
    static int ConstantPoolEnd(byte[] data,out int count){
        if(data.Length<10||data[0]!=0xCA||data[1]!=0xFE||data[2]!=0xBA||data[3]!=0xBE)throw new InvalidDataException("Geçersiz Java sınıfı.");count=U2(data,8);int p=10;
        for(int i=1;i<count;i++){int tag=data[p++];switch(tag){case 1:int length=U2(data,p);p+=2+length;break;case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;case 7:case 8:case 16:case 19:case 20:p+=2;break;case 9:case 10:case 11:case 12:case 17:case 18:p+=4;break;case 15:p+=3;break;default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);}if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");}return p;
    }
    static int FindBytes(byte[] data,byte[] value){for(int i=0;i<=data.Length-value.Length;i++){bool same=true;for(int j=0;j<value.Length;j++)if(data[i+j]!=value[j]){same=false;break;}if(same)return i;}return -1;}
    static int CountBytes(byte[] data,byte[] value){int found=0;for(int i=0;i<=data.Length-value.Length;i++){bool same=true;for(int j=0;j<value.Length;j++)if(data[i+j]!=value[j]){same=false;break;}if(same)found++;}return found;}
    static byte[] ReplaceUtf8ConstantBytes(byte[] data,string oldValue,string newValue){
        byte[] oldBytes=Encoding.UTF8.GetBytes(oldValue),newBytes=Encoding.UTF8.GetBytes(newValue);int count=U2(data,8),p=10,oldStart=-1,oldCount=0,newCount=0;
        for(int i=1;i<count;i++){int tag=data[p++];switch(tag){case 1:int length=U2(data,p),start=p+2;bool oldSame=length==oldBytes.Length,newSame=length==newBytes.Length;for(int j=0;j<length&&(oldSame||newSame);j++){if(oldSame&&data[start+j]!=oldBytes[j])oldSame=false;if(newSame&&data[start+j]!=newBytes[j])newSame=false;}if(oldSame){oldStart=start;oldCount++;}if(newSame)newCount++;p=start+length;break;case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;case 7:case 8:case 16:case 19:case 20:p+=2;break;case 9:case 10:case 11:case 12:case 17:case 18:p+=4;break;case 15:p+=3;break;default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);}if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");}
        if(oldCount==0&&newCount>0)return data;if(oldCount!=1)throw new InvalidDataException("Java metin sabiti güvenle bulunamadı: "+oldValue);byte[] patched=new byte[data.Length-oldBytes.Length+newBytes.Length];int lengthOffset=oldStart-2;Buffer.BlockCopy(data,0,patched,0,lengthOffset);patched[lengthOffset]=(byte)(newBytes.Length>>8);patched[lengthOffset+1]=(byte)newBytes.Length;Buffer.BlockCopy(newBytes,0,patched,oldStart,newBytes.Length);Buffer.BlockCopy(data,oldStart+oldBytes.Length,patched,oldStart+newBytes.Length,data.Length-oldStart-oldBytes.Length);return patched;
    }
    static byte[] PatchWeatherTimeBytes(byte[] data){
        if(FindUtf8Constant(data,Encoding.UTF8.GetBytes("tr-TR"))>=0&&FindUtf8Constant(data,Encoding.UTF8.GetBytes("forLanguageTag"))>=0)return data;
        int count;int cpEnd=ConstantPoolEnd(data,out count);byte[] oldCall={0xB8,0x00,0x3F,0xB6,0x00,0x3D,0xB6,0x00,0x34};int call=FindBytes(data,oldCall);if(call<0||CountBytes(data,oldCall)!=1)throw new InvalidDataException("Hava durumu saat biçimi bu oyun sürümünde güvenle bulunamadı.");
        int trUtf=count,trString=count+1,localeUtf=count+2,localeClass=count+3,nameUtf=count+4,descUtf=count+5,nameType=count+6,methodRef=count+7;byte[] additions;
        using(var stream=new MemoryStream()){PutUtf8(stream,"tr-TR");stream.WriteByte(8);PutU2(stream,trUtf);PutUtf8(stream,"java/util/Locale");stream.WriteByte(7);PutU2(stream,localeUtf);PutUtf8(stream,"forLanguageTag");PutUtf8(stream,"(Ljava/lang/String;)Ljava/util/Locale;");stream.WriteByte(12);PutU2(stream,nameUtf);PutU2(stream,descUtf);stream.WriteByte(10);PutU2(stream,localeClass);PutU2(stream,nameType);additions=stream.ToArray();}
        byte[] patched=new byte[data.Length+additions.Length];Buffer.BlockCopy(data,0,patched,0,8);patched[8]=(byte)((count+8)>>8);patched[9]=(byte)(count+8);Buffer.BlockCopy(data,10,patched,10,cpEnd-10);Buffer.BlockCopy(additions,0,patched,cpEnd,additions.Length);Buffer.BlockCopy(data,cpEnd,patched,cpEnd+additions.Length,data.Length-cpEnd);int target=call+additions.Length;byte[] newCall={0x13,(byte)(trString>>8),(byte)trString,0xB8,(byte)(methodRef>>8),(byte)methodRef,0x00,0x00,0x00};Buffer.BlockCopy(newCall,0,patched,target,newCall.Length);return patched;
    }
    static byte[] PatchBattlegroundTimeBytes(byte[] data){
        if(FindUtf8Constant(data,Encoding.UTF8.GetBytes("tr-TR"))>=0&&FindUtf8Constant(data,Encoding.UTF8.GetBytes("forLanguageTag"))>=0)return data;
        int count;int cpEnd=ConstantPoolEnd(data,out count);byte[] oldCall={0xB8,0x00,0x73,0xB6,0x00,0x71,0xB6,0x00,0x66};if(CountBytes(data,oldCall)!=3)throw new InvalidDataException("Savaş alanı tarih-saat biçimi bu oyun sürümünde güvenle bulunamadı.");
        int trUtf=count,trString=count+1,localeUtf=count+2,localeClass=count+3,nameUtf=count+4,descUtf=count+5,nameType=count+6,methodRef=count+7;byte[] additions;
        using(var stream=new MemoryStream()){PutUtf8(stream,"tr-TR");stream.WriteByte(8);PutU2(stream,trUtf);PutUtf8(stream,"java/util/Locale");stream.WriteByte(7);PutU2(stream,localeUtf);PutUtf8(stream,"forLanguageTag");PutUtf8(stream,"(Ljava/lang/String;)Ljava/util/Locale;");stream.WriteByte(12);PutU2(stream,nameUtf);PutU2(stream,descUtf);stream.WriteByte(10);PutU2(stream,localeClass);PutU2(stream,nameType);additions=stream.ToArray();}
        byte[] patched=new byte[data.Length+additions.Length];Buffer.BlockCopy(data,0,patched,0,8);patched[8]=(byte)((count+8)>>8);patched[9]=(byte)(count+8);Buffer.BlockCopy(data,10,patched,10,cpEnd-10);Buffer.BlockCopy(additions,0,patched,cpEnd,additions.Length);Buffer.BlockCopy(data,cpEnd,patched,cpEnd+additions.Length,data.Length-cpEnd);byte[] newCall={0x13,(byte)(trString>>8),(byte)trString,0xB8,(byte)(methodRef>>8),(byte)methodRef,0x00,0x00,0x00};for(int n=0;n<3;n++){int target=FindBytes(patched,oldCall);if(target<0)throw new InvalidDataException("Savaş alanı tarih-saat çağrısı eksik kaldı.");Buffer.BlockCopy(newCall,0,patched,target,newCall.Length);}return patched;
    }
    static void CountPersistentNameOverheadPatterns(byte[] data,out int original,out int legacyBad,out int safeCount){
        original=-1;legacyBad=-1;safeCount=0;int originalCount=0,legacyBadCount=0;
        for(int i=0;i<=data.Length-9;i++){
            bool tail=data[i+3]==0x07&&data[i+4]==0x2A&&data[i+5]==0xB6&&data[i+8]==0xB1;if(!tail)continue;
            if(data[i]==0x1B&&data[i+1]==0x9A&&data[i+2]==0x00){original=i;originalCount++;}
            if(data[i]==0xA7&&data[i+1]==0x00&&data[i+2]==0x08){legacyBad=i;legacyBadCount++;}
            if(data[i]==0x04&&data[i+1]==0x9A&&data[i+2]==0x00)safeCount++;
        }
        if(originalCount!=1)original=-1;if(legacyBadCount!=1)legacyBad=-1;if(originalCount>1||legacyBadCount>1)safeCount=-1;
    }
    static bool HasSafePersistentNameOverheadBytes(byte[] data){int original,legacyBad,safeCount;CountPersistentNameOverheadPatterns(data,out original,out legacyBad,out safeCount);return original<0&&legacyBad<0&&safeCount==1;}
    static byte[] PatchPersistentNameOverheadBytes(byte[] data){
        int original,legacyBad,safeCount;CountPersistentNameOverheadPatterns(data,out original,out legacyBad,out safeCount);
        if(original<0&&legacyBad<0&&safeCount==1)return data;int target=original>=0?original:legacyBad;
        if(target<0||safeCount!=0)throw new InvalidDataException("Kalıcı V oyuncu adı yaşam döngüsü bu oyun sürümünde güvenle bulunamadı.");
        byte[] patched=(byte[])data.Clone();patched[target]=0x04;patched[target+1]=0x9A;patched[target+2]=0x00;patched[target+3]=0x07;if(!HasSafePersistentNameOverheadBytes(patched))throw new InvalidDataException("Kalıcı V oyuncu adı yaması doğrulanamadı.");return patched;
    }
    static int U4(byte[] data,int offset){if(offset<0||offset+4>data.Length)throw new InvalidDataException("Eksik Java sinifi.");long value=((long)data[offset]<<24)|((long)data[offset+1]<<16)|((long)data[offset+2]<<8)|data[offset+3];if(value>Int32.MaxValue)throw new InvalidDataException("Java sinifi bolumu cok buyuk.");return(int)value;}
    static int SkipJavaAttributes(byte[] data,int position,int count){for(int i=0;i<count;i++){if(position+6>data.Length)throw new InvalidDataException("Eksik Java ozniteligi.");int length=U4(data,position+2);position+=6;if(position+length>data.Length)throw new InvalidDataException("Eksik Java ozniteligi.");position+=length;}return position;}
    static int LocateHoverCompatibleNameToggleTail(byte[] data,out bool patched){
        int cpCount;int cpEnd=ConstantPoolEnd(data,out cpCount);var tags=new byte[cpCount];var first=new int[cpCount];var second=new int[cpCount];var utf8=new string[cpCount];int p=10;
        for(int i=1;i<cpCount;i++){int tag=data[p++];tags[i]=(byte)tag;switch(tag){
            case 1:int length=U2(data,p);p+=2;utf8[i]=Encoding.UTF8.GetString(data,p,length);p+=length;break;
            case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;
            case 7:case 8:case 16:case 19:case 20:first[i]=U2(data,p);p+=2;break;
            case 9:case 10:case 11:case 12:case 17:case 18:first[i]=U2(data,p);second[i]=U2(data,p+2);p+=4;break;
            case 15:first[i]=data[p];second[i]=U2(data,p+1);p+=3;break;
            default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);
        }if(p>data.Length)throw new InvalidDataException("Eksik Java sinifi.");}
        if(p!=cpEnd||p+8>data.Length)throw new InvalidDataException("Eksik Java sinifi govdesi.");int thisClass=U2(data,p+2);p+=6;int interfaceCount=U2(data,p);p+=2+2*interfaceCount;
        if(p+2>data.Length)throw new InvalidDataException("Eksik Java alan tablosu.");int fieldCount=U2(data,p);p+=2;for(int i=0;i<fieldCount;i++){if(p+8>data.Length)throw new InvalidDataException("Eksik Java alani.");int attributes=U2(data,p+6);p=SkipJavaAttributes(data,p+8,attributes);}
        if(p+2>data.Length)throw new InvalidDataException("Eksik Java yontem tablosu.");int methodCount=U2(data,p);p+=2;int target=-1,candidates=0;bool targetPatched=false,hasCwc=false;
        for(int i=0;i<methodCount;i++){if(p+8>data.Length)throw new InvalidDataException("Eksik Java yontemi.");int nameIndex=U2(data,p+2),descriptorIndex=U2(data,p+4),attributeCount=U2(data,p+6);string methodName=utf8[nameIndex],descriptor=utf8[descriptorIndex];p+=8;if(methodName=="cWC"&&descriptor=="()V")hasCwc=true;
            for(int j=0;j<attributeCount;j++){if(p+6>data.Length)throw new InvalidDataException("Eksik Java yontem ozniteligi.");int attributeName=U2(data,p),attributeLength=U4(data,p+2),info=p+6;if(info+attributeLength>data.Length)throw new InvalidDataException("Eksik Java yontem ozniteligi.");
                if(methodName=="a"&&utf8[attributeName]=="Code"){if(attributeLength<12)throw new InvalidDataException("Eksik Java kod ozniteligi.");int codeLength=U4(data,info+4),codeStart=info+8,codeEnd=codeStart+codeLength;if(codeEnd>info+attributeLength||codeLength<4)throw new InvalidDataException("Eksik Java yontem kodu.");bool isPatched=data[codeEnd-4]==0x00&&data[codeEnd-3]==0x00&&data[codeEnd-2]==0x00&&data[codeEnd-1]==0xB1;bool isOriginal=false;if(data[codeEnd-4]==0xB8&&data[codeEnd-1]==0xB1){int methodRef=U2(data,codeEnd-3);if(methodRef>0&&methodRef<cpCount&&tags[methodRef]==10&&first[methodRef]==thisClass){int nameType=second[methodRef];isOriginal=nameType>0&&nameType<cpCount&&tags[nameType]==12&&utf8[first[nameType]]=="cWC"&&utf8[second[nameType]]=="()V";}}if(isOriginal||isPatched){target=codeEnd-4;targetPatched=isPatched;candidates++;}}
                p=info+attributeLength;
            }
        }
        if(!hasCwc||candidates!=1||target<0)throw new InvalidDataException("V fare ustu uyumluluk noktasi bu oyun surumunde guvenle bulunamadi.");patched=targetPatched;return target;
    }
    static bool HasHoverCompatibleNameToggleBytes(byte[] data){try{bool patched;LocateHoverCompatibleNameToggleTail(data,out patched);return patched;}catch{return false;}}
    static byte[] PatchHoverCompatibleNameToggleBytes(byte[] data){bool patched;int target=LocateHoverCompatibleNameToggleTail(data,out patched);if(patched)return data;byte[] result=(byte[])data.Clone();result[target]=0x00;result[target+1]=0x00;result[target+2]=0x00;if(!HasHoverCompatibleNameToggleBytes(result))throw new InvalidDataException("V acikken fare ustu ad yamasi dogrulanamadi.");return result;}
    static void LocateOverheadFontPair(byte[] data,out string currentProfile,out int mainOffset,out int titleOffset){
        var offsets=new Dictionary<string,int>(StringComparer.Ordinal);int fontEntries=0,count=U2(data,8),p=10;
        for(int i=1;i<count;i++){
            if(p>=data.Length)throw new InvalidDataException("Eksik Java sınıfı.");int tag=data[p++];
            switch(tag){
                case 1:
                    if(p+2>data.Length)throw new InvalidDataException("Eksik Java metin sabiti.");int length=U2(data,p),start=p+2;if(start+length>data.Length)throw new InvalidDataException("Eksik Java metin sabiti.");string value=Encoding.UTF8.GetString(data,start,length);p=start+length;
                    if(value.StartsWith("fontNarrow",StringComparison.Ordinal)&&value.EndsWith("BoldBordered",StringComparison.Ordinal)){
                        fontEntries++;if(value!="fontNarrow28BoldBordered"&&value!="fontNarrow24BoldBordered"&&value!="fontNarrow20BoldBordered"&&value!="fontNarrow16BoldBordered")throw new InvalidDataException("Desteklenmeyen baş üstü yazı stili bulundu: "+value);
                        if(offsets.ContainsKey(value))throw new InvalidDataException("Baş üstü yazı stili birden çok kez bulundu: "+value);offsets[value]=start;
                    }
                    break;
                case 3:case 4:p+=4;break;case 5:case 6:p+=8;i++;break;case 7:case 8:case 16:case 19:case 20:p+=2;break;case 9:case 10:case 11:case 12:case 17:case 18:p+=4;break;case 15:p+=3;break;default:throw new InvalidDataException("Desteklenmeyen sabit havuzu etiketi: "+tag);
            }
            if(p>data.Length)throw new InvalidDataException("Eksik Java sınıfı.");
        }
        currentProfile=null;mainOffset=-1;titleOffset=-1;if(fontEntries!=2)throw new InvalidDataException("Baş üstü yazı font çifti güvenle bulunamadı.");
        if(offsets.ContainsKey("fontNarrow28BoldBordered")&&offsets.ContainsKey("fontNarrow24BoldBordered")){currentProfile="normal";mainOffset=offsets["fontNarrow28BoldBordered"];titleOffset=offsets["fontNarrow24BoldBordered"];}
        else if(offsets.ContainsKey("fontNarrow24BoldBordered")&&offsets.ContainsKey("fontNarrow20BoldBordered")){currentProfile="small";mainOffset=offsets["fontNarrow24BoldBordered"];titleOffset=offsets["fontNarrow20BoldBordered"];}
        else if(offsets.ContainsKey("fontNarrow20BoldBordered")&&offsets.ContainsKey("fontNarrow16BoldBordered")){currentProfile="tiny";mainOffset=offsets["fontNarrow20BoldBordered"];titleOffset=offsets["fontNarrow16BoldBordered"];}
        else throw new InvalidDataException("Baş üstü yazı font çifti tanınmıyor; güvenli yama uygulanmadı.");
    }
    static byte[] PatchOverheadFontProfileBytes(byte[] data,string desiredProfile){
        desiredProfile=NormalizeOverheadProfile(desiredProfile);string currentProfile;int mainOffset,titleOffset;LocateOverheadFontPair(data,out currentProfile,out mainOffset,out titleOffset);if(currentProfile==desiredProfile)return data;
        string main=desiredProfile=="normal"?"fontNarrow28BoldBordered":desiredProfile=="small"?"fontNarrow24BoldBordered":"fontNarrow20BoldBordered";
        string title=desiredProfile=="normal"?"fontNarrow24BoldBordered":desiredProfile=="small"?"fontNarrow20BoldBordered":"fontNarrow16BoldBordered";
        byte[] mainBytes=Encoding.UTF8.GetBytes(main),titleBytes=Encoding.UTF8.GetBytes(title);if(mainBytes.Length!=24||titleBytes.Length!=24)throw new InvalidDataException("Baş üstü yazı stili uzunluğu beklenenden farklı.");byte[] patched=(byte[])data.Clone();Buffer.BlockCopy(mainBytes,0,patched,mainOffset,mainBytes.Length);Buffer.BlockCopy(titleBytes,0,patched,titleOffset,titleBytes.Length);
        string verified;int ignoredMain,ignoredTitle;LocateOverheadFontPair(patched,out verified,out ignoredMain,out ignoredTitle);if(verified!=desiredProfile)throw new InvalidDataException("Baş üstü yazı boyutu doğrulanamadı.");return patched;
    }
    static void PatchCharacterChoiceTitle(string clientJar){
        if(!File.Exists(clientJar))throw new Exception("wakfu-client.jar bulunamadı.");
        using(ZipArchive zip=ZipFile.Open(clientJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("cOt.class");if(entry==null)throw new Exception("Karakter seçim arayüzü bulunamadı.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}
            byte[] oldValue=Encoding.UTF8.GetBytes("%selection% %yourCharacter%"),newValue=Encoding.UTF8.GetBytes("Karakterini Seç");int index=FindUtf8Constant(data,oldValue);if(index<0){if(FindUtf8Constant(data,newValue)>=0)return;throw new Exception("Karakter seçimi başlık kalıbı bu oyun sürümünde bulunamadı.");}
            byte[] patched=new byte[data.Length-oldValue.Length+newValue.Length];Buffer.BlockCopy(data,0,patched,0,index-2);patched[index-2]=(byte)(newValue.Length>>8);patched[index-1]=(byte)(newValue.Length&255);Buffer.BlockCopy(newValue,0,patched,index,newValue.Length);Buffer.BlockCopy(data,index+oldValue.Length,patched,index+newValue.Length,data.Length-index-oldValue.Length);
            entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("cOt.class",CompressionLevel.Optimal);using(Stream output=replacement.Open())output.Write(patched,0,patched.Length);
        }
    }
    static void PatchWeatherTimeFormat(string clientJar){
        if(!File.Exists(clientJar))throw new Exception("wakfu-client.jar bulunamadı.");
        using(ZipArchive zip=ZipFile.Open(clientJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("bSn.class");if(entry==null)throw new Exception("Hava durumu saat biçimi sınıfı bulunamadı.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}byte[] patched=PatchWeatherTimeBytes(data);if(patched.Length==data.Length)return;entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("bSn.class",CompressionLevel.Optimal);using(Stream output=replacement.Open())output.Write(patched,0,patched.Length);
        }
    }
    static void PatchBattlegroundTimeFormat(string clientJar){
        if(!File.Exists(clientJar))throw new Exception("wakfu-client.jar bulunamadı.");
        using(ZipArchive zip=ZipFile.Open(clientJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("bhw.class");if(entry==null)throw new Exception("Savaş alanı tarih-saat biçimi sınıfı bulunamadı.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}byte[] patched=PatchBattlegroundTimeBytes(data);if(patched.Length==data.Length)return;entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("bhw.class",CompressionLevel.Optimal);using(Stream output=replacement.Open())output.Write(patched,0,patched.Length);
        }
    }
    static void PatchAchievementTotalLabel(string clientJar){
        if(!File.Exists(clientJar))throw new Exception("wakfu-client.jar bulunamadı.");
        using(ZipArchive zip=ZipFile.Open(clientJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("cQS.class");if(entry==null)throw new Exception("Başarım kök etiketi sınıfı bulunamadı.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}byte[] patched=ReplaceUtf8ConstantBytes(data,"Total","Toplam");if(patched.Length==data.Length)return;entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("cQS.class",CompressionLevel.Optimal);using(Stream output=replacement.Open())output.Write(patched,0,patched.Length);
        }
    }
    static void PatchPersistentNameOverhead(string clientJar,string overheadProfile){
        if(!File.Exists(clientJar))throw new Exception("wakfu-client.jar bulunamadı.");
        using(ZipArchive zip=ZipFile.Open(clientJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("dde.class");if(entry==null)throw new Exception("Oyuncu adı yaşam döngüsü sınıfı bulunamadı.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}byte[] patched=PatchPersistentNameOverheadBytes(data);patched=PatchOverheadFontProfileBytes(patched,overheadProfile);if(!Object.ReferenceEquals(patched,data)){entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("dde.class",CompressionLevel.Optimal);using(Stream output=replacement.Open())output.Write(patched,0,patched.Length);}
            const string commandName="com/ankamagames/wakfu/client/console/command/display/ShowNameAndHighlightElementsCommand.class";ZipArchiveEntry command=zip.GetEntry(commandName);if(command==null)throw new Exception("V ac/kapat komutu bulunamadi.");byte[] commandData;using(Stream input=command.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);commandData=memory.ToArray();}byte[] patchedCommand=PatchHoverCompatibleNameToggleBytes(commandData);if(!Object.ReferenceEquals(patchedCommand,commandData)){command.Delete();ZipArchiveEntry replacement=zip.CreateEntry(commandName,CompressionLevel.Optimal);using(Stream output=replacement.Open())output.Write(patchedCommand,0,patchedCommand.Length);}
        }
        VerifyPersistentNameOverheadJar(clientJar,overheadProfile);VerifyHoverCompatibleNameToggleJar(clientJar);
    }
    static void PatchAlmanaxDescription(string clientJar){
        const string expectedOriginal="F643B6AFF261B0BC917820FF0B01AC9DD58DDCD2A24DAA1F2C2A87BD6D45E978";
        const string previousTalentyrePatch="225FD3F7E76BA1A9B5A9A63437751FB3DCD8102D575D616F6FE765B576360BE4";
        const string previousTalentyreDywPatch="EC1A3D53592124B8FEB90F36CACB98F35092F611BDD12EC3F8FD34EE93CBBFA2";
        const string previousTalentyreDywSoPatch="97D497AA8CF88C994DC6F5CEC2DDD7D6914A2E5617040AE9EBCF701572DF411F";
        const string previousBitkyoCurlyPatch="88D052C0237DC30D8B61EEDC49946D9799F7607914C47B9B6BA3A9427FA6351E";
        const string resourceName="almanax_bgU.class";
        if(!File.Exists(clientJar))throw new Exception("wakfu-client.jar bulunamadı.");
        string patchedHash=HashResource(resourceName);
        using(ZipArchive zip=ZipFile.Open(clientJar,ZipArchiveMode.Update)){
            ZipArchiveEntry entry=zip.GetEntry("bgU.class");if(entry==null)throw new Exception("Almanax açıklama sınıfı bulunamadı.");
            byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}
            string currentHash=HashBytes(data);if(currentHash==patchedHash)return;
            if(currentHash!=expectedOriginal&&currentHash!=previousTalentyrePatch&&currentHash!=previousTalentyreDywPatch&&currentHash!=previousTalentyreDywSoPatch&&currentHash!=previousBitkyoCurlyPatch)throw new Exception("Almanax açıklama sınıfı bu oyun sürümünde değişmiş; güvenli yama uygulanmadı.");
            entry.Delete();ZipArchiveEntry replacement=zip.CreateEntry("bgU.class",CompressionLevel.Optimal);using(Stream input=Resource(resourceName))using(Stream output=replacement.Open())input.CopyTo(output);
        }
        using(ZipArchive zip=ZipFile.OpenRead(clientJar)){ZipArchiveEntry entry=zip.GetEntry("bgU.class");if(entry==null)throw new Exception("Almanax açıklama yaması doğrulanamadı.");using(Stream input=entry.Open())if(HashStream(input)!=patchedHash)throw new Exception("Almanax açıklama yaması doğrulanamadı.");}
    }
    static bool IsIsolatedDistributionTest(string game){
        string state=Environment.GetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT");if(String.IsNullOrWhiteSpace(state))return false;
        string stateRoot=Path.GetFullPath(state).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);string fixture=Path.GetDirectoryName(stateRoot);if(String.IsNullOrWhiteSpace(fixture))return false;
        string tempRoot=Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar)+Path.DirectorySeparatorChar;
        string fixtureRoot=Path.GetFullPath(fixture).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);string expectedGame=Path.Combine(fixtureRoot,"game");
        return fixtureRoot.StartsWith(tempRoot,StringComparison.OrdinalIgnoreCase)&&Path.GetFileName(fixtureRoot).StartsWith("WakfuDagitimTest_",StringComparison.OrdinalIgnoreCase)&&String.Equals(Path.GetFullPath(game).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),expectedGame,StringComparison.OrdinalIgnoreCase);
    }
    static void EnsureClosed(string game){if(IsIsolatedDistributionTest(game))return;foreach(var n in new[]{"Wakfu","java","javaw","Ankama Launcher","zaap"})if(System.Diagnostics.Process.GetProcessesByName(n).Length>0)throw new Exception("Kurulumdan önce Wakfu ve Ankama Launcher tamamen kapatılmalıdır.");}
    static Dictionary<string,string> GameFiles(string game){return new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase){{"i18n_en",Path.Combine(game,"contents","i18n","i18n_en.jar")},{"i18n",Path.Combine(game,"contents","i18n","i18n.jar")},{"gui",Path.Combine(game,"contents","gui_jar","gui.jar")},{"client",Path.Combine(game,"lib","wakfu-client.jar")},{"data",Path.Combine(game,"contents","data","data.jar")}};}
    static string BackupName(string key){switch(key){case "i18n_en":return "i18n_en.jar";case "i18n":return "i18n.jar";case "gui":return "gui.jar";case "client":return "wakfu-client.jar";default:return "data.jar";}}
    static void ArchiveExistingBackups(){
        if(!Directory.Exists(BackupDir))return;string[] files=Directory.GetFiles(BackupDir);if(files.Length==0)return;string archive=Path.Combine(ArchiveDir,DateTime.Now.ToString("yyyyMMdd_HHmmss")+"_"+Guid.NewGuid().ToString("N").Substring(0,6));Directory.CreateDirectory(archive);foreach(string file in files)File.Copy(file,Path.Combine(archive,Path.GetFileName(file)),true);
    }
    static Dictionary<string,string> PrepareOfficialSources(string game,string officialDir,bool preferExistingI18nBackups=false){
        Directory.CreateDirectory(officialDir);Directory.CreateDirectory(BackupDir);var state=ReadInstallState();var files=GameFiles(game);var result=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);bool archived=false;
        foreach(string key in new[]{"i18n_en","i18n","gui","client","data"}){
            string live=files[key];string backup=Path.Combine(BackupDir,BackupName(key));
            // Temiz Steam kurulumu, oyun ilk kez açılana kadar etkin i18n.jar
            // dosyasını içermeyebilir. Bu durumda resmi i18n_en.jar hem temiz
            // kaynak hem de geri yükleme kopyası olarak güvenle kullanılabilir.
            if(!File.Exists(live)&&key=="i18n"){
                if(!result.ContainsKey("i18n_en"))throw new Exception("Temiz İngilizce dil paketi hazırlanamadı: "+files["i18n_en"]);
                string source=result["i18n_en"];
                if(File.Exists(backup)&&!String.Equals(HashFile(backup),HashFile(source),StringComparison.OrdinalIgnoreCase)&&!archived){ArchiveExistingBackups();archived=true;}
                File.Copy(source,backup,true);string stagedFallback=Path.Combine(officialDir,BackupName(key));File.Copy(source,stagedFallback,true);result[key]=stagedFallback;continue;
            }
            if(!File.Exists(live))throw new Exception("Oyun bileşeni bulunamadı: "+live);bool patched=StateMatchesPatched(state,game,key,live);
            if(!patched&&(key=="i18n_en"||key=="i18n")&&String.Equals(HashFile(live),HashResource("i18n.jar"),StringComparison.OrdinalIgnoreCase))patched=true;
            if(!patched&&preferExistingI18nBackups&&(key=="i18n_en"||key=="i18n")&&File.Exists(backup))patched=true;
            string official;
            if(patched){if(!File.Exists(backup))throw new Exception("Kurulu Türkçe yama algılandı ancak temiz resmi yedek eksik: "+BackupName(key)+". Steam'de dosya doğrulaması yaptıktan sonra yeniden deneyin.");official=backup;}
            else{official=live;if(File.Exists(backup)&&!String.Equals(HashFile(backup),HashFile(official),StringComparison.OrdinalIgnoreCase)&&!archived){ArchiveExistingBackups();archived=true;}File.Copy(official,backup,true);}
            string staged=Path.Combine(officialDir,BackupName(key));File.Copy(official,staged,true);result[key]=staged;
        }
        return result;
    }
    static void PatchGuiFonts(string gui){
        using(ZipArchive zip=ZipFile.Open(gui,ZipArchiveMode.Update))foreach(string font in Fonts){ZipArchiveEntry old=zip.GetEntry("theme/fonts/"+font);if(old==null)throw new Exception("Font hedefi bu oyun sürümünde bulunamadı: "+font);old.Delete();ZipArchiveEntry entry=zip.CreateEntry("theme/fonts/"+font,CompressionLevel.Optimal);using(Stream input=Resource(font))using(Stream output=entry.Open())input.CopyTo(output);}
        using(ZipArchive zip=ZipFile.OpenRead(gui))foreach(string font in Fonts){ZipArchiveEntry entry=zip.GetEntry("theme/fonts/"+font);if(entry==null)throw new Exception("Türkçe font kurulamadı: "+font);using(Stream input=entry.Open())if(HashStream(input)!=HashResource(font))throw new Exception("Türkçe font doğrulanamadı: "+font);}
    }
    static void VerifyJar(string path,string entry){if(!File.Exists(path)||new FileInfo(path).Length==0)throw new Exception("Hazırlanan bileşen eksik: "+Path.GetFileName(path));using(ZipArchive zip=ZipFile.OpenRead(path))if(zip.GetEntry(entry)==null)throw new Exception("Hazırlanan bileşen doğrulanamadı: "+Path.GetFileName(path));}
    static void VerifyPersistentNameOverheadJar(string path,string overheadProfile){using(ZipArchive zip=ZipFile.OpenRead(path)){ZipArchiveEntry entry=zip.GetEntry("dde.class");if(entry==null)throw new Exception("V oyuncu adı sınıfı doğrulanamadı.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}if(!HasSafePersistentNameOverheadBytes(data))throw new Exception("V oyuncu adı aç/kapat yaması güvenlik doğrulamasından geçmedi.");string actual;int mainOffset,titleOffset;LocateOverheadFontPair(data,out actual,out mainOffset,out titleOffset);if(!String.Equals(actual,NormalizeOverheadProfile(overheadProfile),StringComparison.Ordinal))throw new Exception("Seçilen baş üstü yazı boyutu doğrulanamadı.");}}
    static void VerifyNameToggleShortcutJar(string path){const string expected=@"(?s)<shortcut\b(?=[^>]*\bid=""showHideNameOverheadsCommand"")(?=[^>]*\bkeyCode\s*=\s*""86"")(?=[^>]*\bonKeyReleased\s*=\s*""false"")[^>]*>";using(ZipArchive zip=ZipFile.OpenRead(path)){ZipArchiveEntry entry=zip.GetEntry("shortcuts.xml");if(entry==null)throw new Exception("V tuşu ayarı doğrulanamadı.");string text;using(var reader=new StreamReader(entry.Open(),Encoding.UTF8,true))text=reader.ReadToEnd();if(Regex.Matches(text,expected,RegexOptions.CultureInvariant).Count!=1)throw new Exception("V tuşunun basış başına tek aç/kapat davranışı doğrulanamadı.");}}
    static void VerifyHoverCompatibleNameToggleJar(string path){const string commandName="com/ankamagames/wakfu/client/console/command/display/ShowNameAndHighlightElementsCommand.class";using(ZipArchive zip=ZipFile.OpenRead(path)){ZipArchiveEntry entry=zip.GetEntry(commandName);if(entry==null)throw new Exception("V ac/kapat komutu dogrulanamadi.");byte[] data;using(Stream input=entry.Open())using(var memory=new MemoryStream()){input.CopyTo(memory);data=memory.ToArray();}if(!HasHoverCompatibleNameToggleBytes(data))throw new Exception("V acikken fare ustu ad davranisi dogrulanamadi.");}}
    static void VerifyClientWithGameJava(string game,string clientJar){
        string java=Path.Combine(game,"jre","bin","java.exe");if(!File.Exists(java))return;
        var start=new System.Diagnostics.ProcessStartInfo{FileName=java,Arguments="-Xverify:all -cp \""+Path.GetFullPath(clientJar)+";"+Path.Combine(game,"lib","*")+"\" dde",UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
        string output=RunVerificationProcess(start);if(output.IndexOf("VerifyError",StringComparison.OrdinalIgnoreCase)>=0||output.IndexOf("Main method not found in class dde",StringComparison.OrdinalIgnoreCase)<0)throw new Exception("V oyuncu adı sınıfı Java doğrulamasından geçmedi."+Environment.NewLine+output);
        var startCommand=new System.Diagnostics.ProcessStartInfo{FileName=java,Arguments="-Xverify:all -cp \""+Path.GetFullPath(clientJar)+";"+Path.Combine(game,"lib","*")+"\" com.ankamagames.wakfu.client.console.command.display.ShowNameAndHighlightElementsCommand",UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
        output=RunVerificationProcess(startCommand);if(output.IndexOf("VerifyError",StringComparison.OrdinalIgnoreCase)>=0||output.IndexOf("Main method not found in class",StringComparison.OrdinalIgnoreCase)<0)throw new Exception("V fare ustu uyumluluk sinifi Java dogrulamasindan gecmedi."+Environment.NewLine+output);
    }
    static string RunVerificationProcess(System.Diagnostics.ProcessStartInfo start){
        using(var process=new System.Diagnostics.Process{StartInfo=start}){process.Start();Task<string> stdout=process.StandardOutput.ReadToEndAsync();Task<string> stderr=process.StandardError.ReadToEndAsync();if(!process.WaitForExit(60000)){try{process.Kill();process.WaitForExit(5000);}catch{}throw new TimeoutException("Java doğrulaması 60 saniye içinde tamamlanmadı.");}Task.WaitAll(stdout,stderr);return stdout.Result+Environment.NewLine+stderr.Result;}
    }
    static void CopyFileWithRetry(string source,string target){
        for(int attempt=0;;attempt++)try{File.Copy(source,target,true);return;}catch(Exception ex){if(!(ex is IOException)&&!(ex is UnauthorizedAccessException))throw;if(attempt>=11)throw;System.Threading.Thread.Sleep(250);}
    }
    static void ReplaceFileAtomically(string source,string target){
        string directory=Path.GetDirectoryName(target);if(String.IsNullOrWhiteSpace(directory))throw new IOException("Invalid install target: "+target);Directory.CreateDirectory(directory);
        string temporary=Path.Combine(directory,"."+Path.GetFileName(target)+"."+Guid.NewGuid().ToString("N")+".new");
        try{CopyFileWithRetry(source,temporary);if(!String.Equals(HashFile(source),HashFile(temporary),StringComparison.OrdinalIgnoreCase))throw new IOException("Temporary install file could not be verified: "+Path.GetFileName(target));if(File.Exists(target))File.Replace(temporary,target,null);else File.Move(temporary,target);}finally{if(File.Exists(temporary))try{File.Delete(temporary);}catch{}}
    }
    static void CommitTransaction(Dictionary<string,string> stagedByTarget,string transactionRoot){
        string rollback=Path.Combine(transactionRoot,"rollback");Directory.CreateDirectory(rollback);var backups=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);var committed=new List<string>();
        try{
            int index=0;foreach(var pair in stagedByTarget){Directory.CreateDirectory(Path.GetDirectoryName(pair.Key));string old=Path.Combine(rollback,(index++).ToString("D2")+"_"+Path.GetFileName(pair.Key));if(File.Exists(pair.Key)){File.Copy(pair.Key,old,true);backups[pair.Key]=old;}committed.Add(pair.Key);CopyFileWithRetry(pair.Value,pair.Key);if(!String.Equals(HashFile(pair.Value),HashFile(pair.Key),StringComparison.OrdinalIgnoreCase))throw new Exception("Kurulum sonrası dosya özeti eşleşmedi: "+Path.GetFileName(pair.Key));}
        }catch(Exception ex){foreach(string target in committed)try{string old;if(backups.TryGetValue(target,out old))CopyFileWithRetry(old,target);else if(File.Exists(target))File.Delete(target);}catch{}throw new Exception("Kurulum tamamlanamadı; değiştirilen dosyalar otomatik geri alındı."+Environment.NewLine+"Ayrıntı: "+ex.Message,ex);}
    }
    // The release updater changes only the two i18n targets.  Its transaction
    // is intentionally separate from the legacy five-file installer so the
    // existing font, UI and client fixes remain untouched.
    static void CommitReleaseI18nTransaction(Dictionary<string,string> stagedByTarget,string transactionRoot){
        string rollback=Path.Combine(transactionRoot,"rollback");Directory.CreateDirectory(rollback);var backups=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);var committed=new List<string>();
        try{int index=0;foreach(var pair in stagedByTarget){string old=Path.Combine(rollback,(index++).ToString("D2")+"_"+Path.GetFileName(pair.Key));if(File.Exists(pair.Key)){File.Copy(pair.Key,old,true);backups[pair.Key]=old;}committed.Add(pair.Key);ReplaceFileAtomically(pair.Value,pair.Key);if(!String.Equals(HashFile(pair.Value),HashFile(pair.Key),StringComparison.OrdinalIgnoreCase))throw new IOException("Installed release file hash differs: "+Path.GetFileName(pair.Key));}}
        catch(Exception ex){for(int i=committed.Count-1;i>=0;i--)try{string old;if(backups.TryGetValue(committed[i],out old))ReplaceFileAtomically(old,committed[i]);else if(File.Exists(committed[i]))File.Delete(committed[i]);}catch{}throw new ReleaseUpdateException("Release kurulumu tamamlanamadı; eski i18n dosyaları otomatik geri alındı.",ex);}
    }
    static string ReadStateBytesAsText(string path){return File.Exists(path)?File.ReadAllText(path,Encoding.UTF8):null;}
    static void RestoreStateText(string path,string original){string temporary=path+"."+Guid.NewGuid().ToString("N")+".restore";try{if(original==null){if(File.Exists(path))File.Delete(path);return;}Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(temporary,original,new UTF8Encoding(false));if(File.Exists(path))File.Replace(temporary,path,null);else File.Move(temporary,path);}finally{if(File.Exists(temporary))try{File.Delete(temporary);}catch{}}}
    static void RestoreReleaseI18nTargets(Dictionary<string,string> live,string backup,string transaction){var staged=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);foreach(string key in new[]{"i18n_en","i18n"}){string old=Path.Combine(backup,BackupName(key));if(File.Exists(old))staged[live[key]]=old;}if(staged.Count>0)CommitReleaseI18nTransaction(staged,transaction);foreach(string key in new[]{"i18n_en","i18n"})if(!File.Exists(Path.Combine(backup,BackupName(key)))&&File.Exists(live[key]))File.Delete(live[key]);}
    static void InstallReleasedPatch(string game,string overheadProfile,LatestPatchRelease release,PatchManifest manifest,Action<string> progress){InstallReleasedPatchCore(game,overheadProfile,release,manifest,progress,null);}
#if WAKFU_TESTS
    internal static void TestInstallReleasedPatch(string game,LatestPatchRelease release,PatchManifest manifest,IReleaseHttpTransport transport){WakfuReleaseUpdater.TestTransportOverride=transport;try{InstallReleasedPatchCore(game,"tiny",release,manifest,null,transport);}finally{WakfuReleaseUpdater.TestTransportOverride=null;}}
#endif
    static void InstallReleasedPatchCore(string game,string overheadProfile,LatestPatchRelease release,PatchManifest manifest,Action<string> progress,IReleaseHttpTransport transport){
        if(!IsWakfu(game))throw new ReleaseUpdateException("Geçerli Wakfu klasörü seçilmedi.");if(release==null||manifest==null)throw new ReleaseUpdateException("İndirilecek Release bilgisi yok.");EnsureClosed(game);WakfuReleaseUpdater.ValidateReleaseContract(release,manifest);string releaseBaseline=VerifyReleaseBaseline(game,manifest);
        string transaction=Path.Combine(Path.GetTempPath(),"WakfuTurkceRelease_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(transaction);string priorPatchState=ReadStateBytesAsText(InstalledPatchStatePath),priorInstallState=ReadStateBytesAsText(InstallStatePath),backup=null;Dictionary<string,string> live=null;bool filesCommitted=false;
        try{string downloaded=Path.Combine(transaction,manifest.File);if(progress!=null)progress("İndiriliyor...");WakfuReleaseUpdater.DownloadPatch(release,manifest,downloaded);if(progress!=null)progress("Doğrulanıyor...");WakfuReleaseUpdater.VerifyDownloadedPatch(downloaded,manifest);VerifyJar(downloaded,"texts_en.properties");VerifyJar(downloaded,"texts_en_cleaned.properties");live=GameFiles(game);backup=BackupReleaseTargets(live,manifest);if(progress!=null)progress("Kuruluyor...");Install(game,overheadProfile,downloaded,releaseBaseline);filesCommitted=true;if(!String.Equals(HashFile(live["i18n_en"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase)||!String.Equals(HashFile(live["i18n"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase))throw new ReleaseUpdateException("Kurulum sonrası i18n dosyası doğrulanamadı.");WriteReleasedPatchState(game,release,manifest,backup);UpdateLegacyInstallStateI18n(game,manifest.Sha256);}
        catch{if(filesCommitted&&live!=null&&backup!=null)try{RestoreReleaseI18nTargets(live,backup,Path.Combine(transaction,"state-rollback"));}catch{}try{RestoreStateText(InstalledPatchStatePath,priorPatchState);}catch{}try{RestoreStateText(InstallStatePath,priorInstallState);}catch{}throw;}
        finally{try{Directory.Delete(transaction,true);}catch{}}
    }
    static void Install(string game,string overheadProfile){Install(game,overheadProfile,null,null);}
    static void Install(string game,string overheadProfile,string releasedI18n,string releasedSource){
        overheadProfile=NormalizeOverheadProfile(overheadProfile);if(!IsWakfu(game))throw new Exception("Geçerli Wakfu klasörü seçilmedi.");EnsureClosed(game);VerifyEmbeddedPackage();if(String.IsNullOrWhiteSpace(releasedI18n)&&IsFullyCurrentInstallation(game,overheadProfile)){try{WriteOverheadPreference(overheadProfile);}catch{}return;}string transaction=Path.Combine(Path.GetTempPath(),"WakfuTurkceKurulum_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(transaction);
        try{
            var live=GameFiles(game);if(!String.IsNullOrWhiteSpace(releasedI18n)){if(String.IsNullOrWhiteSpace(releasedSource)||!File.Exists(releasedSource))throw new ReleaseUpdateException("Temiz İngilizce dil kaynağı doğrulanamadı.");Directory.CreateDirectory(BackupDir);string cleanBackup=Path.Combine(BackupDir,"i18n_en.jar");if(!File.Exists(cleanBackup)||!String.Equals(HashFile(cleanBackup),HashFile(releasedSource),StringComparison.OrdinalIgnoreCase))File.Copy(releasedSource,cleanBackup,true);string activeBackup=Path.Combine(BackupDir,"i18n.jar");if(!File.Exists(activeBackup))File.Copy(cleanBackup,activeBackup,true);}var official=PrepareOfficialSources(game,Path.Combine(transaction,"official"),!String.IsNullOrWhiteSpace(releasedI18n));string patchedDir=Path.Combine(transaction,"patched");Directory.CreateDirectory(patchedDir);var staged=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
            string prepared;if(String.IsNullOrWhiteSpace(releasedI18n))prepared=BuildAdaptivePatch(official["i18n_en"]);else{VerifyJar(releasedI18n,"texts_en.properties");VerifyJar(releasedI18n,"texts_en_cleaned.properties");prepared=Path.Combine(patchedDir,"release-i18n.jar");File.Copy(releasedI18n,prepared,true);}string patchedEn=Path.Combine(patchedDir,"i18n_en.jar"),patchedActive=Path.Combine(patchedDir,"i18n.jar");File.Move(prepared,patchedEn);File.Copy(patchedEn,patchedActive,true);staged[live["i18n_en"]]=patchedEn;staged[live["i18n"]]=patchedActive;
            string gui=Path.Combine(patchedDir,"gui.jar");File.Copy(official["gui"],gui,true);PatchGuiFonts(gui);VerifyJar(gui,"theme/fonts/asul.ttf");staged[live["gui"]]=gui;
            string client=Path.Combine(patchedDir,"wakfu-client.jar");File.Copy(official["client"],client,true);PatchCharacterChoiceTitle(client);PatchWeatherTimeFormat(client);PatchBattlegroundTimeFormat(client);PatchAchievementTotalLabel(client);PatchPersistentNameOverhead(client,overheadProfile);PatchAlmanaxDescription(client);VerifyJar(client,"dde.class");VerifyPersistentNameOverheadJar(client,overheadProfile);VerifyClientWithGameJava(game,client);staged[live["client"]]=client;
            string data=Path.Combine(patchedDir,"data.jar");File.Copy(official["data"],data,true);EnsureNameToggleShortcut(data);VerifyJar(data,"shortcuts.xml");staged[live["data"]]=data;
            CommitTransaction(staged,transaction);var officialHashes=new Dictionary<string,string>();var patchedHashes=new Dictionary<string,string>();foreach(var pair in official)officialHashes[pair.Key]=HashFile(pair.Value);foreach(var pair in live)patchedHashes[pair.Key]=HashFile(pair.Value);WriteInstallState(game,officialHashes,patchedHashes,overheadProfile);try{WriteOverheadPreference(overheadProfile);}catch{}
        }finally{try{Directory.Delete(transaction,true);}catch{}}
    }
    static void Restore(string game){
        if(!IsWakfu(game))throw new Exception("Geçerli Wakfu klasörü seçilmedi.");EnsureClosed(game);string en=Path.Combine(BackupDir,"i18n_en.jar");if(!File.Exists(en))throw new Exception("Bu bilgisayarda geri yüklenecek temiz resmi yedek bulunamadı.");string transaction=Path.Combine(Path.GetTempPath(),"WakfuTurkceGeriAl_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(transaction);
        try{var live=GameFiles(game);var staged=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);foreach(var pair in live){string backup=Path.Combine(BackupDir,BackupName(pair.Key));if(File.Exists(backup))staged[pair.Value]=backup;}CommitTransaction(staged,transaction);if(File.Exists(InstallStatePath))File.Delete(InstallStatePath);}finally{try{Directory.Delete(transaction,true);}catch{}}
    }

    sealed class SetupForm:Form {
        TextBox path=new TextBox();Label status=new Label();ComboBox overheadSize=new ComboBox();LatestPatchRelease availableRelease;PatchManifest availableManifest;
        string SelectedOverheadProfile(){return overheadSize.SelectedIndex==0?"normal":overheadSize.SelectedIndex==2?"tiny":"small";}
        public SetupForm(){
            Text="Wakfu Türkçe Yama";Size=new Size(790,340);StartPosition=FormStartPosition.CenterScreen;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;Font=new Font("Segoe UI",10);BackColor=Color.FromArgb(38,38,42);ForeColor=Color.WhiteSmoke;
            var label=new Label{Text="Bulunan/seçilen Wakfu klasörü:"};label.SetBounds(20,28,250,25);path.SetBounds(20,56,420,28);path.Text=FindGame();path.BackColor=Color.FromArgb(54,54,60);path.ForeColor=Color.WhiteSmoke;
            var wakfu=new Button{Text="Wakfu Klasörü Seç",BackColor=Color.FromArgb(65,65,72),ForeColor=Color.WhiteSmoke,FlatStyle=System.Windows.Forms.FlatStyle.Flat};wakfu.SetBounds(585,53,170,33);
            var overheadLabel=new Label{Text="Nick Font Boyutu:"};overheadLabel.SetBounds(20,100,165,27);overheadSize.DropDownStyle=ComboBoxStyle.DropDownList;overheadSize.BackColor=Color.FromArgb(54,54,60);overheadSize.ForeColor=Color.WhiteSmoke;overheadSize.Items.AddRange(new object[]{"Normal (28 / 24)","Küçük (24 / 20)","Çok küçük (20 / 16) — Önerilen"});overheadSize.SetBounds(190,96,300,30);string preferred=ReadOverheadPreference();overheadSize.SelectedIndex=preferred=="normal"?0:preferred=="tiny"?2:1;
            var install=new Button{Text="Türkçe Yamayı Yükle",BackColor=Color.FromArgb(35,120,70),ForeColor=Color.White,FlatStyle=(System.Windows.Forms.FlatStyle)1};install.SetBounds(110,143,245,45);var restore=new Button{Text="Türkçe Yamayı Kaldır / Orijinali Yükle",BackColor=Color.FromArgb(120,95,35),ForeColor=Color.White,FlatStyle=(System.Windows.Forms.FlatStyle)1};restore.SetBounds(375,143,300,45);
            status.Text="Güncellemeler kontrol ediliyor...";status.AutoEllipsis=true;status.SetBounds(20,206,735,25);
            var version=new Label{Text="EXE v"+System.Diagnostics.FileVersionInfo.GetVersionInfo(Assembly.GetExecutingAssembly().Location).FileVersion,Font=new Font("Segoe UI",9),ForeColor=Color.FromArgb(170,170,175),TextAlign=ContentAlignment.MiddleLeft};version.SetBounds(20,276,180,25);
            var brand=new Label{Text="Relactive",Font=new Font("Segoe UI",10,FontStyle.Bold|FontStyle.Italic),ForeColor=Color.FromArgb(220,70,70),TextAlign=ContentAlignment.MiddleRight};brand.SetBounds(650,276,105,25);
            wakfu.Click+=(s,e)=>{using(var d=new FolderBrowserDialog{Description="Doğrudan Wakfu oyun klasörünü seçin"})if(d.ShowDialog()==DialogResult.OK){if(IsWakfu(d.SelectedPath))path.Text=d.SelectedPath;else MessageBox.Show("Seçilen klasör geçerli bir Wakfu klasörü değil. İçinde contents\\i18n\\i18n_en.jar bulunmalıdır.","Geçersiz Wakfu klasörü",MessageBoxButtons.OK,MessageBoxIcon.Warning);}};
            overheadSize.SelectedIndexChanged+=(s,e)=>{try{WriteOverheadPreference(SelectedOverheadProfile());}catch{}};
            Shown+=(s,e)=>CheckLatestRelease();
            install.Click+=(s,e)=>InstallAvailableRelease();restore.Click+=(s,e)=>{if(MessageBox.Show("Yalnızca Türkçe yama, font ve arayüz değişiklikleri kaldırılacak; yedekteki resmî oyun dosyaları geri yüklenecek. Devam edilsin mi?","Türkçe yamayı kaldır",MessageBoxButtons.YesNo,MessageBoxIcon.Warning)==DialogResult.Yes)Run(()=>Restore(path.Text),"Türkçe yama kaldırıldı; orijinal oyun dosyaları geri yüklendi.");};
            Controls.AddRange(new Control[]{label,path,wakfu,overheadLabel,overheadSize,install,restore,status,version,brand});
        }
        async void Run(Action action,string ok){try{Enabled=false;UseWaitCursor=true;status.Text="İşlem yapılıyor…";await Task.Run(action);status.Text=ok;MessageBox.Show(ok,"İşlem tamam",MessageBoxButtons.OK,MessageBoxIcon.Information);}catch(Exception ex){MessageBox.Show(ex.Message,"İşlem hatası",MessageBoxButtons.OK,MessageBoxIcon.Error);}finally{UseWaitCursor=false;Enabled=true;}}
        sealed class Candidate { internal LatestPatchRelease Release; internal PatchManifest Manifest; }
        void SetReleaseStatus(string text){if(IsDisposed)return;if(InvokeRequired){BeginInvoke((Action)(()=>SetReleaseStatus(text)));return;}status.Text=text;}
        async void CheckLatestRelease(){
            SetReleaseStatus("Güncellemeler kontrol ediliyor...");
            try{Candidate candidate=await Task.Run(()=>{var release=WakfuReleaseUpdater.GetLatestRelease();return new Candidate{Release=release,Manifest=WakfuReleaseUpdater.GetManifest(release)};});availableRelease=candidate.Release;availableManifest=candidate.Manifest;var installed=ReadInstalledPatchState();string local=StateText(installed,"patch_version");
                if(!String.IsNullOrWhiteSpace(local)&&Regex.IsMatch(local,"^[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}\\.[0-9]+$")&&ComparePatchVersions(local,availableManifest.PatchVersion)>0){SetReleaseStatus("Yerel yama Release sürümünden daha yeni; geri yükleme yapılmayacak.");return;}
                if(IsReleasedPatchInstalled(path.Text,availableManifest)){SetReleaseStatus("Yamanız güncel.");return;}
                SetReleaseStatus("Yeni Türkçe yama bulundu: "+availableManifest.PatchVersion);
            }catch(Exception ex){SetReleaseStatus(WakfuReleaseUpdater.IsOfflineFailure(ex)?"Güncelleme kontrol edilemedi. İnternet bağlantınızı kontrol edin.":"Güncelleme kontrol edilemedi: "+ex.Message);}
        }
        async void InstallAvailableRelease(){
            if(availableRelease==null||availableManifest==null){SetReleaseStatus("Önce güncelleme kontrolünün tamamlanması gerekiyor.");return;}
            try{Enabled=false;UseWaitCursor=true;string profile=SelectedOverheadProfile();await Task.Run(()=>InstallReleasedPatch(path.Text,profile,availableRelease,availableManifest,SetReleaseStatus));SetReleaseStatus("Kurulum tamamlandı.");MessageBox.Show("Kurulum tamamlandı.","İşlem tamam",MessageBoxButtons.OK,MessageBoxIcon.Information);}
            catch(Exception ex){SetReleaseStatus("Kurulum başarısız; mevcut yama korundu.");MessageBox.Show(ex.Message,"İşlem hatası",MessageBoxButtons.OK,MessageBoxIcon.Error);}finally{UseWaitCursor=false;Enabled=true;}
        }
    }
}
