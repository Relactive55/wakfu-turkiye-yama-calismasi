using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

// These tests exercise the internal seam, not a user-facing endpoint switch.
// The production updater still constructs only its fixed GitHub transport;
// this assembly is compiled with WAKFU_TESTS.
static class ReleaseUpdaterTests {
    sealed class ResponseSpec {
        internal int StatusCode = 200;
        internal byte[] Body = new byte[0];
        internal long ContentLength = -1;
        internal string Location;
        internal bool DropConnection;
    }

    sealed class LocalFakeGitHubTransport : IReleaseHttpTransport, IDisposable {
        readonly Dictionary<string, ResponseSpec> routes;
        readonly Uri endpoint;
        HttpListener server;
        internal LocalFakeGitHubTransport(Dictionary<string, ResponseSpec> routeMap) { routes = routeMap; endpoint = new Uri("http://127.0.0.1:" + FreePort() + "/"); }
        static int FreePort() { var listener = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0); listener.Start(); int port = ((System.Net.IPEndPoint)listener.LocalEndpoint).Port; listener.Stop(); return port; }
        ResponseSpec Resolve(string path) { ResponseSpec spec; if (routes.TryGetValue(path, out spec)) return spec; return new ResponseSpec { StatusCode = 404, Body = Encoding.UTF8.GetBytes("not found") }; }
        public ReleaseHttpResponse Get(Uri requested, string accept, long maximumBytes) {
            server = new HttpListener(); server.Prefixes.Add(endpoint.AbsoluteUri); server.Start();
            ResponseSpec spec = Resolve(requested.AbsolutePath);
            var worker = new Thread(delegate() {
                try {
                    HttpListenerContext context = server.GetContext();
                    context.Response.StatusCode = spec.StatusCode;
                    if (!String.IsNullOrWhiteSpace(spec.Location)) context.Response.RedirectLocation = spec.Location;
                    byte[] body = spec.Body ?? new byte[0];
                    long advertised = spec.ContentLength >= 0 ? spec.ContentLength : body.Length;
                    context.Response.ContentLength64 = advertised;
                    if (!spec.DropConnection && body.Length > 0) context.Response.OutputStream.Write(body, 0, body.Length);
                    else if (spec.DropConnection && body.Length > 1) context.Response.OutputStream.Write(body, 0, body.Length / 2);
                    context.Response.Close();
                } catch { try { server.Stop(); } catch { } }
            });
            worker.IsBackground = true; worker.Start();
            try {
                var request = (HttpWebRequest)WebRequest.Create(endpoint);
                request.AllowAutoRedirect = false; request.Timeout = 3000; request.ReadWriteTimeout = 3000;
                using (var response = (HttpWebResponse)request.GetResponse()) using (var input = response.GetResponseStream()) using (var memory = new MemoryStream()) { input.CopyTo(memory); return new ReleaseHttpResponse((int)response.StatusCode, response.ContentLength, memory.ToArray()); }
            } catch (WebException ex) {
                var response = ex.Response as HttpWebResponse; if (response == null) throw;
                using (response) using (var input = response.GetResponseStream()) using (var memory = new MemoryStream()) { if (input != null) input.CopyTo(memory); return new ReleaseHttpResponse((int)response.StatusCode, response.ContentLength, memory.ToArray()); }
            } finally { try { worker.Join(3000); } catch { } try { if (server != null) server.Stop(); } catch { } }
        }
        public void Dispose() { try { if (server != null) server.Close(); } catch { } }
    }

    sealed class ThrowingTransport : IReleaseHttpTransport {
        readonly Exception error;
        internal ThrowingTransport(Exception value) { error = value; }
        public ReleaseHttpResponse Get(Uri uri, string accept, long maximumBytes) { throw error; }
    }

    sealed class Fixture {
        internal readonly byte[] SourceJar;
        internal readonly byte[] PatchJar;
        internal readonly string SourceHash;
        internal readonly string PatchHash;
        internal readonly string ManifestJson;
        internal readonly string ReleaseJson;
        internal Fixture() { SourceJar = CreateJar("source"); PatchJar = CreateJar("translated"); SourceHash = Hash(SourceJar); PatchHash = Hash(PatchJar); ManifestJson = ManifestJsonFor(PatchHash, PatchJar.Length, SourceHash); ReleaseJson = ReleaseJsonFor(Encoding.UTF8.GetByteCount(ManifestJson), PatchJar.Length); }
        internal LocalFakeGitHubTransport Transport() {
            var routes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) {
                { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(ReleaseJson) } },
                { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = Encoding.UTF8.GetBytes(ManifestJson) } },
                { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = PatchJar } }
            }; return new LocalFakeGitHubTransport(routes);
        }
    }

    static void Require(bool condition, string message) { if (!condition) throw new Exception(message); }
    static void ExpectFailure(string name, Action action) { try { action(); throw new Exception(name + " unexpectedly succeeded"); } catch (ReleaseUpdateException) { } catch (WebException) { } catch (TimeoutException) { } }
    static string Hash(byte[] bytes) { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", ""); }
    static byte[] CreateJar(string marker) {
        using (var memory = new MemoryStream()) { using (var zip = new ZipArchive(memory, ZipArchiveMode.Create, true)) foreach (string name in new[] { "texts_en.properties", "texts_en_cleaned.properties" }) { ZipArchiveEntry entry = zip.CreateEntry(name); using (var writer = new StreamWriter(entry.Open(), new UTF8Encoding(false))) writer.Write("fixture=" + marker + "\n"); } return memory.ToArray(); }
    }
    static string ManifestJsonFor(string hash, int size, string sourceHash) { return "{\"game_version\":\"1.92.1.5172.314\",\"patch_version\":\"2026.09.05.2\",\"file\":\"i18n.jar\",\"sha256\":\"" + hash + "\",\"size\":" + size + ",\"source_i18n_sha256\":\"" + sourceHash + "\"}"; }
    static string ReleaseJsonFor(int manifestSize, int patchSize) { return "{\"id\":12,\"tag_name\":\"tr-2026.09.05.2\",\"draft\":false,\"prerelease\":false,\"assets\":[{\"id\":13,\"name\":\"manifest.json\",\"size\":" + manifestSize + "},{\"id\":14,\"name\":\"i18n.jar\",\"size\":" + patchSize + "}]}"; }
    static string ReleaseJsonWithAssets(string assets) { return "{\"id\":12,\"tag_name\":\"tr-2026.09.05.2\",\"draft\":false,\"prerelease\":false,\"assets\":[" + assets + "]}"; }
    static Dictionary<string, ResponseSpec> LatestOnly(string json, int status) { return new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { StatusCode = status, Body = Encoding.UTF8.GetBytes(json) } } }; }
    static Dictionary<string, ResponseSpec> LatestOnlySpec(ResponseSpec spec) { return new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", spec } }; }
    static LocalFakeGitHubTransport ServerFor(Dictionary<string, ResponseSpec> routes) { return new LocalFakeGitHubTransport(routes); }

    static void TestContractAndHash(string root) {
        var fixture = new Fixture(); string data = Path.Combine(root, "payload.jar"); File.WriteAllBytes(data, fixture.PatchJar); var release = WakfuReleaseUpdater.ParseLatestRelease(fixture.ReleaseJson); var manifest = WakfuReleaseUpdater.ParseManifest(fixture.ManifestJson, release.Tag); WakfuReleaseUpdater.ValidateReleaseContract(release, manifest); WakfuReleaseUpdater.VerifyDownloadedPatch(data, manifest); string channelManifest = fixture.ManifestJson.Replace("1.92.1.5172.314", "6.0_1.92.1.5172.314"); Require(WakfuReleaseUpdater.ParseManifest(channelManifest, release.Tag).GameVersion == "6.0_1.92.1.5172.314", "Ankama channel game version was rejected");
        File.WriteAllBytes(data, new byte[] { 1, 2, 3, 5 }); ExpectFailure("SHA mismatch", delegate { WakfuReleaseUpdater.VerifyDownloadedPatch(data, manifest); }); Require(WakfuReleaseUpdater.IsAllowedDownloadUri(new Uri("https://api.github.com/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest")), "fixed GitHub API rejected"); Require(!WakfuReleaseUpdater.IsAllowedDownloadUri(new Uri("http://api.github.com/repos/a")), "HTTP accepted"); Require(!WakfuReleaseUpdater.IsAllowedDownloadUri(new Uri("https://example.invalid/x")), "arbitrary host accepted"); Require(WakfuReleaseUpdater.IsOfflineFailure(new WebException("offline")), "offline failure not classified");
    }

    static void TestStableReleaseFlags() {
        var fixture = new Fixture(); string draft = fixture.ReleaseJson.Replace("\"draft\":false", "\"draft\":true"); string prerelease = fixture.ReleaseJson.Replace("\"prerelease\":false", "\"prerelease\":true"); ExpectFailure("draft release accepted", delegate { WakfuReleaseUpdater.ParseLatestRelease(draft); }); ExpectFailure("prerelease release accepted", delegate { WakfuReleaseUpdater.ParseLatestRelease(prerelease); });
    }

    static void TestFakeHttpEndToEnd(string root) {
        var fixture = new Fixture(); using (var server = fixture.Transport()) { var release = WakfuReleaseUpdater.GetLatestRelease(server); Require(release.Id == 12, "latest Release id was not parsed"); Require(release.Assets["manifest.json"].Id == 13, "manifest asset id was not retained"); Require(release.Assets["i18n.jar"].Id == 14, "i18n asset id was not retained"); var manifest = WakfuReleaseUpdater.GetManifest(release, server); Require(manifest.PatchVersion == "2026.09.05.2", "manifest schema was not validated"); string destination = Path.Combine(root, "downloaded.jar"); WakfuReleaseUpdater.DownloadPatch(release, manifest, destination, server); Require(File.Exists(destination), "asset download did not create destination"); WakfuReleaseUpdater.VerifyDownloadedPatch(destination, manifest); Require(new FileInfo(destination).Length == manifest.Size, "download size was not checked"); }
    }

    static void TestHttpFailureMatrix(string root) {
        var fixture = new Fixture(); ExpectFailure("connection refused", delegate { WakfuReleaseUpdater.GetLatestRelease(new ThrowingTransport(new WebException("refused", WebExceptionStatus.ConnectFailure))); }); ExpectFailure("timeout", delegate { WakfuReleaseUpdater.GetLatestRelease(new ThrowingTransport(new TimeoutException("timeout"))); });
        foreach (int status in new[] { 404, 500 }) using (var server = ServerFor(LatestOnly(fixture.ReleaseJson, status))) ExpectFailure("HTTP " + status, delegate { WakfuReleaseUpdater.GetLatestRelease(server); });
        using (var server = ServerFor(LatestOnly("", 200))) ExpectFailure("empty response", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); using (var server = ServerFor(LatestOnly("{bad", 200))) ExpectFailure("malformed JSON", delegate { WakfuReleaseUpdater.GetLatestRelease(server); });
        using (var server = ServerFor(LatestOnly(ReleaseJsonWithAssets("{\"id\":14,\"name\":\"i18n.jar\",\"size\":1}"), 200))) ExpectFailure("missing manifest", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); using (var server = ServerFor(LatestOnly(ReleaseJsonWithAssets("{\"id\":13,\"name\":\"manifest.json\",\"size\":1}"), 200))) ExpectFailure("missing i18n", delegate { WakfuReleaseUpdater.GetLatestRelease(server); });
        string duplicateManifest = "{\"id\":13,\"name\":\"manifest.json\",\"size\":1},{\"id\":15,\"name\":\"manifest.json\",\"size\":1},{\"id\":14,\"name\":\"i18n.jar\",\"size\":1}"; using (var server = ServerFor(LatestOnly(ReleaseJsonWithAssets(duplicateManifest), 200))) ExpectFailure("duplicate manifest", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); string duplicatePatch = "{\"id\":13,\"name\":\"manifest.json\",\"size\":1},{\"id\":14,\"name\":\"i18n.jar\",\"size\":1},{\"id\":15,\"name\":\"i18n.jar\",\"size\":1}"; using (var server = ServerFor(LatestOnly(ReleaseJsonWithAssets(duplicatePatch), 200))) ExpectFailure("duplicate i18n", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); using (var server = ServerFor(LatestOnly(ReleaseJsonWithAssets("{\"id\":0,\"name\":\"manifest.json\",\"size\":1},{\"id\":14,\"name\":\"i18n.jar\",\"size\":1}"), 200))) ExpectFailure("invalid asset id", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); using (var server = ServerFor(LatestOnly(ReleaseJsonWithAssets("{\"id\":13,\"name\":\"unexpected.bin\",\"size\":1},{\"id\":14,\"name\":\"i18n.jar\",\"size\":1}"), 200))) ExpectFailure("unexpected asset name", delegate { WakfuReleaseUpdater.GetLatestRelease(server); });
        var routes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ReleaseJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ManifestJson), ContentLength = Encoding.UTF8.GetByteCount(fixture.ManifestJson) - 1 } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = fixture.PatchJar } } }; using (var server = ServerFor(routes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); ExpectFailure("manifest Content-Length", delegate { WakfuReleaseUpdater.GetManifest(release, server); }); }
        var manifest404 = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ReleaseJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { StatusCode = 404, Body = Encoding.UTF8.GetBytes("missing") } } }; using (var server = ServerFor(manifest404)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); ExpectFailure("manifest download 404", delegate { WakfuReleaseUpdater.GetManifest(release, server); }); }
        var i18n404 = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ReleaseJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ManifestJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { StatusCode = 404, Body = Encoding.UTF8.GetBytes("missing") } } }; using (var server = ServerFor(i18n404)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); ExpectFailure("i18n download 404", delegate { WakfuReleaseUpdater.DownloadPatch(release, manifest, Path.Combine(root, "missing.jar"), server); }); }
        byte[] manifestBytes = Encoding.UTF8.GetBytes(fixture.ManifestJson); routes["/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13"] = new ResponseSpec { Body = manifestBytes.SubArray(0, manifestBytes.Length - 2) }; using (var server = ServerFor(routes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); ExpectFailure("truncated manifest", delegate { WakfuReleaseUpdater.GetManifest(release, server); }); }
        var patchShort = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ReleaseJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = manifestBytes } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = fixture.PatchJar.SubArray(0, fixture.PatchJar.Length - 1) } } }; using (var server = ServerFor(patchShort)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); ExpectFailure("truncated i18n", delegate { WakfuReleaseUpdater.DownloadPatch(release, manifest, Path.Combine(root, "short.jar"), server); }); }
        var contentRoutes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ReleaseJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = manifestBytes } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = fixture.PatchJar, ContentLength = fixture.PatchJar.Length + 1 } } }; using (var server = ServerFor(contentRoutes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); ExpectFailure("i18n Content-Length", delegate { WakfuReleaseUpdater.DownloadPatch(release, manifest, Path.Combine(root, "content-mismatch.jar"), server); }); }
        string wrongManifest = ManifestJsonFor(new String('0', 64), fixture.PatchJar.Length, fixture.SourceHash); var wrongHashRoutes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(ReleaseJsonFor(Encoding.UTF8.GetByteCount(wrongManifest), fixture.PatchJar.Length)) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = Encoding.UTF8.GetBytes(wrongManifest) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = fixture.PatchJar } } }; using (var server = ServerFor(wrongHashRoutes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); ExpectFailure("SHA mismatch", delegate { WakfuReleaseUpdater.DownloadPatch(release, manifest, Path.Combine(root, "sha.jar"), server); }); }
        string mismatchManifest = ManifestJsonFor(fixture.PatchHash, fixture.PatchJar.Length + 1, fixture.SourceHash); var mismatchRoutes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(ReleaseJsonFor(Encoding.UTF8.GetByteCount(mismatchManifest), fixture.PatchJar.Length)) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = Encoding.UTF8.GetBytes(mismatchManifest) } } }; using (var server = ServerFor(mismatchRoutes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); ExpectFailure("manifest size mismatch", delegate { WakfuReleaseUpdater.GetManifest(release, server); }); }
        var dropRoutes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(fixture.ReleaseJson) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = manifestBytes } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = fixture.PatchJar, ContentLength = fixture.PatchJar.Length, DropConnection = true } } }; using (var server = ServerFor(dropRoutes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); ExpectFailure("connection drop", delegate { WakfuReleaseUpdater.DownloadPatch(release, manifest, Path.Combine(root, "drop.jar"), server); }); }
        var redirect = new ResponseSpec { StatusCode = 302, Location = "http://api.github.com/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest" }; using (var server = ServerFor(LatestOnlySpec(redirect))) ExpectFailure("HTTPS downgrade redirect", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); var loop = new ResponseSpec { StatusCode = 302, Location = "https://api.github.com/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest" }; using (var server = ServerFor(LatestOnlySpec(loop))) ExpectFailure("redirect loop", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); var forbidden = new ResponseSpec { StatusCode = 302, Location = "https://evil.example/releases/latest" }; using (var server = ServerFor(LatestOnlySpec(forbidden))) ExpectFailure("non-allowlisted redirect", delegate { WakfuReleaseUpdater.GetLatestRelease(server); }); Require(!WakfuReleaseUpdater.IsAllowedDownloadUri(new Uri("http://api.github.com/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest")), "HTTPS downgrade allowed"); Require(!WakfuReleaseUpdater.IsAllowedDownloadUri(new Uri("https://evil.example/releases/latest")), "non-allowlisted redirect allowed");
    }

    static void TestInstallAndRollback(string root) {
        var fixture = new Fixture(); string fixtureRoot = Path.Combine(Path.GetTempPath(), "WakfuDagitimTest_" + Guid.NewGuid().ToString("N")); string game = Path.Combine(fixtureRoot, "game"); string state = Path.Combine(fixtureRoot, "state"); Directory.CreateDirectory(Path.Combine(game, "contents", "i18n")); Directory.CreateDirectory(state); string source = Path.Combine(game, "contents", "i18n", "i18n_en.jar"), old = Path.Combine(game, "contents", "i18n", "i18n.jar"); File.WriteAllBytes(source, fixture.SourceJar); File.WriteAllBytes(old, fixture.SourceJar); string previousState = Environment.GetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT"); Environment.SetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT", state);
        try {
            string wrongManifest = ManifestJsonFor(new String('0', 64), fixture.PatchJar.Length, fixture.SourceHash); var badRoutes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) { { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(ReleaseJsonFor(Encoding.UTF8.GetByteCount(wrongManifest), fixture.PatchJar.Length)) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/13", new ResponseSpec { Body = Encoding.UTF8.GetBytes(wrongManifest) } }, { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/14", new ResponseSpec { Body = fixture.PatchJar } } }; bool preinstallFailed = false; using (var server = ServerFor(badRoutes)) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); try { typeof(WakfuSetupApp).GetMethod("TestInstallReleasedPatch", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { game, release, manifest, server }); } catch (TargetInvocationException) { preinstallFailed = true; } } Require(preinstallFailed, "pre-install hash error did not fail"); Require(WakfuReleaseUpdater.Sha256File(source) == fixture.SourceHash, "pre-install error touched i18n_en"); Require(WakfuReleaseUpdater.Sha256File(old) == fixture.SourceHash, "pre-install error touched i18n");
            using (var server = fixture.Transport()) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); typeof(WakfuSetupApp).GetMethod("TestInstallReleasedPatch", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { game, release, manifest, server }); Require(WakfuReleaseUpdater.Sha256File(source) == fixture.PatchHash, "i18n_en was not installed"); Require(WakfuReleaseUpdater.Sha256File(old) == fixture.PatchHash, "i18n.jar was not installed"); string statePath = Path.Combine(state, "installed_patch.json"); Require(File.Exists(statePath), "installed_patch.json was not written"); string stateText = File.ReadAllText(statePath); Require(stateText.Contains("2026.09.05.2"), "installed patch version missing"); var stateMap = new System.Web.Script.Serialization.JavaScriptSerializer().Deserialize<Dictionary<string, object>>(stateText); string backup = Convert.ToString(stateMap["backup_dir"]); Require(File.Exists(Path.Combine(backup, "i18n_en.jar")), "i18n_en backup missing"); Require(File.Exists(Path.Combine(backup, "i18n.jar")), "i18n backup missing"); TestInstalledStateMatrix(game, manifest, statePath, source, old); }
            string statePathFailure = Path.Combine(state, "installed_patch.json"); if (File.Exists(statePathFailure)) File.Delete(statePathFailure); Directory.CreateDirectory(statePathFailure); File.WriteAllBytes(source, fixture.SourceJar); File.WriteAllBytes(old, fixture.SourceJar); string beforeSource = WakfuReleaseUpdater.Sha256File(source), beforeOld = WakfuReleaseUpdater.Sha256File(old); bool failed = false; using (var server = fixture.Transport()) { var release = WakfuReleaseUpdater.GetLatestRelease(server); var manifest = WakfuReleaseUpdater.GetManifest(release, server); try { typeof(WakfuSetupApp).GetMethod("TestInstallReleasedPatch", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { game, release, manifest, server }); } catch (TargetInvocationException) { failed = true; } } Require(failed, "state write failure did not fail install"); Require(WakfuReleaseUpdater.Sha256File(source) == beforeSource, "state failure did not roll back i18n_en"); Require(WakfuReleaseUpdater.Sha256File(old) == beforeOld, "state failure did not roll back i18n"); Require(Directory.Exists(statePathFailure), "state failure changed the state path");
        } finally { Environment.SetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT", previousState); try { Directory.Delete(fixtureRoot, true); } catch { } }
    }

    // Consumes the Python full-simulation output through the same internal
    // transport seam as the normal fake Release tests.  The fixture directory
    // is supplied only by the test runner; the shipped Setup has no such
    // endpoint or file-system override.
    static void TestExternalFullSimulation(string fixtureRoot) {
        if (String.IsNullOrWhiteSpace(fixtureRoot) || !Directory.Exists(fixtureRoot)) throw new Exception("full simulation fixture directory is missing");
        string manifestText = File.ReadAllText(Path.Combine(fixtureRoot, "manifest.json"), Encoding.UTF8);
        byte[] patch = File.ReadAllBytes(Path.Combine(fixtureRoot, "i18n.jar"));
        byte[] source = File.ReadAllBytes(Path.Combine(fixtureRoot, "version_a_i18n_en.jar"));
        string releaseJson = ExternalReleaseJsonFor(manifestText, patch.Length);
        var routes = new Dictionary<string, ResponseSpec>(StringComparer.Ordinal) {
            { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/latest", new ResponseSpec { Body = Encoding.UTF8.GetBytes(releaseJson) } },
            { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/101", new ResponseSpec { Body = Encoding.UTF8.GetBytes(manifestText) } },
            { "/repos/Relactive55/wakfu-turkiye-yama-calismasi/releases/assets/102", new ResponseSpec { Body = patch } }
        };
        string distributionRoot = Path.Combine(Path.GetTempPath(), "WakfuDagitimTest_" + Guid.NewGuid().ToString("N"));
        string game = Path.Combine(distributionRoot, "game");
        string state = Path.Combine(distributionRoot, "state");
        string previousStateRoot = Environment.GetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT");
        try {
            Directory.CreateDirectory(Path.Combine(game, "contents", "i18n"));
            Directory.CreateDirectory(state);
            string sourcePath = Path.Combine(game, "contents", "i18n", "i18n_en.jar");
            string activePath = Path.Combine(game, "contents", "i18n", "i18n.jar");
            File.WriteAllBytes(sourcePath, source);
            File.WriteAllBytes(activePath, source);
            Environment.SetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT", state);
            using (var server = ServerFor(routes)) {
                var release = WakfuReleaseUpdater.GetLatestRelease(server);
                var manifest = WakfuReleaseUpdater.GetManifest(release, server);
                Require(String.Equals(release.Tag, "tr-" + manifest.PatchVersion, StringComparison.Ordinal), "external Release tag does not match manifest patch version");
                Require(String.Equals(manifest.SourceI18nSha256, Hash(source), StringComparison.OrdinalIgnoreCase), "full simulation source baseline hash differs");
                typeof(WakfuSetupApp).GetMethod("TestInstallReleasedPatch", BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, new object[] { game, release, manifest, server });
                Require(WakfuReleaseUpdater.Sha256File(sourcePath) == manifest.Sha256, "full simulation i18n_en post-install hash failed");
                Require(WakfuReleaseUpdater.Sha256File(activePath) == manifest.Sha256, "full simulation i18n post-install hash failed");
                string statePath = Path.Combine(state, "installed_patch.json");
                Require(File.Exists(statePath), "full simulation installed_patch.json missing");
                string stateText = File.ReadAllText(statePath, Encoding.UTF8);
                Require(stateText.Contains(manifest.PatchVersion), "full simulation installed patch version missing");
                var stateMap = new System.Web.Script.Serialization.JavaScriptSerializer().Deserialize<Dictionary<string, object>>(stateText);
                string backup = Convert.ToString(stateMap["backup_dir"]);
                Require(File.Exists(Path.Combine(backup, "i18n_en.jar")), "full simulation i18n_en backup missing");
                Require(File.Exists(Path.Combine(backup, "i18n.jar")), "full simulation i18n backup missing");
            }
        } finally {
            Environment.SetEnvironmentVariable("WAKFU_PATCH_STATE_ROOT", previousStateRoot);
            try { Directory.Delete(distributionRoot, true); } catch { }
        }
    }

    static string ExternalReleaseJsonFor(string manifestJson, int patchSize) {
        var parsed = new System.Web.Script.Serialization.JavaScriptSerializer().Deserialize<Dictionary<string, object>>(manifestJson);
        string patchVersion = Convert.ToString(parsed["patch_version"]);
        return "{\"id\":42,\"tag_name\":\"tr-" + patchVersion + "\",\"draft\":false,\"prerelease\":false,\"assets\":[{\"id\":101,\"name\":\"manifest.json\",\"size\":" + Encoding.UTF8.GetByteCount(manifestJson).ToString(CultureInfo.InvariantCulture) + "},{\"id\":102,\"name\":\"i18n.jar\",\"size\":" + patchSize.ToString(CultureInfo.InvariantCulture) + "}]}";
    }

    static void TestInstalledStateMatrix(string game, PatchManifest manifest, string statePath, string source, string old) {
        var method = typeof(WakfuSetupApp).GetMethod("IsReleasedPatchInstalled", BindingFlags.Static | BindingFlags.NonPublic); Require(method != null, "state comparison method missing"); string escapedGame = game.Replace("\\", "\\\\"); string valid = "{\"game_dir\":\"" + escapedGame + "\",\"patch_version\":\"2026.09.05.2\",\"sha256\":\"" + manifest.Sha256 + "\"}"; File.WriteAllText(statePath, valid); Require((bool)method.Invoke(null, new object[] { game, manifest }), "valid state was rejected");
        File.Delete(statePath); Require(!(bool)method.Invoke(null, new object[] { game, manifest }), "missing installed_patch state accepted"); Require(File.Exists(source) && File.Exists(old), "missing state removed game files"); File.WriteAllText(statePath, valid); Require((bool)method.Invoke(null, new object[] { game, manifest }), "valid state was not restored");
        string[] invalid = new[] { "{", "{}", "{\"game_dir\":3,\"patch_version\":\"2026.09.05.2\",\"sha256\":\"" + manifest.Sha256 + "\"}", "{\"game_dir\":\"x\",\"patch_version\":\"bad\",\"sha256\":\"" + manifest.Sha256 + "\"}", "{\"game_dir\":\"" + escapedGame + "\",\"patch_version\":\"2026.09.05.1\",\"sha256\":\"" + manifest.Sha256 + "\"}", "{\"game_dir\":\"" + escapedGame + "\",\"patch_version\":\"2026.09.05.3\",\"sha256\":\"" + manifest.Sha256 + "\"}", "{\"game_dir\":\"other\",\"patch_version\":\"2026.09.05.2\",\"sha256\":\"" + manifest.Sha256 + "\"}", "{\"game_dir\":\"" + escapedGame + "\",\"patch_version\":\"2026.09.05.2\",\"sha256\":\"bad\"}" }; foreach (string text in invalid) { File.WriteAllText(statePath, text); Require(!(bool)method.Invoke(null, new object[] { game, manifest }), "invalid installed_patch state accepted"); Require(File.Exists(source) && File.Exists(old), "invalid state removed game files"); }
        string stateDir = statePath + ".writefailure"; if (Directory.Exists(stateDir)) Directory.Delete(stateDir, true); Directory.CreateDirectory(stateDir); bool failed = false; try { WakfuReleaseUpdater.WriteInstalledPatchState(stateDir, new Dictionary<string, object> { { "patch_version", "2026.09.05.2" } }); } catch (Exception) { failed = true; } finally { try { Directory.Delete(stateDir, true); } catch { } } Require(failed, "state write failure was accepted");
    }

    static void TestRollbackPrimitive(string root) {
        string targetA = Path.Combine(root, "i18n_en.jar"), targetB = Path.Combine(root, "i18n.jar"), sourceA = Path.Combine(root, "new.jar"); File.WriteAllText(targetA, "old-en"); File.WriteAllText(targetB, "old-active"); File.WriteAllText(sourceA, "new"); var method = typeof(WakfuSetupApp).GetMethod("CommitReleaseI18nTransaction", BindingFlags.Static | BindingFlags.NonPublic); Require(method != null, "release transaction method missing"); var staged = new Dictionary<string, string>(); staged.Add(targetA, sourceA); staged.Add(targetB, Path.Combine(root, "missing.jar")); bool failed = false; try { method.Invoke(null, new object[] { staged, Path.Combine(root, "transaction") }); } catch (TargetInvocationException) { failed = true; } Require(failed, "forced release transaction failure did not fail"); Require(File.ReadAllText(targetA) == "old-en", "rollback did not restore i18n_en.jar"); Require(File.ReadAllText(targetB) == "old-active", "rollback changed i18n.jar");
        string lockedA = Path.Combine(root, "locked_en.jar"), lockedB = Path.Combine(root, "locked_active.jar"), newA = Path.Combine(root, "locked_new_en.jar"), newB = Path.Combine(root, "locked_new_active.jar"); File.WriteAllText(lockedA, "old-en"); File.WriteAllText(lockedB, "old-active"); File.WriteAllText(newA, "new-en"); File.WriteAllText(newB, "new-active"); bool replaceFailed = false; using (var fileLock = new FileStream(lockedB, FileMode.Open, FileAccess.Read, FileShare.Read)) { var lockedStage = new Dictionary<string, string>(); lockedStage.Add(lockedA, newA); lockedStage.Add(lockedB, newB); try { method.Invoke(null, new object[] { lockedStage, Path.Combine(root, "locked-transaction") }); } catch (TargetInvocationException) { replaceFailed = true; } } Require(replaceFailed, "second-file replace failure did not fail"); Require(File.ReadAllText(lockedA) == "old-en", "second-file replace rollback did not restore i18n_en.jar"); Require(File.ReadAllText(lockedB) == "old-active", "locked i18n.jar changed");
    }

    static void TestPatchVersions() { Require(PatchVersion.Parse("2026.09.05.9").CompareTo(PatchVersion.Parse("2026.09.05.10")) < 0, "numeric revision comparison failed"); Require(PatchVersion.Parse("2026.09.05.10").CompareTo(PatchVersion.Parse("2026.09.06.1")) < 0, "day comparison failed"); Require(PatchVersion.Parse("2026.09.30.1").CompareTo(PatchVersion.Parse("2026.10.01.1")) < 0, "month comparison failed"); Require(PatchVersion.Parse("2026.09.05.10").CompareTo(PatchVersion.Parse("2026.09.05.10")) == 0, "same version comparison failed"); var compare = typeof(WakfuSetupApp).GetMethod("ComparePatchVersions", BindingFlags.Static | BindingFlags.NonPublic); Require((int)compare.Invoke(null, new object[] { "2026.09.05.2", "2026.09.05.2" }) == 0, "same patch state comparison failed"); Require((int)compare.Invoke(null, new object[] { "2026.09.05.2", "2026.09.05.3" }) < 0, "newer remote state comparison failed"); Require((int)compare.Invoke(null, new object[] { "2026.09.05.3", "2026.09.05.2" }) > 0, "local newer state comparison failed"); foreach (string invalid in new[] { "2026.09.05", "2026.09.05.-1", "2026.09.05.01", "2026.13.01.1", "x" }) try { PatchVersion.Parse(invalid); throw new Exception("malformed patch version accepted: " + invalid); } catch (ReleaseUpdateException) { } }

    [STAThread] static int Main() {
        string root = Path.Combine(Path.GetTempPath(), "WakfuReleaseUpdaterTests_" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root);
        try {
            var tests = new Dictionary<string, Action> { { "contract/hash/allowlist", delegate { TestContractAndHash(root); } }, { "stable Release draft/prerelease filtering", TestStableReleaseFlags }, { "fake Release network E2E", delegate { TestFakeHttpEndToEnd(root); } }, { "HTTP failure matrix", delegate { TestHttpFailureMatrix(root); } }, { "patch version parser", TestPatchVersions }, { "install/backup/state/rollback", delegate { TestInstallAndRollback(root); } }, { "transaction rollback primitive", delegate { TestRollbackPrimitive(root); } } };
            string external = Environment.GetEnvironmentVariable("WAKFU_FULL_SIMULATION_FIXTURE");
            if (!String.IsNullOrWhiteSpace(external)) tests.Add("full simulated external Release -> Setup", delegate { TestExternalFullSimulation(external); });
            foreach (var test in tests) { test.Value(); Console.WriteLine("PASS|" + test.Key); }
            Console.WriteLine("RELEASE_UPDATER_TESTS_OK"); return 0;
        } catch (Exception ex) { Console.WriteLine("FAIL|" + ex.Message); Console.WriteLine(ex.ToString()); return 1; } finally { try { Directory.Delete(root, true); } catch { } }
    }
}

static class ByteArrayExtensions {
    internal static byte[] SubArray(this byte[] source, int index, int length) { var result = new byte[length]; Buffer.BlockCopy(source, index, result, 0, length); return result; }
}
