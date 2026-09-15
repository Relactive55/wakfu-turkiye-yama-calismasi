using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
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
[assembly: AssemblyVersion("6.5.17.0")]
[assembly: AssemblyFileVersion("6.5.17.0")]
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

    sealed class TransactionFailureException : Exception {
        internal readonly bool RollbackCompleted;
        internal readonly string TransactionRoot;
        internal TransactionFailureException(string message, Exception inner, bool rollbackCompleted, string transactionRoot) : base(message, inner) {
            RollbackCompleted=rollbackCompleted;TransactionRoot=transactionRoot;
        }
    }

    [STAThread] static void Main(string[] args){
        if(args!=null&&args.Length>0&&String.Equals(args[0],"--replace-self",StringComparison.OrdinalIgnoreCase)){Environment.ExitCode=ReplaceSelf(args);return;}
        if(args!=null&&args.Length>0){try{string game=null,profile=null;for(int i=0;i<args.Length;i++){if(String.Equals(args[i],"--install",StringComparison.OrdinalIgnoreCase)&&i+1<args.Length)game=args[++i];else if(String.Equals(args[i],"--overhead-size",StringComparison.OrdinalIgnoreCase)&&i+1<args.Length)profile=args[++i];else throw new ArgumentException("Kullanım: --install <Wakfu klasörü> --overhead-size <normal|small|tiny>");}if(String.IsNullOrWhiteSpace(game))throw new ArgumentException("Wakfu klasörü belirtilmedi.");Install(game,NormalizeOverheadProfile(profile));}catch(Exception ex){Console.Error.WriteLine(ex.Message);Environment.ExitCode=1;}return;}
        TryInstallerSelfUpdate();
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new SetupForm());
    }
    static void TryInstallerSelfUpdate(){
        try{
            string exe=Assembly.GetExecutingAssembly().Location;if(String.IsNullOrWhiteSpace(exe)||!File.Exists(exe)||Environment.GetEnvironmentVariable("WAKFU_INSTALLER_UPDATE_CHILD")=="1")return;
            ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
            var req=(HttpWebRequest)WebRequest.Create("https://api.github.com/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases?per_page=100");req.UserAgent="WakfuTurkceYamaSetup/1.0";req.Accept="application/vnd.github+json";req.Timeout=5000;
            string json;using(var res=(HttpWebResponse)req.GetResponse())using(var reader=new StreamReader(res.GetResponseStream(),Encoding.UTF8))json=reader.ReadToEnd();
            var list=new JavaScriptSerializer{MaxJsonLength=8*1024*1024}.DeserializeObject(json) as System.Collections.ArrayList;if(list==null)return;Version current=InstallerVersion(System.Diagnostics.FileVersionInfo.GetVersionInfo(exe).FileVersion);Dictionary<string,object> chosen=null;Version best=null;
            foreach(object raw in list){var r=raw as Dictionary<string,object>;if(r==null||Bool(r,"draft")||Bool(r,"prerelease"))continue;string tag=Text(r,"tag_name");Match m=Regex.Match(tag??"","^installer-(\\d+)\\.(\\d+)\\.(\\d+)$");if(!m.Success)continue;Version v=new Version(Int32.Parse(m.Groups[1].Value),Int32.Parse(m.Groups[2].Value),0);if(current!=null&&v<=current)continue;if(best==null||v>best){best=v;chosen=r;}}
            if(chosen==null)return;var assets=chosen["assets"] as System.Collections.ArrayList;if(assets==null)return;Dictionary<string,object> asset=null;foreach(object raw in assets){var a=raw as Dictionary<string,object>;if(a!=null&&Regex.IsMatch(Text(a,"name"),"^Wakfu.*\\.exe$",RegexOptions.IgnoreCase)){asset=a;break;}}if(asset==null)return;long size=Long(asset,"size");string digest=Text(asset,"digest");if(size<=0||size>100*1024*1024||!Regex.IsMatch(digest??"","^sha256:[0-9a-fA-F]{64}$"))return;
            string tagName=Text(chosen,"tag_name"),name=Text(asset,"name");Uri uri=new Uri("https://github.com/Relactive55/wakfu-turkiye-yama-calismasi/releases/download/"+Uri.EscapeDataString(tagName)+"/"+Uri.EscapeDataString(name));if(uri.Scheme!="https"||uri.Host!="github.com")return;string temp=exe+"."+Guid.NewGuid().ToString("N")+".update";var dl=(HttpWebRequest)WebRequest.Create(uri);dl.UserAgent=req.UserAgent;dl.Timeout=30000;using(var res=(HttpWebResponse)dl.GetResponse())using(var input=res.GetResponseStream())using(var output=new FileStream(temp,FileMode.CreateNew))input.CopyTo(output);if(new FileInfo(temp).Length!=size||!String.Equals("sha256:"+LowerHash(temp),digest,StringComparison.OrdinalIgnoreCase)){try{File.Delete(temp);}catch{}return;}
            string backup=exe+".previous";var start=new System.Diagnostics.ProcessStartInfo{FileName=exe,UseShellExecute=false,CreateNoWindow=true,Arguments="--replace-self \\\""+exe.Replace("\\\"","\\\\\\\"")+"\\\" \\\""+temp.Replace("\\\"","\\\\\\\"")+"\\\" \\\""+backup.Replace("\\\"","\\\\\\\"")+"\\\""};System.Diagnostics.Process.Start(start);Environment.Exit(0);
        }catch{}
    }
    static int ReplaceSelf(string[] args){
        if(args.Length!=4)return 2;string target=Path.GetFullPath(args[1]),temp=Path.GetFullPath(args[2]),backup=Path.GetFullPath(args[3]);
        if(!File.Exists(temp)||!String.Equals(Path.GetDirectoryName(target),Path.GetDirectoryName(temp),StringComparison.OrdinalIgnoreCase)||!String.Equals(Path.GetExtension(temp),".update",StringComparison.OrdinalIgnoreCase))return 3;
        for(int i=0;i<20;i++){try{if(File.Exists(backup))File.Delete(backup);if(File.Exists(target))File.Move(target,backup);File.Move(temp,target);System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo{FileName=target,UseShellExecute=true});return 0;}catch{try{if(!File.Exists(target)&&File.Exists(backup))File.Move(backup,target);}catch{}System.Threading.Thread.Sleep(250);}}
        try{if(File.Exists(temp))File.Delete(temp);}catch{}return 4;
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
        var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};string temp=InstallStatePath+"."+Guid.NewGuid().ToString("N")+".tmp";
        try{File.WriteAllText(temp,serializer.Serialize(record),new UTF8Encoding(false));if(File.Exists(InstallStatePath))File.Replace(temp,InstallStatePath,null);else File.Move(temp,InstallStatePath);}
        finally{if(File.Exists(temp))try{File.Delete(temp);}catch{}}
    }
    static string StateText(Dictionary<string,object> state,string name){object value;return state!=null&&state.TryGetValue(name,out value)&&value!=null?Convert.ToString(value):"";}
    static bool SameGameDirectory(string first,string second){try{return String.Equals(Path.GetFullPath(first).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),Path.GetFullPath(second).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar),StringComparison.OrdinalIgnoreCase);}catch{return false;}}
    static int ComparePatchVersions(string left,string right){string[] a=left.Split('.'),b=right.Split('.');for(int i=0;i<4;i++){long x=Int64.Parse(a[i],System.Globalization.CultureInfo.InvariantCulture),y=Int64.Parse(b[i],System.Globalization.CultureInfo.InvariantCulture);if(x!=y)return x<y?-1:1;}return 0;}
    static bool IsSha256(string value){return Regex.IsMatch(value??"","^[A-Fa-f0-9]{64}$",RegexOptions.CultureInvariant);}
    static bool IsGameVersionFormat(string value){return Regex.IsMatch(value??"","^[0-9]+(?:\\.[0-9]+){1,10}(?:_[0-9]+(?:\\.[0-9]+){1,10})?$",RegexOptions.CultureInvariant);}
    static bool FileHashEquals(string path,string expected){try{return File.Exists(path)&&IsSha256(expected)&&String.Equals(HashFile(path),expected,StringComparison.OrdinalIgnoreCase);}catch{return false;}}
    static bool FilesHaveSameHash(string first,string second){try{return File.Exists(first)&&File.Exists(second)&&String.Equals(HashFile(first),HashFile(second),StringComparison.OrdinalIgnoreCase);}catch{return false;}}
    static bool IsInstalledPatchStateValid(string game,Dictionary<string,object> state){
        if(state==null||!SameGameDirectory(StateText(state,"game_dir"),game)||!Regex.IsMatch(StateText(state,"patch_version"),"^[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}\\.[0-9]+$",RegexOptions.CultureInvariant)||!IsSha256(StateText(state,"sha256")))return false;
        var files=GameFiles(game);string hash=StateText(state,"sha256");return FileHashEquals(files["i18n_en"],hash)&&FileHashEquals(files["i18n"],hash);
    }
    static bool IsOriginalI18nStateValid(string game,Dictionary<string,object> state){
        if(state==null||!SameGameDirectory(StateText(state,"game_dir"),game))return false;string expected=StateText(state,"source_i18n_sha256");if(!IsSha256(expected))return false;
        var files=GameFiles(game);return FileHashEquals(files["i18n_en"],expected)&&FileHashEquals(files["i18n"],expected);
    }
    static bool IsLegacyPatchedInstallation(string game){
        var state=ReadInstallState();var files=GameFiles(game);return StateMatchesPatched(state,game,"i18n_en",files["i18n_en"])&&StateMatchesPatched(state,game,"i18n",files["i18n"]);
    }
    static string ReadPropertiesValue(string path,string key){
        try{if(!File.Exists(path))return "";string pattern=@"^\s*"+Regex.Escape(key)+@"\s*=\s*(.*?)\s*$";foreach(string line in File.ReadAllLines(path,Encoding.UTF8)){Match match=Regex.Match(line,pattern,RegexOptions.CultureInvariant);if(match.Success)return match.Groups[1].Value.Trim();}}catch{}return "";
    }
    static string InstalledPatchVersion(string game){
        var state=ReadInstalledPatchState();return IsInstalledPatchStateValid(game,state)?StateText(state,"patch_version"):"";
    }
    static string InstalledGameVersion(string game){
        var patch=ReadInstalledPatchState();
        if(IsInstalledPatchStateValid(game,patch)||IsOriginalI18nStateValid(game,patch)){
            string known=StateText(patch,"game_version");if(IsGameVersionFormat(known))return known;
        }
        string release=ReadPropertiesValue(Path.Combine(game,"sentry.properties"),"release");
        return String.IsNullOrWhiteSpace(release)?"":release;
    }
    static bool OriginalGameFiles(string game){
        var files=GameFiles(game);if(!File.Exists(files["i18n_en"]))return false;
        var patch=ReadInstalledPatchState();if(IsInstalledPatchStateValid(game,patch))return false;
        if(IsOriginalI18nStateValid(game,patch))return true;
        var legacy=ReadInstallState();object raw;var official=legacy!=null&&legacy.TryGetValue("official",out raw)?StringDictionary(raw):null;
        string expected;bool matchesOfficial=official!=null&&official.TryGetValue("i18n_en",out expected)&&FileHashEquals(files["i18n_en"],expected);
        if(matchesOfficial){if(!File.Exists(files["i18n"]))return true;return official.TryGetValue("i18n",out expected)&&FileHashEquals(files["i18n"],expected);}
        string backup=Path.Combine(BackupDir,"i18n_en.jar");if(FilesHaveSameHash(files["i18n_en"],backup)){if(!File.Exists(files["i18n"]))return true;return FilesHaveSameHash(files["i18n"],backup);}
        return false;
    }
    static bool IsReleasedPatchInstalled(string game,PatchManifest manifest){
        var state=ReadInstalledPatchState();if(state==null||!SameGameDirectory(StateText(state,"game_dir"),game)||!String.Equals(StateText(state,"patch_version"),manifest.PatchVersion,StringComparison.Ordinal)||!String.Equals(StateText(state,"sha256"),manifest.Sha256,StringComparison.OrdinalIgnoreCase))return false;
        var files=GameFiles(game);return File.Exists(files["i18n_en"])&&File.Exists(files["i18n"])&&String.Equals(HashFile(files["i18n_en"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase)&&String.Equals(HashFile(files["i18n"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase);
    }
    static void UpdateLegacyInstallStateI18n(string game,string hash){
        var state=ReadInstallState();if(state==null||!SameGameDirectory(StateText(state,"gameDir"),game))return;object raw;var patched=state.TryGetValue("patched",out raw)?raw as Dictionary<string,object>:null;if(patched==null)return;
        patched["i18n_en"]=hash;patched["i18n"]=hash;Directory.CreateDirectory(StateRoot);var serializer=new JavaScriptSerializer{MaxJsonLength=Int32.MaxValue};string temp=InstallStatePath+"."+Guid.NewGuid().ToString("N")+".tmp";
        try{File.WriteAllText(temp,serializer.Serialize(state),new UTF8Encoding(false));if(File.Exists(InstallStatePath))File.Replace(temp,InstallStatePath,null);else File.Move(temp,InstallStatePath);}
        finally{if(File.Exists(temp))try{File.Delete(temp);}catch{}}
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
    static bool IsProcessForGame(System.Diagnostics.Process process,string game,string processName){
        if(!String.Equals(processName,"java",StringComparison.OrdinalIgnoreCase)&&!String.Equals(processName,"javaw",StringComparison.OrdinalIgnoreCase))return true;
        try{
            string executable=process.MainModule==null?"":process.MainModule.FileName;
            if(String.IsNullOrWhiteSpace(executable))return false;
            string expected=Path.Combine(game,"jre","bin",processName+".exe");
            return String.Equals(Path.GetFullPath(executable),Path.GetFullPath(expected),StringComparison.OrdinalIgnoreCase);
        }catch{return false;}
    }
    static bool IsRelevantProcessRunning(string name,string game){
        foreach(System.Diagnostics.Process process in System.Diagnostics.Process.GetProcessesByName(name)){
            try{if(IsProcessForGame(process,game,name))return true;}
            catch{if(!String.Equals(name,"java",StringComparison.OrdinalIgnoreCase)&&!String.Equals(name,"javaw",StringComparison.OrdinalIgnoreCase))return true;}
            finally{process.Dispose();}
        }
        return false;
    }
    static void EnsureClosed(string game){
        if(IsIsolatedDistributionTest(game))return;
        foreach(var n in new[]{"Wakfu","java","javaw","Ankama Launcher","zaap"})
            if(IsRelevantProcessRunning(n,game))
                throw new Exception("Kurulumdan önce Wakfu ve Ankama Launcher tamamen kapatılmalıdır. Engelleyen süreç: "+n);
    }
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
    static List<string> RollbackTargets(List<string> committed,Dictionary<string,string> backups,bool atomic){
        var failures=new List<string>();
        for(int i=committed.Count-1;i>=0;i--){
            string target=committed[i];
            try{
                string old;
                if(backups.TryGetValue(target,out old)){
                    if(atomic)ReplaceFileAtomically(old,target);else CopyFileWithRetry(old,target);
                    if(!File.Exists(target)||!String.Equals(HashFile(old),HashFile(target),StringComparison.OrdinalIgnoreCase))throw new IOException("geri yüklenen dosya doğrulanamadı");
                }else{
                    if(File.Exists(target))File.Delete(target);
                    if(File.Exists(target))throw new IOException("yeni dosya silinemedi");
                }
            }catch(Exception ex){failures.Add(Path.GetFileName(target)+": "+ex.Message);}
        }
        return failures;
    }
    static string RollbackDetail(List<string> failures){return failures.Count==0?"":Environment.NewLine+"Geri alınamayan dosyalar: "+String.Join(", ",failures.ToArray());}
    static void CommitTransaction(Dictionary<string,string> stagedByTarget,string transactionRoot){CommitTransaction(stagedByTarget,transactionRoot,null);}
    static void CommitTransaction(Dictionary<string,string> stagedByTarget,string transactionRoot,Action afterCommit){
        string rollback=Path.Combine(transactionRoot,"rollback");Directory.CreateDirectory(rollback);var backups=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);var committed=new List<string>();
        try{
            int index=0;
            foreach(var pair in stagedByTarget){
                Directory.CreateDirectory(Path.GetDirectoryName(pair.Key));
                string old=Path.Combine(rollback,(index++).ToString("D2")+"_"+Path.GetFileName(pair.Key));
                if(File.Exists(pair.Key)){File.Copy(pair.Key,old,true);backups[pair.Key]=old;}
                committed.Add(pair.Key);
                CopyFileWithRetry(pair.Value,pair.Key);
                if(!String.Equals(HashFile(pair.Value),HashFile(pair.Key),StringComparison.OrdinalIgnoreCase))throw new Exception("Kurulum sonrası dosya özeti eşleşmedi: "+Path.GetFileName(pair.Key));
            }
            if(afterCommit!=null)afterCommit();
        }catch(Exception ex){
            List<string> failures=RollbackTargets(committed,backups,false);
            bool complete=failures.Count==0;
            string message=complete
                ? "Kurulum tamamlanamadı; değiştirilen dosyalar geri alındı."
                : "Kurulum tamamlanamadı; geri alma tamamlanamadı. İşlem klasörü korunuyor: "+transactionRoot;
            throw new TransactionFailureException(message+RollbackDetail(failures)+Environment.NewLine+"Ayrıntı: "+ex.Message,ex,complete,transactionRoot);
        }
    }
    // Release rollback uses the same transaction engine as the full installer;
    // this keeps the test seam and production path on one failure-safe code
    // path while still limiting the release operation to its two i18n files.
    static void CommitReleaseI18nTransaction(Dictionary<string,string> stagedByTarget,string transactionRoot){
        try{CommitTransaction(stagedByTarget,transactionRoot);}
        catch(TransactionFailureException ex){throw new ReleaseUpdateException(ex.Message,ex);}
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
        string transaction=Path.Combine(Path.GetTempPath(),"WakfuTurkceRelease_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(transaction);string priorPatchState=ReadStateBytesAsText(InstalledPatchStatePath),priorInstallState=ReadStateBytesAsText(InstallStatePath),backup=null;Dictionary<string,string> live=null;bool preserveTransaction=false;
        try{
            string downloaded=Path.Combine(transaction,manifest.File);
            if(progress!=null)progress("İndiriliyor...");
            WakfuReleaseUpdater.DownloadPatch(release,manifest,downloaded);
            if(progress!=null)progress("Doğrulanıyor...");
            WakfuReleaseUpdater.VerifyDownloadedPatch(downloaded,manifest);VerifyJar(downloaded,"texts_en.properties");VerifyJar(downloaded,"texts_en_cleaned.properties");
            live=GameFiles(game);backup=BackupReleaseTargets(live,manifest);
            if(progress!=null)progress("Kuruluyor...");
            Install(game,overheadProfile,downloaded,releaseBaseline,delegate{
                if(!String.Equals(HashFile(live["i18n_en"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase)||!String.Equals(HashFile(live["i18n"]),manifest.Sha256,StringComparison.OrdinalIgnoreCase))throw new ReleaseUpdateException("Kurulum sonrası i18n dosyası doğrulanamadı.");
                WriteReleasedPatchState(game,release,manifest,backup);UpdateLegacyInstallStateI18n(game,manifest.Sha256);
            });
        }catch(TransactionFailureException ex){
            preserveTransaction=!ex.RollbackCompleted;
            var stateFailures=new List<string>();
            try{RestoreStateText(InstalledPatchStatePath,priorPatchState);}catch(Exception stateError){stateFailures.Add("installed_patch.json: "+stateError.Message);}
            try{RestoreStateText(InstallStatePath,priorInstallState);}catch(Exception stateError){stateFailures.Add("kurulum_durumu.json: "+stateError.Message);}
            if(stateFailures.Count>0)throw new ReleaseUpdateException(ex.Message+Environment.NewLine+"Durum geri alınamadı: "+String.Join(", ",stateFailures.ToArray()),ex);
            throw;
        }catch(Exception ex){
            var stateFailures=new List<string>();
            try{RestoreStateText(InstalledPatchStatePath,priorPatchState);}catch(Exception stateError){stateFailures.Add("installed_patch.json: "+stateError.Message);}
            try{RestoreStateText(InstallStatePath,priorInstallState);}catch(Exception stateError){stateFailures.Add("kurulum_durumu.json: "+stateError.Message);}
            if(stateFailures.Count>0)throw new ReleaseUpdateException("Release kurulumu başarısız oldu; durum geri alınamadı: "+String.Join(", ",stateFailures.ToArray()),ex);
            throw;
        }finally{if(!preserveTransaction)try{Directory.Delete(transaction,true);}catch{}}
    }
    static void Install(string game,string overheadProfile){Install(game,overheadProfile,null,null,null);}
    static void Install(string game,string overheadProfile,string releasedI18n,string releasedSource){Install(game,overheadProfile,releasedI18n, releasedSource, null);}
    static void Install(string game,string overheadProfile,string releasedI18n,string releasedSource,Action afterCommit){
        overheadProfile=NormalizeOverheadProfile(overheadProfile);if(!IsWakfu(game))throw new Exception("Geçerli Wakfu klasörü seçilmedi.");EnsureClosed(game);
#if !WAKFU_TESTS
        VerifyEmbeddedPackage();
#endif
#if WAKFU_TESTS
        // The isolated updater harness contains only the two i18n targets.
        // Exercise the same verified release transaction without requiring
        // the full five-file game installation or embedded production assets.
        if(IsIsolatedDistributionTest(game)&&!String.IsNullOrWhiteSpace(releasedI18n)){
            var releaseLive=GameFiles(game);var releaseStaged=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase){{releaseLive["i18n_en"],releasedI18n},{releaseLive["i18n"],releasedI18n}};
            string releaseTransaction=Path.Combine(Path.GetTempPath(),"WakfuReleaseTest_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(releaseTransaction);bool preserveReleaseTransaction=false;
            try{CommitTransaction(releaseStaged,releaseTransaction,afterCommit);}
            catch(TransactionFailureException ex){preserveReleaseTransaction=!ex.RollbackCompleted;throw;}
            finally{if(!preserveReleaseTransaction)try{Directory.Delete(releaseTransaction,true);}catch{}}
            return;
        }
#endif
        if(String.IsNullOrWhiteSpace(releasedI18n)&&IsFullyCurrentInstallation(game,overheadProfile)){try{WriteOverheadPreference(overheadProfile);}catch{}return;}string transaction=Path.Combine(Path.GetTempPath(),"WakfuTurkceKurulum_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(transaction);bool preserveTransaction=false;
        try{
            var live=GameFiles(game);if(!String.IsNullOrWhiteSpace(releasedI18n)){if(String.IsNullOrWhiteSpace(releasedSource)||!File.Exists(releasedSource))throw new ReleaseUpdateException("Temiz İngilizce dil kaynağı doğrulanamadı.");Directory.CreateDirectory(BackupDir);string cleanBackup=Path.Combine(BackupDir,"i18n_en.jar");if(!File.Exists(cleanBackup)||!String.Equals(HashFile(cleanBackup),HashFile(releasedSource),StringComparison.OrdinalIgnoreCase))File.Copy(releasedSource,cleanBackup,true);string activeBackup=Path.Combine(BackupDir,"i18n.jar");if(!File.Exists(activeBackup))File.Copy(cleanBackup,activeBackup,true);}var official=PrepareOfficialSources(game,Path.Combine(transaction,"official"),!String.IsNullOrWhiteSpace(releasedI18n));string patchedDir=Path.Combine(transaction,"patched");Directory.CreateDirectory(patchedDir);var staged=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
            string prepared;if(String.IsNullOrWhiteSpace(releasedI18n))prepared=BuildAdaptivePatch(official["i18n_en"]);else{VerifyJar(releasedI18n,"texts_en.properties");VerifyJar(releasedI18n,"texts_en_cleaned.properties");prepared=Path.Combine(patchedDir,"release-i18n.jar");File.Copy(releasedI18n,prepared,true);}string patchedEn=Path.Combine(patchedDir,"i18n_en.jar"),patchedActive=Path.Combine(patchedDir,"i18n.jar");File.Move(prepared,patchedEn);File.Copy(patchedEn,patchedActive,true);staged[live["i18n_en"]]=patchedEn;staged[live["i18n"]]=patchedActive;
            string gui=Path.Combine(patchedDir,"gui.jar");File.Copy(official["gui"],gui,true);PatchGuiFonts(gui);VerifyJar(gui,"theme/fonts/asul.ttf");staged[live["gui"]]=gui;
            string client=Path.Combine(patchedDir,"wakfu-client.jar");File.Copy(official["client"],client,true);PatchCharacterChoiceTitle(client);PatchWeatherTimeFormat(client);PatchBattlegroundTimeFormat(client);PatchAchievementTotalLabel(client);PatchPersistentNameOverhead(client,overheadProfile);PatchAlmanaxDescription(client);VerifyJar(client,"dde.class");VerifyPersistentNameOverheadJar(client,overheadProfile);VerifyClientWithGameJava(game,client);staged[live["client"]]=client;
            string data=Path.Combine(patchedDir,"data.jar");File.Copy(official["data"],data,true);EnsureNameToggleShortcut(data);VerifyJar(data,"shortcuts.xml");staged[live["data"]]=data;
            var officialHashes=new Dictionary<string,string>();var patchedHashes=new Dictionary<string,string>();foreach(var pair in official)officialHashes[pair.Key]=HashFile(pair.Value);foreach(var pair in live){string stagedPath; if(!staged.TryGetValue(pair.Value,out stagedPath))throw new Exception("Kurulum hedefi hazırlanamadı: "+Path.GetFileName(pair.Value));patchedHashes[pair.Key]=HashFile(stagedPath);}
            CommitTransaction(staged,transaction,delegate{WriteInstallState(game,officialHashes,patchedHashes,overheadProfile);if(afterCommit!=null)afterCommit();});try{WriteOverheadPreference(overheadProfile);}catch{}
        }catch(TransactionFailureException ex){preserveTransaction=!ex.RollbackCompleted;throw;
        }finally{if(!preserveTransaction)try{Directory.Delete(transaction,true);}catch{}}
    }
    static void Restore(string game){
        if(!IsWakfu(game))throw new Exception("Geçerli Wakfu klasörü seçilmedi.");EnsureClosed(game);string en=Path.Combine(BackupDir,"i18n_en.jar");if(!File.Exists(en))throw new Exception("Bu bilgisayarda geri yüklenecek temiz resmi yedek bulunamadı.");string transaction=Path.Combine(Path.GetTempPath(),"WakfuTurkceGeriAl_"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(transaction);
        bool preserveTransaction=false;
        try{var live=GameFiles(game);var staged=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);foreach(var pair in live){string backup=Path.Combine(BackupDir,BackupName(pair.Key));if(File.Exists(backup))staged[pair.Value]=backup;}CommitTransaction(staged,transaction);if(File.Exists(InstallStatePath))File.Delete(InstallStatePath);if(File.Exists(InstalledPatchStatePath))File.Delete(InstalledPatchStatePath);}
        catch(TransactionFailureException ex){preserveTransaction=!ex.RollbackCompleted;throw;}
        finally{if(!preserveTransaction)try{Directory.Delete(transaction,true);}catch{}}
    }

    sealed class TopAlignedImageBox:Control {
        internal Image Image;
        internal TopAlignedImageBox(){SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer|ControlStyles.ResizeRedraw|ControlStyles.Opaque,true);}
        protected override void OnPaintBackground(PaintEventArgs e){e.Graphics.Clear(BackColor);}
        protected override void OnPaint(PaintEventArgs e){
            if(Image==null||Width<=0||Height<=0)return;e.Graphics.CompositingQuality=CompositingQuality.HighQuality;e.Graphics.InterpolationMode=InterpolationMode.HighQualityBicubic;e.Graphics.PixelOffsetMode=PixelOffsetMode.HighQuality;e.Graphics.SmoothingMode=SmoothingMode.HighQuality;
            double scale=Math.Min((double)Width/Image.Width,(double)Height/Image.Height);int drawWidth=Math.Max(1,(int)Math.Round(Image.Width*scale));int drawHeight=Math.Max(1,(int)Math.Round(Image.Height*scale));int x=(Width-drawWidth)/2;e.Graphics.DrawImage(Image,new Rectangle(x,0,drawWidth,drawHeight),0,0,Image.Width,Image.Height,GraphicsUnit.Pixel);
        }
        protected override void Dispose(bool disposing){if(disposing&&Image!=null){Image.Dispose();Image=null;}base.Dispose(disposing);}
    }
    sealed class RoundedSurface:Panel {
        internal Color SurfaceColor=Color.FromArgb(14,23,32);
        internal Color BorderColor=Color.FromArgb(218,166,104);
        internal int CornerRadius=22;
        internal RoundedSurface(){SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer|ControlStyles.ResizeRedraw,true);BackColor=SurfaceColor;}
        protected override void OnResize(EventArgs e){base.OnResize(e);using(var path=RoundedPath(new Rectangle(0,0,Math.Max(1,Width-1),Math.Max(1,Height-1)),CornerRadius))Region=new Region(path);}
        protected override void OnPaintBackground(PaintEventArgs e){e.Graphics.Clear(SurfaceColor);}
        protected override void OnPaint(PaintEventArgs e){e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;using(var path=RoundedPath(new Rectangle(0,0,Math.Max(1,Width-1),Math.Max(1,Height-1)),CornerRadius))using(var pen=new Pen(BorderColor,1.5f))e.Graphics.DrawPath(pen,path);}
    }
    sealed class RoundedActionButton:Button {
        internal Color HoverColor;
        bool hovered;
        internal RoundedActionButton(){FlatStyle=FlatStyle.Flat;FlatAppearance.BorderSize=0;UseVisualStyleBackColor=false;Cursor=Cursors.Hand;SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer|ControlStyles.ResizeRedraw|ControlStyles.Opaque,true);}
        protected override void OnResize(EventArgs e){base.OnResize(e);using(var path=RoundedPath(new Rectangle(0,0,Math.Max(1,Width-1),Math.Max(1,Height-1)),12))Region=new Region(path);}
        protected override void OnMouseEnter(EventArgs e){hovered=true;Invalidate();base.OnMouseEnter(e);}
        protected override void OnMouseLeave(EventArgs e){hovered=false;Invalidate();base.OnMouseLeave(e);}
        protected override void OnEnabledChanged(EventArgs e){if(!Enabled)hovered=false;base.OnEnabledChanged(e);Invalidate();}
        protected override void OnTextChanged(EventArgs e){base.OnTextChanged(e);Invalidate();}
        Color PaintColor(){Color active=hovered&&Enabled&&HoverColor!=Color.Empty?HoverColor:BackColor;if(Enabled)return Color.FromArgb(255,active.R,active.G,active.B);Color parent=Parent==null?Color.FromArgb(14,23,32):Parent.BackColor;return Color.FromArgb(255,(active.R+parent.R*2)/3,(active.G+parent.G*2)/3,(active.B+parent.B*2)/3);}
        protected override void OnPaintBackground(PaintEventArgs e){e.Graphics.Clear(PaintColor());}
        protected override void OnPaint(PaintEventArgs e){e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;e.Graphics.PixelOffsetMode=PixelOffsetMode.HighQuality;Color color=PaintColor();using(var path=RoundedPath(new Rectangle(0,0,Math.Max(1,Width-1),Math.Max(1,Height-1)),12))using(var fill=new SolidBrush(color))e.Graphics.FillPath(fill,path);Color textColor=Enabled?ForeColor:Color.FromArgb(188,198,207);TextRenderer.DrawText(e.Graphics,Text,Font,ClientRectangle,textColor,TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis|TextFormatFlags.NoPadding);}
    }
    static GraphicsPath RoundedPath(Rectangle bounds,int radius){var path=new GraphicsPath();int diameter=Math.Max(2,Math.Min(radius*2,Math.Min(bounds.Width,bounds.Height)));int r=diameter-1;path.AddArc(bounds.X,bounds.Y,r,r,180,90);path.AddArc(bounds.Right-r,bounds.Y,r,r,270,90);path.AddArc(bounds.Right-r,bounds.Bottom-r,r,r,0,90);path.AddArc(bounds.X,bounds.Bottom-r,r,r,90,90);path.CloseFigure();return path;}

    sealed class SetupForm:Form {
        TextBox path=new TextBox();Label status=new Label();Label gameVersionStatus=new Label();Label patchStatus=new Label();ComboBox overheadSize=new ComboBox();LatestPatchRelease availableRelease;PatchManifest availableManifest;
        string SelectedOverheadProfile(){return overheadSize.SelectedIndex==0?"normal":overheadSize.SelectedIndex==2?"tiny":"small";}
        static Image LoadImageResource(string name){
            try{using(Stream source=Resource(name))using(var buffer=new MemoryStream()){source.CopyTo(buffer);buffer.Position=0;using(var loaded=Image.FromStream(buffer))return new Bitmap(loaded);}
            }catch{return null;}
        }
        public SetupForm(){
            Text="Wakfu Türkçe Yama - Relactive";ClientSize=new Size(720,520);MinimumSize=Size;StartPosition=FormStartPosition.CenterScreen;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;Font=new Font("Segoe UI",10);BackColor=Color.FromArgb(8,16,24);ForeColor=Color.WhiteSmoke;
            try{using(Stream source=Resource("program.ico"))using(var buffer=new MemoryStream()){source.CopyTo(buffer);buffer.Position=0;Icon=new Icon(buffer);}}catch{}
            var background=new TopAlignedImageBox{Dock=DockStyle.Fill,BackColor=Color.FromArgb(8,16,24),Image=LoadImageResource("program_background.png")};
            Color panelColor=Color.FromArgb(14,23,32);var surface=new RoundedSurface{CornerRadius=12,SurfaceColor=panelColor,BackColor=panelColor};
            var label=new Label{Text="Wakfu Oyun Klasörü",BackColor=panelColor,ForeColor=Color.WhiteSmoke,Font=new Font("Segoe UI",10,FontStyle.Regular),TextAlign=ContentAlignment.MiddleLeft};
            path.Text=FindGame();path.BackColor=Color.FromArgb(35,44,56);path.ForeColor=Color.WhiteSmoke;path.BorderStyle=BorderStyle.FixedSingle;path.Font=new Font("Segoe UI",10);path.Margin=Padding.Empty;
            var wakfu=new RoundedActionButton{Text="Gözat...",BackColor=Color.FromArgb(45,53,65),HoverColor=Color.FromArgb(62,72,86),ForeColor=Color.WhiteSmoke,Font=new Font("Segoe UI",10)};
            var overheadLabel=new Label{Text="Nick Font Boyutu:",ForeColor=Color.Gainsboro,Visible=false};overheadSize.DropDownStyle=ComboBoxStyle.DropDownList;overheadSize.BackColor=Color.FromArgb(48,52,60);overheadSize.ForeColor=Color.WhiteSmoke;overheadSize.Items.AddRange(new object[]{"Normal (28 / 24)","Küçük (24 / 20)","Çok küçük (20 / 16) — Önerilen"});overheadSize.Visible=false;string preferred=ReadOverheadPreference();overheadSize.SelectedIndex=preferred=="normal"?0:preferred=="tiny"?2:1;
            var install=new RoundedActionButton{Text="YAMA KUR",BackColor=Color.FromArgb(27,143,119),HoverColor=Color.FromArgb(34,169,140),ForeColor=Color.White,Font=new Font("Segoe UI",13,FontStyle.Bold)};
            var restore=new RoundedActionButton{Text="GERİ AL",BackColor=Color.FromArgb(25,141,119),HoverColor=Color.FromArgb(34,169,140),ForeColor=Color.White,Font=new Font("Segoe UI",13,FontStyle.Bold)};
            var support=new RoundedActionButton{Text="DESTEK / BAĞIŞ",BackColor=Color.FromArgb(20,117,221),HoverColor=Color.FromArgb(41,141,239),ForeColor=Color.White,Font=new Font("Segoe UI",11,FontStyle.Regular)};support.Cursor=Cursors.Hand;
            var supportTip=new ToolTip();supportTip.SetToolTip(support,"Shopier destek sayfasını aç");support.MouseEnter+=(s,e)=>{support.Text="Teşekkürler";};support.MouseLeave+=(s,e)=>{support.Text="DESTEK / BAĞIŞ";};support.EnabledChanged+=(s,e)=>{if(!support.Enabled)support.Text="DESTEK / BAĞIŞ";};support.Click+=(s,e)=>{try{System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("https://www.shopier.com/poe2tr/50856020"){UseShellExecute=true});}catch(Exception ex){MessageBox.Show(this,"Destek sayfası açılamadı: "+ex.Message,"Bağlantı hatası",MessageBoxButtons.OK,MessageBoxIcon.Warning);}};
            status.Text="Hazır — Güncellemeler kontrol ediliyor...";status.AutoEllipsis=true;status.BackColor=panelColor;status.ForeColor=Color.White;status.Font=new Font("Segoe UI",9);status.TextAlign=ContentAlignment.MiddleCenter;
            gameVersionStatus.AutoEllipsis=true;gameVersionStatus.BackColor=panelColor;gameVersionStatus.ForeColor=Color.WhiteSmoke;gameVersionStatus.Font=new Font("Segoe UI",11);gameVersionStatus.TextAlign=ContentAlignment.MiddleLeft;
            patchStatus.Visible=false;
            var brand=new Label{Text="Yapım Relactive",BackColor=panelColor,Font=new Font("Segoe UI",10,FontStyle.Bold|FontStyle.Italic),ForeColor=Color.FromArgb(220,150,88),TextAlign=ContentAlignment.MiddleRight};

            Action layoutSurface=null;layoutSurface=()=>{
                int w=surface.ClientSize.Width,h=surface.ClientSize.Height,pad=20;int browseWidth=80;int rowY=12,rowH=28;
                label.SetBounds(pad,rowY,130,rowH);path.SetBounds(pad+130,rowY,Math.Max(120,w-pad*2-130-browseWidth-10),rowH);wakfu.SetBounds(w-pad-browseWidth,rowY,browseWidth,rowH);
                int gap=12;int buttonY=53;int installWidth=150;int restoreWidth=150;int supportWidth=120;int groupWidth=installWidth+restoreWidth+supportWidth+gap*2;int groupX=Math.Max(pad,(w-groupWidth)/2);install.SetBounds(groupX,buttonY,installWidth,39);restore.SetBounds(groupX+installWidth+gap,buttonY,restoreWidth,39);support.SetBounds(groupX+installWidth+gap+restoreWidth+gap,buttonY,supportWidth,39);
                int bottomY=118;gameVersionStatus.SetBounds(pad,bottomY,170,22);status.SetBounds(200,bottomY,340,22);brand.SetBounds(545,bottomY,127,22);patchStatus.SetBounds(0,0,1,1);
                overheadLabel.SetBounds(0,0,1,1);overheadSize.SetBounds(0,0,1,1);surface.Invalidate();
            };
            Action layoutForm=()=>{int margin=14;int panelHeight=160;int bottom=16;surface.SetBounds(margin,Math.Max(20,ClientSize.Height-panelHeight-bottom),Math.Max(400,ClientSize.Width-margin*2),panelHeight);layoutSurface();};
            Resize+=(s,e)=>layoutForm();
            RefreshLocalStatus();
            wakfu.Click+=(s,e)=>{using(var d=new FolderBrowserDialog{Description="Doğrudan Wakfu oyun klasörünü seçin"})if(d.ShowDialog(this)==DialogResult.OK){if(IsWakfu(d.SelectedPath)){path.Text=d.SelectedPath;RefreshLocalStatus();}else MessageBox.Show(this,"Seçilen klasör geçerli bir Wakfu klasörü değil. İçinde contents\\i18n\\i18n_en.jar bulunmalıdır.","Geçersiz Wakfu klasörü",MessageBoxButtons.OK,MessageBoxIcon.Warning);}};
            overheadSize.SelectedIndexChanged+=(s,e)=>{try{WriteOverheadPreference(SelectedOverheadProfile());}catch{}};
            Shown+=(s,e)=>CheckLatestRelease();
            install.Click+=(s,e)=>InstallAvailableRelease();restore.Click+=(s,e)=>{if(MessageBox.Show(this,"Yalnızca Türkçe yama, font ve arayüz değişiklikleri kaldırılacak; yedekteki resmî oyun dosyaları geri yüklenecek. Devam edilsin mi?","Türkçe yamayı kaldır",MessageBoxButtons.YesNo,MessageBoxIcon.Warning)==DialogResult.Yes)Run(()=>Restore(path.Text),"Türkçe yama kaldırıldı; orijinal oyun dosyaları geri yüklendi.");};
            surface.Controls.AddRange(new Control[]{label,path,wakfu,overheadLabel,overheadSize,install,restore,support,status,gameVersionStatus,brand});
            Controls.Add(background);Controls.Add(surface);background.SendToBack();surface.BringToFront();layoutForm();
        }
        void RefreshLocalStatus(){
            try{
                string game=path.Text.Trim();if(!IsWakfu(game)){gameVersionStatus.Text="Sürüm —";patchStatus.Text="Yama durumu: geçerli bir Wakfu klasörü seçilmedi.";return;}
                string gameVersion=InstalledGameVersion(game);gameVersionStatus.Text="Sürüm "+(String.IsNullOrWhiteSpace(gameVersion)?"—":gameVersion);
                string patch=InstalledPatchVersion(game);if(!String.IsNullOrWhiteSpace(patch))patchStatus.Text="Türkçe yama yüklü: "+patch;else if(IsLegacyPatchedInstallation(game))patchStatus.Text="Türkçe yama yüklü: sürüm bilgisi eski kurulum kaydında yok.";else if(OriginalGameFiles(game))patchStatus.Text="Oyun dosyaları orijinal.";else patchStatus.Text="Yama durumu: tespit edilemedi.";
            }catch{gameVersionStatus.Text="Sürüm okunamadı";patchStatus.Text="Yama durumu: okunamadı.";}
        }
        void SetBusy(bool busy){UseWaitCursor=busy;Enabled=!busy;if(!busy){Invalidate(true);Update();}}
        async void Run(Action action,string ok){Exception failure=null;try{SetBusy(true);status.Text="İşlem yapılıyor…";await Task.Run(action);RefreshLocalStatus();status.Text=ok;}catch(Exception ex){failure=ex;status.Text=InstallFailureStatus(ex);}finally{SetBusy(false);}if(failure==null)MessageBox.Show(this,ok,"İşlem tamam",MessageBoxButtons.OK,MessageBoxIcon.Information);else MessageBox.Show(this,failure.Message,"İşlem hatası",MessageBoxButtons.OK,MessageBoxIcon.Error);}
        sealed class Candidate { internal LatestPatchRelease Release; internal PatchManifest Manifest; }
        void SetReleaseStatus(string text){if(IsDisposed)return;if(InvokeRequired){BeginInvoke((Action)(()=>SetReleaseStatus(text)));return;}status.Text=text;}
        static TransactionFailureException FindTransactionFailure(Exception error){for(Exception current=error;current!=null;current=current.InnerException){var transaction=current as TransactionFailureException;if(transaction!=null)return transaction;}return null;}
        static string InstallFailureStatus(Exception error){var transaction=FindTransactionFailure(error);if(transaction==null)return "Kurulum başarısız; oyun dosyaları değiştirilmedi.";if(transaction.RollbackCompleted)return "Kurulum başarısız; yapılan dosya değişiklikleri geri alındı.";return "Kurulum başarısız; geri alma tamamlanamadı. Kurtarma klasörü: "+transaction.TransactionRoot;}
        async void CheckLatestRelease(){
            SetReleaseStatus("Güncellemeler kontrol ediliyor...");
            try{Candidate candidate=await Task.Run(()=>{var release=WakfuReleaseUpdater.GetLatestRelease();return new Candidate{Release=release,Manifest=WakfuReleaseUpdater.GetManifest(release)};});availableRelease=candidate.Release;availableManifest=candidate.Manifest;RefreshLocalStatus();string local=InstalledPatchVersion(path.Text);
                if(!String.IsNullOrWhiteSpace(local)&&Regex.IsMatch(local,"^[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}\\.[0-9]+$")&&ComparePatchVersions(local,availableManifest.PatchVersion)>0){SetReleaseStatus("Mevcut güncelleme: yerel yama daha yeni ("+local+").");return;}
                if(IsReleasedPatchInstalled(path.Text,availableManifest)){SetReleaseStatus("Mevcut güncelleme: yamanız güncel ("+availableManifest.PatchVersion+").");return;}
                SetReleaseStatus("Mevcut güncelleme: yeni Türkçe yama bulundu — "+availableManifest.PatchVersion);
            }catch(Exception ex){SetReleaseStatus(WakfuReleaseUpdater.IsOfflineFailure(ex)?"Güncelleme kontrol edilemedi. İnternet bağlantınızı kontrol edin.":"Güncelleme kontrol edilemedi: "+ex.Message);}
        }
        async void InstallAvailableRelease(){
            if(availableRelease==null||availableManifest==null){SetReleaseStatus("Önce güncelleme kontrolünün tamamlanması gerekiyor.");return;}
            Exception failure=null;try{SetBusy(true);string profile=SelectedOverheadProfile();await Task.Run(()=>InstallReleasedPatch(path.Text,profile,availableRelease,availableManifest,SetReleaseStatus));RefreshLocalStatus();SetReleaseStatus("Kurulum tamamlandı: Türkçe yama "+availableManifest.PatchVersion+".");}
            catch(Exception ex){failure=ex;SetReleaseStatus(InstallFailureStatus(ex));}finally{SetBusy(false);}if(failure==null)MessageBox.Show(this,"Kurulum tamamlandı.","İşlem tamam",MessageBoxButtons.OK,MessageBoxIcon.Information);else MessageBox.Show(this,failure.Message,"İşlem hatası",MessageBoxButtons.OK,MessageBoxIcon.Error);
        }
    }
}
