using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

// Shared only by the Setup EXE build.  The translation-editor EXE must not
// compile or contain this network/update code.
internal sealed class ReleaseAsset {
    internal long Id;
    internal string Name;
    internal long Size;
}

internal sealed class LatestPatchRelease {
    internal long Id;
    internal string Tag;
    internal Dictionary<string, ReleaseAsset> Assets;
}

internal sealed class PatchManifest {
    internal string GameVersion;
    internal string PatchVersion;
    internal string File;
    internal string Sha256;
    internal long Size;
    internal string SourceI18nSha256;
}

internal sealed class PatchVersion : IComparable<PatchVersion> {
    internal readonly int Year, Month, Day, Revision;
    PatchVersion(int year,int month,int day,int revision){Year=year;Month=month;Day=day;Revision=revision;}
    internal static PatchVersion Parse(string value){
        if(String.IsNullOrWhiteSpace(value) || !Regex.IsMatch(value,"^[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}\\.(?:0|[1-9][0-9]*)$",RegexOptions.CultureInvariant))throw new ReleaseUpdateException("patch_version must be YYYY.MM.DD.N without a leading-zero revision.");
        string[] p=value.Split('.');int y=Int32.Parse(p[0],CultureInfo.InvariantCulture),m=Int32.Parse(p[1],CultureInfo.InvariantCulture),d=Int32.Parse(p[2],CultureInfo.InvariantCulture),r=Int32.Parse(p[3],CultureInfo.InvariantCulture);
        try{new DateTime(y,m,d);}catch(Exception ex){throw new ReleaseUpdateException("patch_version has an invalid calendar date.",ex);}return new PatchVersion(y,m,d,r);
    }
    public int CompareTo(PatchVersion other){if(other==null)return 1;int result=Year.CompareTo(other.Year);if(result!=0)return result;result=Month.CompareTo(other.Month);if(result!=0)return result;result=Day.CompareTo(other.Day);if(result!=0)return result;return Revision.CompareTo(other.Revision);}
}

internal sealed class ReleaseUpdateException : Exception {
    internal ReleaseUpdateException(string message) : base(message) { }
    internal ReleaseUpdateException(string message, Exception inner) : base(message, inner) { }
}

// Internal on purpose: the shipped Setup EXE exposes no endpoint setting,
// command-line switch, registry key or environment variable for this seam.
// It exists solely so the separately compiled test harness can use HttpListener.
internal interface IReleaseHttpTransport {
    ReleaseHttpResponse Get(Uri uri, string accept, long maximumBytes);
}
internal sealed class ReleaseHttpResponse {
    internal readonly int StatusCode;
    internal readonly long ContentLength;
    internal readonly byte[] Body;
    internal ReleaseHttpResponse(int statusCode,long contentLength,byte[] body){StatusCode=statusCode;ContentLength=contentLength;Body=body;}
}

internal static class WakfuReleaseUpdater {
    internal const string Owner = "Relactive";
    internal const string Repository = "wakfu-turkiye-yama-calismasi";
    internal const string RepositorySlug = Owner + "/" + Repository;
    internal const string ApiBase = "https://api.github.com/repos/" + RepositorySlug;
    internal const string ManifestAssetName = "manifest.json";
    internal const string PatchAssetName = "i18n.jar";
    internal const long MaximumManifestBytes = 256 * 1024;
    internal const long MaximumPatchBytes = 512L * 1024 * 1024;
#if WAKFU_TESTS
    internal static IReleaseHttpTransport TestTransportOverride;
#endif
    static readonly Regex HashPattern = new Regex("^[A-Fa-f0-9]{64}$", RegexOptions.CultureInvariant);
    static readonly Regex GameVersionPattern = new Regex("^[0-9]+(?:\\.[0-9]+){1,10}$", RegexOptions.CultureInvariant);
    static readonly Regex PatchVersionPattern = new Regex("^[0-9]{4}\\.[0-9]{2}\\.[0-9]{2}\\.[0-9]+$", RegexOptions.CultureInvariant);

    internal static Uri LatestReleaseUri { get { return new Uri(ApiBase + "/releases/latest"); } }

    // Fixed production transport. The shipped Setup has no endpoint setting;
    // tests provide a separate internal implementation.
    internal sealed class GitHubReleaseHttpTransport : IReleaseHttpTransport {
        public ReleaseHttpResponse Get(Uri uri, string accept, long maximumBytes) {
            using (var response = OpenFollowingOnlyAllowedRedirects(uri, accept)) {
                if (response.ContentLength > maximumBytes) throw new ReleaseUpdateException("GitHub response exceeded the safe size limit.");
                using (var input = response.GetResponseStream()) using (var memory = new MemoryStream()) {
                    byte[] buffer = new byte[65536];
                    int read;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0) {
                        if (memory.Length + read > maximumBytes) throw new ReleaseUpdateException("GitHub response exceeded the safe size limit.");
                        memory.Write(buffer, 0, read);
                    }
                    return new ReleaseHttpResponse((int)response.StatusCode, response.ContentLength, memory.ToArray());
                }
            }
        }
    }

    internal static LatestPatchRelease GetLatestRelease(IReleaseHttpTransport transport) {
        if (transport == null) throw new ArgumentNullException("transport");
        ReleaseHttpResponse response;try{response=transport.Get(LatestReleaseUri,"application/vnd.github+json",MaximumManifestBytes);}catch(ReleaseUpdateException){throw;}catch(Exception ex){throw new ReleaseUpdateException("GitHub latest Release isteği tamamlanamadı.",ex);}
        if(response==null||response.StatusCode!=200||response.Body==null||response.Body.Length==0||response.Body.Length>MaximumManifestBytes)throw new ReleaseUpdateException("GitHub latest Release yanıtı geçersiz.");
        if(response.ContentLength>=0&&response.ContentLength!=response.Body.Length)throw new ReleaseUpdateException("GitHub latest Release Content-Length uyuşmuyor.");
        return ParseLatestRelease(Encoding.UTF8.GetString(response.Body));
    }

    internal static bool IsAllowedDownloadUri(Uri uri) {
        if (uri == null || !String.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase) || uri.UserInfo.Length != 0 || uri.Port != 443) return false;
        string host = uri.Host;
        return String.Equals(host, "api.github.com", StringComparison.OrdinalIgnoreCase)
            || String.Equals(host, "github.com", StringComparison.OrdinalIgnoreCase)
            || String.Equals(host, "objects.githubusercontent.com", StringComparison.OrdinalIgnoreCase)
            || String.Equals(host, "release-assets.githubusercontent.com", StringComparison.OrdinalIgnoreCase)
            || String.Equals(host, "github-releases.githubusercontent.com", StringComparison.OrdinalIgnoreCase);
    }

    static string RequiredString(Dictionary<string, object> map, string name) {
        object value;
        if (!map.TryGetValue(name, out value) || !(value is string) || String.IsNullOrWhiteSpace((string)value)) throw new ReleaseUpdateException("Release " + name + " alanı geçersiz.");
        return ((string)value).Trim();
    }

    static long RequiredPositiveInteger(Dictionary<string, object> map, string name, long maximum) {
        object value;
        if (!map.TryGetValue(name, out value) || value == null) throw new ReleaseUpdateException("Release " + name + " alanı eksik.");
        long result;
        try { result = Convert.ToInt64(value, CultureInfo.InvariantCulture); } catch { throw new ReleaseUpdateException("Release " + name + " alanı tamsayı değil."); }
        if (result <= 0 || result > maximum) throw new ReleaseUpdateException("Release " + name + " alanı güvenli sınırlar dışında.");
        return result;
    }

    static Dictionary<string, object> DeserializeObject(string json, string label) {
        try {
            var serializer = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
            var value = serializer.DeserializeObject(json) as Dictionary<string, object>;
            if (value == null) throw new ReleaseUpdateException(label + " JSON nesnesi değil.");
            return value;
        } catch (ReleaseUpdateException) { throw; }
        catch (Exception ex) { throw new ReleaseUpdateException(label + " JSON'u okunamadı.", ex); }
    }

    internal static LatestPatchRelease ParseLatestRelease(string json) {
        var map = DeserializeObject(json, "GitHub Release");
        object draft, prerelease, rawAssets;
        if (!map.TryGetValue("draft", out draft) || Convert.ToBoolean(draft, CultureInfo.InvariantCulture)) throw new ReleaseUpdateException("Taslak Release kullanılmaz.");
        if (!map.TryGetValue("prerelease", out prerelease) || Convert.ToBoolean(prerelease, CultureInfo.InvariantCulture)) throw new ReleaseUpdateException("Ön-sürüm Release kullanılmaz.");
        long id = RequiredPositiveInteger(map, "id", Int64.MaxValue);
        string tag = RequiredString(map, "tag_name");
        if (!map.TryGetValue("assets", out rawAssets)) throw new ReleaseUpdateException("Release asset listesi yok.");
        object[] list = rawAssets as object[];
        if (list == null) throw new ReleaseUpdateException("Release asset listesi geçersiz.");
        var assets = new Dictionary<string, ReleaseAsset>(StringComparer.Ordinal);
        foreach (object item in list) {
            var asset = item as Dictionary<string, object>;
            if (asset == null) throw new ReleaseUpdateException("Release asset kaydı geçersiz.");
            string name = RequiredString(asset, "name");
            if (assets.ContainsKey(name)) throw new ReleaseUpdateException("Release içinde yinelenen asset adı var: " + name);
            assets.Add(name, new ReleaseAsset { Id = RequiredPositiveInteger(asset, "id", Int64.MaxValue), Name = name, Size = RequiredPositiveInteger(asset, "size", MaximumPatchBytes) });
        }
        ReleaseAsset manifest, patch;
        if (!assets.TryGetValue(ManifestAssetName, out manifest) || manifest.Size > MaximumManifestBytes) throw new ReleaseUpdateException("Release manifest.json asset'i eksik veya çok büyük.");
        if (!assets.TryGetValue(PatchAssetName, out patch)) throw new ReleaseUpdateException("Release i18n.jar asset'i eksik.");
        return new LatestPatchRelease { Id = id, Tag = tag, Assets = assets };
    }

    internal static PatchManifest ParseManifest(string json, string releaseTag) {
        var map = DeserializeObject(json, "manifest.json");
        string gameVersion = RequiredString(map, "game_version");
        string patchVersion = RequiredString(map, "patch_version");
        string file = RequiredString(map, "file");
        string sha256 = RequiredString(map, "sha256");
        string sourceSha256 = RequiredString(map, "source_i18n_sha256");
        long size = RequiredPositiveInteger(map, "size", MaximumPatchBytes);
        if (!GameVersionPattern.IsMatch(gameVersion)) throw new ReleaseUpdateException("manifest.json game_version biçimi geçersiz.");
        PatchVersion.Parse(patchVersion);
        if (!String.Equals(file, PatchAssetName, StringComparison.Ordinal)) throw new ReleaseUpdateException("manifest.json yalnız i18n.jar paketini tanımlayabilir.");
        if (!HashPattern.IsMatch(sha256) || !HashPattern.IsMatch(sourceSha256)) throw new ReleaseUpdateException("manifest.json SHA-256 alanı geçersiz.");
        if (!String.Equals(releaseTag, "tr-" + patchVersion, StringComparison.Ordinal)) throw new ReleaseUpdateException("Release etiketi patch_version ile eşleşmiyor.");
        return new PatchManifest { GameVersion = gameVersion, PatchVersion = patchVersion, File = file, Sha256 = sha256.ToUpperInvariant(), Size = size, SourceI18nSha256 = sourceSha256.ToUpperInvariant() };
    }

    internal static void ValidateReleaseContract(LatestPatchRelease release, PatchManifest manifest) {
        ReleaseAsset patch;
        if (release == null || manifest == null || !release.Assets.TryGetValue(manifest.File, out patch)) throw new ReleaseUpdateException("Release paketi eksik.");
        if (patch.Size != manifest.Size) throw new ReleaseUpdateException("Release asset boyutu manifest.json ile uyuşmuyor.");
    }

    internal static string Sha256File(string path) {
        using (var sha = SHA256.Create()) using (var input = File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "");
    }

    internal static void VerifyDownloadedPatch(string path, PatchManifest manifest) {
        if (manifest == null || !File.Exists(path)) throw new ReleaseUpdateException("İndirilen yama dosyası bulunamadı.");
        long length = new FileInfo(path).Length;
        if (length != manifest.Size) throw new ReleaseUpdateException("İndirilen dosya boyutu manifest.json ile eşleşmiyor.");
        if (!String.Equals(Sha256File(path), manifest.Sha256, StringComparison.OrdinalIgnoreCase)) throw new ReleaseUpdateException("İndirilen dosyanın SHA-256 özeti eşleşmiyor.");
    }

    static HttpWebRequest Request(Uri uri, string accept) {
        if (!IsAllowedDownloadUri(uri)) throw new ReleaseUpdateException("GitHub allowlist güvenli olmayan bir adresi reddetti.");
        var request = (HttpWebRequest)WebRequest.Create(uri);
        request.Method = "GET";
        request.AllowAutoRedirect = false;
        request.UserAgent = "WakfuTurkceYamaSetup/1.0 (Release updater)";
        request.Accept = accept;
        request.Timeout = 30000;
        request.ReadWriteTimeout = 30000;
        request.AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate;
        return request;
    }

    static HttpWebResponse OpenFollowingOnlyAllowedRedirects(Uri initial, string accept) {
        Uri next = initial;
        for (int hop = 0; hop < 6; hop++) {
            try {
                var response = (HttpWebResponse)Request(next, accept).GetResponse();
                int status = (int)response.StatusCode;
                if (status >= 300 && status <= 399) {
                    string location = response.Headers[HttpResponseHeader.Location];
                    response.Close();
                    Uri redirected;
                    if (String.IsNullOrWhiteSpace(location) || !Uri.TryCreate(next, location, out redirected) || !IsAllowedDownloadUri(redirected)) throw new ReleaseUpdateException("GitHub yönlendirmesi allowlist dışına çıktı.");
                    next = redirected;
                    continue;
                }
                if (status != 200) { response.Close(); throw new ReleaseUpdateException("GitHub isteği beklenmeyen HTTP durumu döndürdü: " + status); }
                return response;
            } catch (WebException ex) {
                var response = ex.Response as HttpWebResponse;
                if (response != null) { int status = (int)response.StatusCode; response.Close(); throw new ReleaseUpdateException("GitHub isteği başarısız oldu: HTTP " + status, ex); }
                throw new ReleaseUpdateException("GitHub'a erişilemedi.", ex);
            }
        }
        throw new ReleaseUpdateException("GitHub yönlendirme sınırı aşıldı.");
    }

    static byte[] DownloadSmallAsset(long assetId, long expectedSize) {
        if (assetId <= 0 || expectedSize <= 0 || expectedSize > MaximumManifestBytes) throw new ReleaseUpdateException("Geçersiz manifest asset kimliği veya boyutu.");
        Uri uri = new Uri(ApiBase + "/releases/assets/" + assetId.ToString(CultureInfo.InvariantCulture));
        using (var response = OpenFollowingOnlyAllowedRedirects(uri, "application/octet-stream")) {
            if (response.ContentLength >= 0 && response.ContentLength != expectedSize) throw new ReleaseUpdateException("GitHub manifest asset boyutu beklenenden farklı.");
            using (var input = response.GetResponseStream()) using (var output = new MemoryStream()) {
                input.CopyTo(output);
                if (output.Length != expectedSize || output.Length > MaximumManifestBytes) throw new ReleaseUpdateException("GitHub manifest asset'i eksik veya fazla indirildi.");
                return output.ToArray();
            }
        }
    }

    internal static LatestPatchRelease GetLatestRelease() {
        return GetLatestRelease(new GitHubReleaseHttpTransport());
    }

    internal static PatchManifest GetManifestLegacy(LatestPatchRelease release) {
        if (release == null) throw new ReleaseUpdateException("Release bilgisi yok.");
        ReleaseAsset asset;
        if (!release.Assets.TryGetValue(ManifestAssetName, out asset)) throw new ReleaseUpdateException("manifest.json bulunamadı.");
        var manifest = ParseManifest(Encoding.UTF8.GetString(DownloadSmallAsset(asset.Id, asset.Size)), release.Tag);
        ValidateReleaseContract(release, manifest);
        return manifest;
    }

    internal static PatchManifest GetManifest(LatestPatchRelease release) {
        return GetManifest(release, new GitHubReleaseHttpTransport());
    }

    internal static PatchManifest GetManifestLegacyTransport(LatestPatchRelease release,IReleaseHttpTransport transport) {
        if(release==null||transport==null)throw new ArgumentNullException();ReleaseAsset asset;if(!release.Assets.TryGetValue(ManifestAssetName,out asset))throw new ReleaseUpdateException("manifest.json bulunamadı.");
        ReleaseHttpResponse response;try{response=transport.Get(new Uri(ApiBase+"/releases/assets/"+asset.Id.ToString(CultureInfo.InvariantCulture)),"application/octet-stream",MaximumManifestBytes);}catch(ReleaseUpdateException){throw;}catch(Exception ex){throw new ReleaseUpdateException("manifest.json indirilemedi.",ex);}
        if(response==null||response.StatusCode!=200||response.Body==null||response.Body.Length==0||response.Body.Length>MaximumManifestBytes)throw new ReleaseUpdateException("manifest.json HTTP yanıtı geçersiz.");if(response.ContentLength>=0&&response.ContentLength!=response.Body.Length)throw new ReleaseUpdateException("manifest.json Content-Length uyuşmuyor.");var manifest=ParseManifest(Encoding.UTF8.GetString(response.Body),release.Tag);ValidateReleaseContract(release,manifest);return manifest;
    }

    internal static PatchManifest GetManifest(LatestPatchRelease release, IReleaseHttpTransport transport) {
        if (release == null || transport == null) throw new ArgumentNullException();
        ReleaseAsset asset;
        if (!release.Assets.TryGetValue(ManifestAssetName, out asset)) throw new ReleaseUpdateException("manifest.json asset is missing.");
        ReleaseHttpResponse response;
        try { response = transport.Get(new Uri(ApiBase + "/releases/assets/" + asset.Id.ToString(CultureInfo.InvariantCulture)), "application/octet-stream", MaximumManifestBytes); }
        catch (ReleaseUpdateException) { throw; }
        catch (Exception ex) { throw new ReleaseUpdateException("manifest.json download failed.", ex); }
        if (response == null || response.StatusCode != 200 || response.Body == null || response.Body.Length == 0 || response.Body.Length > MaximumManifestBytes) throw new ReleaseUpdateException("manifest.json HTTP response is invalid.");
        if (response.ContentLength >= 0 && response.ContentLength != response.Body.Length) throw new ReleaseUpdateException("manifest.json Content-Length mismatch.");
        if (response.Body.Length != asset.Size) throw new ReleaseUpdateException("manifest.json asset size mismatch.");
        PatchManifest manifest = ParseManifest(Encoding.UTF8.GetString(response.Body), release.Tag);
        ValidateReleaseContract(release, manifest);
        return manifest;
    }

    internal static void DownloadPatchLegacy(LatestPatchRelease release, PatchManifest manifest, string destination) {
        ValidateReleaseContract(release, manifest);
        ReleaseAsset asset = release.Assets[manifest.File];
        Uri uri = new Uri(ApiBase + "/releases/assets/" + asset.Id.ToString(CultureInfo.InvariantCulture));
        string temporary = destination + "." + Guid.NewGuid().ToString("N") + ".part";
        try {
            using (var response = OpenFollowingOnlyAllowedRedirects(uri, "application/octet-stream")) {
                if (response.ContentLength >= 0 && response.ContentLength != manifest.Size) throw new ReleaseUpdateException("GitHub i18n.jar asset boyutu beklenenden farklı.");
                using (var input = response.GetResponseStream()) using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
                    byte[] buffer = new byte[65536]; int read; long total = 0;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0) {
                        total += read;
                        if (total > manifest.Size || total > MaximumPatchBytes) throw new ReleaseUpdateException("GitHub i18n.jar asset'i beklenenden büyük.");
                        output.Write(buffer, 0, read);
                    }
                    output.Flush(true);
                }
            }
            VerifyDownloadedPatch(temporary, manifest);
            File.Move(temporary, destination);
        } finally { if (File.Exists(temporary)) try { File.Delete(temporary); } catch { } }
    }

    internal static void DownloadPatch(LatestPatchRelease release, PatchManifest manifest, string destination) {
#if WAKFU_TESTS
        if (TestTransportOverride != null) { DownloadPatch(release, manifest, destination, TestTransportOverride); return; }
#endif
        DownloadPatch(release, manifest, destination, new GitHubReleaseHttpTransport());
    }

    internal static void DownloadPatchLegacy(LatestPatchRelease release,PatchManifest manifest,string destination,IReleaseHttpTransport transport){
        ValidateReleaseContract(release,manifest);if(transport==null)throw new ArgumentNullException("transport");ReleaseAsset asset=release.Assets[manifest.File];ReleaseHttpResponse response;try{response=transport.Get(new Uri(ApiBase+"/releases/assets/"+asset.Id.ToString(CultureInfo.InvariantCulture)),"application/octet-stream",MaximumPatchBytes);}catch(ReleaseUpdateException){throw;}catch(Exception ex){throw new ReleaseUpdateException("i18n.jar indirilemedi.",ex);}
        if(response==null||response.StatusCode!=200||response.Body==null)throw new ReleaseUpdateException("i18n.jar HTTP yanıtı geçersiz.");if(response.ContentLength>=0&&response.ContentLength!=response.Body.Length)throw new ReleaseUpdateException("i18n.jar Content-Length uyuşmuyor.");string temporary=destination+"."+Guid.NewGuid().ToString("N")+".part";try{File.WriteAllBytes(temporary,response.Body);VerifyDownloadedPatch(temporary,manifest);File.Move(temporary,destination);}finally{if(File.Exists(temporary))try{File.Delete(temporary);}catch{}}
    }

    internal static void DownloadPatch(LatestPatchRelease release, PatchManifest manifest, string destination, IReleaseHttpTransport transport) {
        ValidateReleaseContract(release, manifest);
        if (transport == null) throw new ArgumentNullException("transport");
        ReleaseAsset asset = release.Assets[manifest.File];
        ReleaseHttpResponse response;
        try { response = transport.Get(new Uri(ApiBase + "/releases/assets/" + asset.Id.ToString(CultureInfo.InvariantCulture)), "application/octet-stream", MaximumPatchBytes); }
        catch (ReleaseUpdateException) { throw; }
        catch (Exception ex) { throw new ReleaseUpdateException("i18n.jar download failed.", ex); }
        if (response == null || response.StatusCode != 200 || response.Body == null) throw new ReleaseUpdateException("i18n.jar HTTP response is invalid.");
        if (response.ContentLength >= 0 && response.ContentLength != response.Body.Length) throw new ReleaseUpdateException("i18n.jar Content-Length mismatch.");
        if (response.Body.Length != asset.Size || response.Body.Length != manifest.Size) throw new ReleaseUpdateException("i18n.jar asset size mismatch.");
        string temporary = destination + "." + Guid.NewGuid().ToString("N") + ".part";
        try { File.WriteAllBytes(temporary, response.Body); VerifyDownloadedPatch(temporary, manifest); File.Move(temporary, destination); }
        finally { if (File.Exists(temporary)) try { File.Delete(temporary); } catch { } }
    }

    internal static bool IsOfflineFailure(Exception ex) {
        while (ex != null) { if (ex is WebException || ex is TimeoutException) return true; ex = ex.InnerException; }
        return false;
    }

    internal static void WriteInstalledPatchState(string path, Dictionary<string, object> state) {
        string directory = Path.GetDirectoryName(path);
        if (String.IsNullOrWhiteSpace(directory)) throw new ReleaseUpdateException("Yama durum dosyası yolu geçersiz.");
        Directory.CreateDirectory(directory);
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            var serializer = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
            File.WriteAllText(temporary, serializer.Serialize(state), new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
        } finally { if (File.Exists(temporary)) try { File.Delete(temporary); } catch { } }
    }
}
