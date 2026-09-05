using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;
using System.Web.Script.Serialization;

static class WakfuAracLauncher
{
    static string ToolStateRoot { get { string isolated = Environment.GetEnvironmentVariable("WAKFU_TOOL_STATE_ROOT"); return String.IsNullOrWhiteSpace(isolated) ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WakfuTurkceCeviriAraci") : Path.GetFullPath(isolated); } }
    static readonly string[] PreservedRelativeFiles = {
        @"Ayarlar\arayuz_ayarlari.json",
        @"Ayarlar\gpu_runtime_path.txt",
        @"Ayarlar\wakfu_oyun_yolu.txt"
    };
    static readonly string[] UserDataRelativeFiles = {
        @"Ceviri_Verileri\wakfu_tr_ceviri.json",
        @"Ceviri_Verileri\terim_duzeltmeleri.json",
        @"Ceviri_Verileri\manual_repairs_v23.json"
    };

    static bool IsProjectRoot(string root)
    {
        return !String.IsNullOrWhiteSpace(root)
            && File.Exists(Path.Combine(root, "Kaynak_Kodu", "WakfuTurkceCeviri.ps1"))
            && File.Exists(Path.Combine(root, "Ceviri_Verileri", "wakfu_tr_ceviri.json"));
    }

    static bool IsGpuRuntime(string path)
    {
        return !String.IsNullOrWhiteSpace(path)
            && File.Exists(Path.Combine(path, "venv", "Scripts", "python.exe"));
    }

    static string ReadRememberedGpuPath(string projectRoot)
    {
        try {
            string pathFile = Path.Combine(projectRoot, "Ayarlar", "gpu_runtime_path.txt");
            return File.Exists(pathFile) ? File.ReadAllText(pathFile).Trim() : null;
        } catch { return null; }
    }

    static string FindGpuRuntime(string projectRoot)
    {
        string[] candidates = {
            Environment.GetEnvironmentVariable("WAKFU_GPU_RUNTIME"),
            ReadRememberedGpuPath(projectRoot),
            Path.Combine(projectRoot, "GPU")
        };
        foreach (string candidate in candidates)
            if (IsGpuRuntime(candidate)) return candidate;
        return null;
    }

    static bool ShouldPreserve(string relative)
    {
        foreach (string item in PreservedRelativeFiles)
            if (String.Equals(item, relative, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    static bool IsUserData(string relative)
    {
        foreach (string item in UserDataRelativeFiles)
            if (String.Equals(item, relative, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    static string HashFile(string path)
    {
        using (var sha = SHA256.Create()) using (var input = File.OpenRead(path))
            return BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "");
    }

    static Dictionary<string, object> ReadManifest(string root)
    {
        try {
            string path = Path.Combine(root, "Ayarlar", "dagitim_manifest.json");
            if (!File.Exists(path)) return null;
            return new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue }.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8));
        } catch { return null; }
    }

    static string ManifestVersion(Dictionary<string, object> manifest)
    {
        object value; return manifest != null && manifest.TryGetValue("version", out value) ? Convert.ToString(value) : "";
    }

    static void CopyPreservedFiles(string sourceRoot, string destinationRoot)
    {
        foreach (string relative in PreservedRelativeFiles) {
            string source = Path.Combine(sourceRoot, relative); if (!File.Exists(source)) continue;
            string target = Path.Combine(destinationRoot, relative); Directory.CreateDirectory(Path.GetDirectoryName(target)); File.Copy(source, target, true);
        }
    }

    static void CopyUserData(string sourceRoot, string destinationRoot)
    {
        foreach (string relative in UserDataRelativeFiles) {
            string source = Path.Combine(sourceRoot, relative); if (!File.Exists(source)) continue;
            string target = Path.Combine(destinationRoot, relative); Directory.CreateDirectory(Path.GetDirectoryName(target)); File.Copy(source, target, true);
        }
    }

    static void BackupUserData(string sourceRoot, string oldVersion, string newVersion)
    {
        string backupRoot = Path.Combine(ToolStateRoot, "Kullanici_Yedekleri", DateTime.Now.ToString("yyyyMMdd_HHmmss") + "_" + (oldVersion == "" ? "eski" : oldVersion) + "_to_" + newVersion);
        bool copied = false;
        foreach (string relative in UserDataRelativeFiles) {
            string source = Path.Combine(sourceRoot, relative); if (!File.Exists(source)) continue;
            string target = Path.Combine(backupRoot, relative); Directory.CreateDirectory(Path.GetDirectoryName(target)); File.Copy(source, target, true); copied = true;
        }
        if (!copied && Directory.Exists(backupRoot)) Directory.Delete(backupRoot, true);
    }

    static void ValidateExtractedApplication(string root)
    {
        if (!IsProjectRoot(root)) throw new Exception("Ana program dosyaları paketten eksik çıktı.");
        var manifest = ReadManifest(root); if (manifest == null) throw new Exception("Dağıtım sürüm bilgisi bulunamadı.");
        object rawFiles; if (!manifest.TryGetValue("files", out rawFiles)) throw new Exception("Dağıtım doğrulama listesi bulunamadı.");
        var files = rawFiles as Dictionary<string, object>; if (files == null) throw new Exception("Dağıtım doğrulama listesi okunamadı.");
        string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        foreach (var pair in files) {
            string relative = pair.Key.Replace('/', '\\'); if (ShouldPreserve(relative) || IsUserData(relative)) continue;
            string target = Path.GetFullPath(Path.Combine(root, pair.Key.Replace('/', '\\')));
            if (!target.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) || !File.Exists(target) || !String.Equals(HashFile(target), Convert.ToString(pair.Value), StringComparison.OrdinalIgnoreCase))
                throw new Exception("Dağıtım bileşeni doğrulanamadı: " + pair.Key);
        }
    }

    static void ExtractEmbeddedApplication(string destination)
    {
        string parent = Path.GetDirectoryName(destination); Directory.CreateDirectory(parent);
        string stage = destination + ".stage_" + Guid.NewGuid().ToString("N"), rollback = destination + ".rollback_" + Guid.NewGuid().ToString("N");
        try {
            Directory.CreateDirectory(stage); string stagePrefix = Path.GetFullPath(stage).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            using (Stream packed = Assembly.GetExecutingAssembly().GetManifestResourceStream("WakfuTool.app.zip")) {
                if (packed == null) throw new Exception("Gömülü program paketi bulunamadı.");
                using (var zip = new ZipArchive(packed, ZipArchiveMode.Read)) foreach (ZipArchiveEntry entry in zip.Entries) {
                    string relative = entry.FullName.Replace('/', '\\').TrimStart('\\'); if (String.IsNullOrWhiteSpace(relative)) continue;
                    string target = Path.GetFullPath(Path.Combine(stage, relative)); if (!target.StartsWith(stagePrefix, StringComparison.OrdinalIgnoreCase)) throw new Exception("Geçersiz paket yolu algılandı.");
                    if (relative.EndsWith("\\")) { Directory.CreateDirectory(target); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(target)); using (Stream input = entry.Open()) using (FileStream output = new FileStream(target, FileMode.Create, FileAccess.Write, FileShare.None)) input.CopyTo(output);
                }
            }
            var newManifest = ReadManifest(stage); string newVersion = ManifestVersion(newManifest); if (newVersion == "") throw new Exception("Yeni program sürümü okunamadı.");
            var oldManifest = Directory.Exists(destination) ? ReadManifest(destination) : null; string oldVersion = ManifestVersion(oldManifest);
            if (Directory.Exists(destination)) { CopyPreservedFiles(destination, stage); if (String.Equals(oldVersion, newVersion, StringComparison.OrdinalIgnoreCase)) CopyUserData(destination, stage); else BackupUserData(destination, oldVersion, newVersion); }
            ValidateExtractedApplication(stage);
            if (Directory.Exists(destination)) Directory.Move(destination, rollback); Directory.Move(stage, destination); try { if (Directory.Exists(rollback)) Directory.Delete(rollback, true); } catch { }
        } catch {
            try { if (!Directory.Exists(destination) && Directory.Exists(rollback)) Directory.Move(rollback, destination); } catch { }
            try { if (Directory.Exists(stage)) Directory.Delete(stage, true); } catch { }
            throw;
        }
    }

    [STAThread]
    static void Main()
    {
        try {
            string exeDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string projectRoot = exeDir;
            if (!IsProjectRoot(projectRoot)) {
                projectRoot = Path.Combine(ToolStateRoot, "App");
                var currentManifest = ReadManifest(projectRoot);
                string embeddedVersion = "";
                using (Stream packed = Assembly.GetExecutingAssembly().GetManifestResourceStream("WakfuTool.app.zip")) using (var zip = new ZipArchive(packed, ZipArchiveMode.Read)) {
                    var entry = zip.GetEntry("Ayarlar/dagitim_manifest.json") ?? zip.GetEntry(@"Ayarlar\dagitim_manifest.json"); if (entry != null) using (var reader = new StreamReader(entry.Open(), Encoding.UTF8, true)) { var m = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(reader.ReadToEnd()); embeddedVersion = ManifestVersion(m); }
                }
                bool currentReady = IsProjectRoot(projectRoot) && embeddedVersion != "" && String.Equals(ManifestVersion(currentManifest), embeddedVersion, StringComparison.OrdinalIgnoreCase);
                if (currentReady) try { ValidateExtractedApplication(projectRoot); } catch { currentReady = false; }
                if (!currentReady) ExtractEmbeddedApplication(projectRoot);
            }
            if (!IsProjectRoot(projectRoot))
                throw new Exception("Ana program dosyaları hazırlanamadı.");

            string script = Path.Combine(projectRoot, "Kaynak_Kodu", "WakfuTurkceCeviri.ps1");
            var start = new ProcessStartInfo(
                "powershell.exe",
                "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" + script + "\"") {
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                WorkingDirectory = Path.Combine(projectRoot, "Kaynak_Kodu")
            };
            start.EnvironmentVariables["WAKFU_PROJECT_ROOT"] = projectRoot;
            start.EnvironmentVariables["WAKFU_EXE_DIR"] = exeDir;
            string gpu = FindGpuRuntime(projectRoot);
            if (gpu != null) start.EnvironmentVariables["WAKFU_GPU_RUNTIME"] = gpu;
            Process.Start(start);
        } catch (Exception ex) {
            MessageBox.Show(ex.Message, "Wakfu Türkçe Çeviri Aracı",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
