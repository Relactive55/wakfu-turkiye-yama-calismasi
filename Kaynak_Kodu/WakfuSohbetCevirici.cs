using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("Wakfu Sohbet Çeviricisi")]
[assembly: AssemblyDescription("WAKFU sohbet günlüğünü isteğe bağlı olarak Türkçeye çeviren yardımcı uygulama")]
[assembly: AssemblyCompany("Wakfu Türkçe Yama Topluluğu")]
[assembly: AssemblyProduct("Wakfu Türkçe Yama")]
[assembly: AssemblyCopyright("Copyright © 2026 Wakfu Türkçe Yama Topluluğu")]
[assembly: AssemblyVersion("6.4.0.0")]
[assembly: AssemblyFileVersion("6.4.0.0")]
[assembly: AssemblyInformationalVersion("Wakfu Türkçe Yama")]

static class WakfuSohbetCeviriciProgram {
    static System.Threading.Mutex singleton;
    [STAThread]
    static void Main(string[] args) {
        if (args != null && args.Length == 1 && args[0].StartsWith("--trade-self-test=", StringComparison.OrdinalIgnoreCase)) {
            string outputPath = args[0].Substring("--trade-self-test=".Length).Trim('"');
            try {
                string translated = TranslatorOverlay.RequestDisplayTranslation("WTB Steadfast II or Aquatic Hooks x(any quantity) offer").GetAwaiter().GetResult();
                if (translated.IndexOf("Steadfast II", StringComparison.Ordinal) < 0 || translated.IndexOf("Aquatic Hooks", StringComparison.Ordinal) < 0 || !translated.EndsWith("almak istiyor (WTB)", StringComparison.Ordinal)) throw new InvalidDataException("Çevrimiçi ticaret iletisi biçimi korunamadı.");
                File.WriteAllText(outputPath, "OK|" + translated, new UTF8Encoding(false));
            } catch (Exception ex) {
                File.WriteAllText(outputPath, "ERROR|" + ex.GetType().Name + "|" + ex.Message, new UTF8Encoding(false));
                Environment.ExitCode = 4;
            }
            return;
        }
        if (args != null && args.Length == 1 && args[0].StartsWith("--offline-test=", StringComparison.OrdinalIgnoreCase)) {
            string outputPath = args[0].Substring("--offline-test=".Length).Trim('"');
            try {
                File.WriteAllText(outputPath, "OK|" + TranslatorOverlay.RunOfflineTests(), new UTF8Encoding(false));
            } catch (Exception ex) {
                File.WriteAllText(outputPath, "ERROR|" + ex.GetType().Name + "|" + ex.Message, new UTF8Encoding(false));
                Environment.ExitCode = 3;
            }
            return;
        }
        if (args != null && args.Length == 1 && args[0].StartsWith("--self-test=", StringComparison.OrdinalIgnoreCase)) {
            string outputPath = args[0].Substring("--self-test=".Length).Trim('"');
            try {
                string translated = TranslatorOverlay.RequestTranslation("Hello, where is the market?").GetAwaiter().GetResult();
                File.WriteAllText(outputPath, "OK|" + translated, new UTF8Encoding(false));
            } catch (Exception ex) {
                File.WriteAllText(outputPath, "ERROR|" + ex.GetType().Name + "|" + ex.Message, new UTF8Encoding(false));
                Environment.ExitCode = 2;
            }
            return;
        }
        bool created;
        singleton = new System.Threading.Mutex(true, @"Local\WakfuTurkceSohbetCeviricisi", out created);
        if (!created) { singleton.Dispose(); return; }
        try {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new TranslatorOverlay());
        } finally {
            try { singleton.ReleaseMutex(); } catch { }
            singleton.Dispose();
        }
    }
}

sealed class TranslatorSettings {
    public string ProtectedApiKey { get; set; }
    public string LogPath { get; set; }
    public int OffsetX { get; set; }
    public int OffsetY { get; set; }
    public bool PositionSaved { get; set; }
    public bool PrivacyAccepted { get; set; }
    public bool Enabled { get; set; }
}

sealed class ChatMessage {
    public int id { get; set; }
    public string channel { get; set; }
    public string sender { get; set; }
    public string text { get; set; }
}

sealed class ProtectedChatItem {
    public string Token { get; set; }
    public string CanonicalName { get; set; }
}

sealed class PreparedChatText {
    public string Text { get; set; }
    public string TradeCode { get; set; }
    public List<ProtectedChatItem> Items { get; set; }
}

sealed class ItemNameCatalog {
    sealed class ItemSpan {
        public int Start;
        public int Length;
        public string Name;
    }

    static readonly Regex TradePrefix = new Regex(@"^\s*(?<code>WTS|WTB)\b[\s:;,\-]*(?<body>.*)$", RegexOptions.IgnoreCase | RegexOptions.Compiled | RegexOptions.CultureInvariant);
    readonly Dictionary<char, List<string>> byFirst = new Dictionary<char, List<string>>();
    public int Count { get; private set; }

    public static ItemNameCatalog Load() {
        var catalog = new ItemNameCatalog();
        Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("WakfuChat.item_names.txt");
        if (stream == null) return catalog;
        var unique = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using (stream)
        using (var reader = new StreamReader(stream, Encoding.UTF8, true)) {
            string line;
            while ((line = reader.ReadLine()) != null) {
                string name = line.Trim();
                if (name.Length < 2 || !unique.Add(name)) continue;
                char first = Char.ToUpperInvariant(name[0]);
                List<string> names;
                if (!catalog.byFirst.TryGetValue(first, out names)) {
                    names = new List<string>();
                    catalog.byFirst[first] = names;
                }
                names.Add(name);
            }
        }
        foreach (List<string> names in catalog.byFirst.Values) {
            names.Sort(delegate(string left, string right) {
                int lengthOrder = right.Length.CompareTo(left.Length);
                return lengthOrder != 0 ? lengthOrder : StringComparer.OrdinalIgnoreCase.Compare(left, right);
            });
            catalog.Count += names.Count;
        }
        return catalog;
    }

    static bool IsNameCharacter(char value) { return Char.IsLetterOrDigit(value); }

    static string CreateToken(int index) {
        char[] code = new char[4];
        int value = index;
        for (int i = code.Length - 1; i >= 0; i--) { code[i] = (char)('A' + (value % 26)); value /= 26; }
        return "ZXQWKFP" + new string(code) + "QXZ";
    }

    public PreparedChatText Prepare(string original) {
        string body = original == null ? "" : original.Trim();
        string tradeCode = "";
        Match trade = TradePrefix.Match(body);
        if (trade.Success) {
            tradeCode = trade.Groups["code"].Value.ToUpperInvariant();
            body = trade.Groups["body"].Value.Trim();
        }
        var spans = new List<ItemSpan>();
        int position = 0;
        while (position < body.Length) {
            if (position > 0 && IsNameCharacter(body[position - 1])) { position++; continue; }
            List<string> candidates;
            if (!byFirst.TryGetValue(Char.ToUpperInvariant(body[position]), out candidates)) { position++; continue; }
            string found = null;
            foreach (string candidate in candidates) {
                if (position + candidate.Length > body.Length) continue;
                if (String.Compare(body, position, candidate, 0, candidate.Length, StringComparison.OrdinalIgnoreCase) != 0) continue;
                int after = position + candidate.Length;
                if (after < body.Length && IsNameCharacter(body[after])) continue;
                found = candidate;
                break;
            }
            if (found == null) { position++; continue; }
            spans.Add(new ItemSpan { Start = position, Length = found.Length, Name = found });
            position += found.Length;
        }
        var protectedItems = new List<ProtectedChatItem>();
        if (spans.Count == 0) return new PreparedChatText { Text = body, TradeCode = tradeCode, Items = protectedItems };
        var prepared = new StringBuilder(body.Length + spans.Count * 12);
        int cursor = 0;
        foreach (ItemSpan span in spans) {
            prepared.Append(body, cursor, span.Start - cursor);
            string token = CreateToken(protectedItems.Count);
            prepared.Append(token);
            protectedItems.Add(new ProtectedChatItem { Token = token, CanonicalName = span.Name });
            cursor = span.Start + span.Length;
        }
        prepared.Append(body, cursor, body.Length - cursor);
        return new PreparedChatText { Text = prepared.ToString(), TradeCode = tradeCode, Items = protectedItems };
    }

    public string Restore(PreparedChatText prepared, string translated) {
        string result = translated ?? "";
        foreach (ProtectedChatItem item in prepared.Items) {
            result = Regex.Replace(result, Regex.Escape(item.Token), delegate { return item.CanonicalName; }, RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        }
        return result;
    }
}

sealed class TranslatorOverlay : Form {
    const int WmNclButtonDown = 0xA1;
    const int HtCaption = 0x2;
    const int SwRestore = 9;
    const string PrimaryApi = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=tr&q=";
    const string SecondaryApi = "https://translate.google.com/translate_a/single?client=at&dt=t&dj=1&sl=auto&tl=tr&q=";
    static readonly Regex ChatLine = new Regex(@"^\d{2}:\d{2}:\d{2},\d{3}\s+-\s+\[(?<channel>[^\]]+)\]\s+(?<sender>[^:]{1,80})\s+:\s+(?<text>.+)$", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
    static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
    static readonly ItemNameCatalog ItemNames = ItemNameCatalog.Load();

    static TranslatorOverlay() {
        Http.DefaultRequestHeaders.TryAddWithoutValidation("User-Agent", "WakfuTurkceSohbet/2.1");
        Http.DefaultRequestHeaders.TryAddWithoutValidation("Accept-Language", "tr-TR,tr;q=0.9,en;q=0.8");
    }

    readonly CheckBox toggle = new CheckBox();
    readonly Button settingsButton = new Button();
    readonly Label status = new Label();
    readonly RichTextBox output = new RichTextBox();
    readonly Panel bar = new Panel();
    readonly Timer windowTimer = new Timer();
    readonly Timer logTimer = new Timer();
    readonly Timer translationTimer = new Timer();
    readonly Queue<ChatMessage> pending = new Queue<ChatMessage>();
    readonly Dictionary<string, string> cache = new Dictionary<string, string>(StringComparer.Ordinal);
    readonly NotifyIcon tray = new NotifyIcon();
    int gameProcessId;
    readonly string settingsDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WakfuTurkceYama");
    TranslatorSettings options;
    string settingsPath;
    string activeLogPath;
    long logPosition = -1;
    IntPtr gameWindow = IntPtr.Zero;
    Rectangle lastGameRect = Rectangle.Empty;
    bool moving;
    bool busy;
    bool exiting;
    int nextMessageId = 1;
    DateTime retryAfterUtc = DateTime.MinValue;

    public TranslatorOverlay() {
        settingsPath = Path.Combine(settingsDir, "sohbet_cevirici.json");
        options = LoadSettings();
        Text = "Wakfu Otomatik Sohbet Çevirisi";
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        TopMost = true;
        ShowInTaskbar = false;
        BackColor = Color.FromArgb(18, 22, 26);
        ForeColor = Color.WhiteSmoke;
        Opacity = 0.91;
        ClientSize = new Size(600, 178);
        MinimumSize = new Size(330, 34);
        MaximumSize = new Size(900, 360);

        output.Dock = DockStyle.Fill;
        output.ReadOnly = true;
        output.BorderStyle = BorderStyle.None;
        output.BackColor = Color.FromArgb(18, 22, 26);
        output.ForeColor = Color.FromArgb(232, 236, 239);
        output.Font = new Font("Segoe UI", 9.5f);
        output.DetectUrls = false;
        output.ScrollBars = RichTextBoxScrollBars.Vertical;

        status.Dock = DockStyle.Top;
        status.Height = 22;
        status.Padding = new Padding(8, 3, 4, 0);
        status.ForeColor = Color.FromArgb(118, 214, 209);
        status.Text = "WAKFU bekleniyor…";

        bar.Dock = DockStyle.Bottom;
        bar.Height = 34;
        bar.BackColor = Color.FromArgb(28, 34, 39);
        toggle.Text = "Otomatik sohbet çevirisi";
        toggle.ForeColor = Color.White;
        toggle.AutoSize = false;
        toggle.SetBounds(10, 5, 225, 24);
        toggle.Checked = options.Enabled;
        settingsButton.Text = "Ayar";
        settingsButton.FlatStyle = FlatStyle.Flat;
        settingsButton.FlatAppearance.BorderColor = Color.FromArgb(90, 110, 120);
        settingsButton.ForeColor = Color.WhiteSmoke;
        settingsButton.SetBounds(510, 3, 78, 27);
        settingsButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        bar.Controls.Add(toggle);
        bar.Controls.Add(settingsButton);
        Controls.Add(output);
        Controls.Add(status);
        Controls.Add(bar);

        toggle.CheckedChanged += ToggleChanged;
        settingsButton.Click += delegate { ShowSettingsDialog(); };
        bar.MouseDown += BeginDrag;
        status.MouseDown += BeginDrag;
        bar.MouseUp += EndDrag;
        status.MouseUp += EndDrag;

        windowTimer.Interval = 500;
        windowTimer.Tick += delegate { FollowGameWindow(); };
        logTimer.Interval = 750;
        logTimer.Tick += delegate { PollLog(); };
        translationTimer.Interval = 1800;
        translationTimer.Tick += async delegate { await TranslatePending(); };
        windowTimer.Start();
        logTimer.Start();
        translationTimer.Start();

        var menu = new ContextMenuStrip();
        menu.Items.Add("Çeviriyi aç / kapat", null, delegate { toggle.Checked = !toggle.Checked; });
        menu.Items.Add("Çeviri ve konum ayarları", null, delegate { ShowSettingsDialog(); });
        menu.Items.Add("Sohbet günlüğünü seç", null, delegate { SelectLogFile(); });
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Çıkış", null, delegate { exiting = true; tray.Visible = false; Close(); });
        tray.Text = "Wakfu Otomatik Sohbet Çevirisi";
        tray.Icon = SystemIcons.Information;
        tray.ContextMenuStrip = menu;
        tray.Visible = true;
        tray.DoubleClick += delegate { toggle.Checked = !toggle.Checked; };

        Resize += delegate { if (WindowState == FormWindowState.Minimized) Hide(); };
        FormClosing += delegate(object sender, FormClosingEventArgs e) {
            if (!exiting) { e.Cancel = true; Hide(); }
            else {
                SaveSettings();
                windowTimer.Stop(); logTimer.Stop(); translationTimer.Stop();
                windowTimer.Dispose(); logTimer.Dispose(); translationTimer.Dispose();
                ContextMenuStrip trayMenu = tray.ContextMenuStrip;
                tray.Dispose();
                if (trayMenu != null) trayMenu.Dispose();
                Http.Dispose();
            }
        };
        ApplyEnabledVisualState();
    }

    static string FinalizePreparedTranslation(PreparedChatText prepared, string serviceText) {
        string translated = ItemNames.Restore(prepared, serviceText).Trim();
        if (prepared.TradeCode == "WTS") return (translated.Length == 0 ? "" : translated + " ") + "satmak istiyor (WTS)";
        if (prepared.TradeCode == "WTB") return (translated.Length == 0 ? "" : translated + " ") + "almak istiyor (WTB)";
        return translated;
    }

    internal static string RunOfflineTests() {
        if (ItemNames.Count < 10000) throw new InvalidDataException("Gömülü WAKFU eşya adları listesi eksik.");
        PreparedChatText buy = ItemNames.Prepare("WTB Steadfast II or Aquatic Hooks x(any quantity) offer");
        if (buy.Items.Count != 2 || buy.Text.IndexOf("Steadfast II", StringComparison.OrdinalIgnoreCase) >= 0 || buy.Text.IndexOf("Aquatic Hooks", StringComparison.OrdinalIgnoreCase) >= 0) throw new InvalidDataException("WTB eşya adları korunamadı.");
        string buyResult = FinalizePreparedTranslation(buy, buy.Text.Replace(" or ", " veya ").Replace("any quantity", "herhangi bir miktar"));
        if (buyResult.IndexOf("Steadfast II", StringComparison.Ordinal) < 0 || buyResult.IndexOf("Aquatic Hooks", StringComparison.Ordinal) < 0 || !buyResult.EndsWith("almak istiyor (WTB)", StringComparison.Ordinal)) throw new InvalidDataException("WTB biçimi doğrulanamadı.");
        PreparedChatText sell = ItemNames.Prepare("WTS Devastate III");
        string sellResult = FinalizePreparedTranslation(sell, sell.Text);
        if (!String.Equals(sellResult, "Devastate III satmak istiyor (WTS)", StringComparison.Ordinal)) throw new InvalidDataException("WTS biçimi doğrulanamadı.");
        PreparedChatText stone = ItemNames.Prepare("wts Ultimate Stone 5M5");
        string stoneResult = FinalizePreparedTranslation(stone, stone.Text);
        if (!String.Equals(stoneResult, "Ultimate Stone 5M5 satmak istiyor (WTS)", StringComparison.Ordinal)) throw new InvalidDataException("Eşya adı ve fiyat eki korunamadı.");
        return "ITEMS=" + ItemNames.Count + "|WTB=OK|WTS=OK|NAMES=OK";
    }

    protected override bool ShowWithoutActivation { get { return true; } }
    protected override CreateParams CreateParams {
        get { var cp = base.CreateParams; cp.ExStyle |= 0x00000080; return cp; }
    }

    void BeginDrag(object sender, MouseEventArgs e) {
        if (e.Button != MouseButtons.Left) return;
        moving = true;
        ReleaseCapture();
        SendMessage(Handle, WmNclButtonDown, HtCaption, 0);
    }

    void EndDrag(object sender, MouseEventArgs e) { SaveRelativePosition(); }

    void SaveRelativePosition() {
        moving = false;
        if (lastGameRect == Rectangle.Empty) return;
        options.OffsetX = Left - lastGameRect.Left;
        options.OffsetY = Top - lastGameRect.Top;
        options.PositionSaved = true;
        SaveSettings();
    }

    void ToggleChanged(object sender, EventArgs e) {
        if (toggle.Checked) {
            if (!EnsurePrivacyConsent()) {
                toggle.CheckedChanged -= ToggleChanged;
                toggle.Checked = false;
                toggle.CheckedChanged += ToggleChanged;
            }
        }
        options.Enabled = toggle.Checked;
        SaveSettings();
        ApplyEnabledVisualState();
    }

    void ApplyEnabledVisualState() {
        if (toggle.Checked) {
            if (Height < 100) Height = 178;
            output.Visible = true;
            status.Visible = true;
            status.Text = String.IsNullOrWhiteSpace(activeLogPath) ? "Sohbet günlüğü aranıyor…" : "Anahtarsız çeviri hazır";
        } else {
            output.Visible = false;
            status.Visible = false;
            Height = 34;
        }
    }

    bool EnsurePrivacyConsent() {
        if (options.PrivacyAccepted) return true;
        string message = "Etkinleştirdiğinizde yeni oyuncu sohbetleri Türkçeye çevrilmek üzere Google Çeviri'ye gönderilir. Birincil bağlantı kullanılamazsa ücretsiz yedek çeviri bağlantısı denenebilir.\n\nAPI anahtarı gerekmez. Eski sohbet geçmişi gönderilmez.\n\nDevam etmek istiyor musunuz?";
        if (MessageBox.Show(message, "Sohbet verisi ve gizlilik", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return false;
        options.PrivacyAccepted = true;
        SaveSettings();
        return true;
    }

    void ShowSettingsDialog() {
        using (var dialog = new Form()) {
            dialog.Text = "Wakfu Sohbet Çeviricisi Ayarları";
            dialog.StartPosition = FormStartPosition.CenterScreen;
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog;
            dialog.MaximizeBox = false;
            dialog.MinimizeBox = false;
            dialog.ClientSize = new Size(540, 205);
            dialog.Font = new Font("Segoe UI", 9.5f);
            var info = new Label { Text = "Çeviri ücretsiz ve anahtarsız çalışır. WAKFU eşya adları özgün bırakılır; WTS ve WTB iletilerinin alım-satım amacı Türkçe gösterilir.", AutoSize = false };
            info.SetBounds(18, 15, 500, 45);
            var choose = new Button { Text = "Sohbet Günlüğünü Seç" };
            choose.SetBounds(18, 78, 190, 34);
            choose.Click += delegate { SelectLogFile(); };
            var reset = new Button { Text = "Konumu Sıfırla" };
            reset.SetBounds(218, 78, 135, 34);
            reset.Click += delegate { options.PositionSaved = false; SaveSettings(); };
            var save = new Button { Text = "Kaydet", DialogResult = DialogResult.OK };
            save.SetBounds(365, 78, 73, 34);
            var cancel = new Button { Text = "İptal", DialogResult = DialogResult.Cancel };
            cancel.SetBounds(445, 78, 73, 34);
            var privacy = new Label { Text = "Not: Çeviri yalnız kutu açıkken çalışır; eski sohbet geçmişi gönderilmez.", ForeColor = Color.DimGray, AutoSize = true };
            privacy.SetBounds(18, 137, 500, 24);
            dialog.Controls.AddRange(new Control[] { info, choose, reset, save, cancel, privacy });
            dialog.AcceptButton = save;
            dialog.CancelButton = cancel;
            if (dialog.ShowDialog() == DialogResult.OK) {
                SaveSettings();
                status.Text = "Anahtarsız çeviri hazır";
            }
        }
    }

    void SelectLogFile() {
        using (var picker = new OpenFileDialog()) {
            picker.Title = "WAKFU sohbet günlüğünü seçin";
            picker.Filter = "WAKFU sohbet günlüğü (wakfu_chat.log)|wakfu_chat.log|Günlük dosyaları (*.log)|*.log";
            if (!String.IsNullOrWhiteSpace(activeLogPath)) picker.InitialDirectory = Path.GetDirectoryName(activeLogPath);
            if (picker.ShowDialog() != DialogResult.OK) return;
            options.LogPath = picker.FileName;
            activeLogPath = picker.FileName;
            logPosition = -1;
            SaveSettings();
        }
    }

    void FollowGameWindow() {
        IntPtr found = FindWakfuWindow();
        if (found == IntPtr.Zero) {
            gameWindow = IntPtr.Zero;
            if (Visible) Hide();
            return;
        }
        gameWindow = found;
        RECT native;
        if (!GetWindowRect(found, out native)) return;
        Rectangle rect = Rectangle.FromLTRB(native.Left, native.Top, native.Right, native.Bottom);
        if (rect.Width < 500 || rect.Height < 400) return;
        lastGameRect = rect;
        if (!moving) {
            int x = options.PositionSaved ? rect.Left + options.OffsetX : rect.Left + 18;
            int y = options.PositionSaved ? rect.Top + options.OffsetY : rect.Bottom - Height - 118;
            Location = ClampToScreen(new Point(x, y));
        }
        IntPtr foreground = GetForegroundWindow();
        bool shouldShow = foreground == found || foreground == Handle || IsOwnedDialogForeground(foreground);
        if (shouldShow && !Visible) Show();
        else if (!shouldShow && Visible) Hide();
        if (String.IsNullOrWhiteSpace(activeLogPath) || !File.Exists(activeLogPath)) {
            activeLogPath = FindLogForWindow(found);
            if (!String.IsNullOrWhiteSpace(activeLogPath)) { options.LogPath = activeLogPath; logPosition = -1; SaveSettings(); }
        }
    }

    bool IsOwnedDialogForeground(IntPtr foreground) {
        if (foreground == IntPtr.Zero) return false;
        foreach (Form form in Application.OpenForms) if (form.Visible && form.Handle == foreground) return true;
        return false;
    }

    Point ClampToScreen(Point point) {
        Rectangle area = Screen.FromPoint(point).WorkingArea;
        int x = Math.Max(area.Left, Math.Min(point.X, area.Right - Width));
        int y = Math.Max(area.Top, Math.Min(point.Y, area.Bottom - Height));
        return new Point(x, y);
    }

    void PollLog() {
        if (!toggle.Checked) return;
        if (String.IsNullOrWhiteSpace(activeLogPath) || !File.Exists(activeLogPath)) return;
        try {
            using (var stream = new FileStream(activeLogPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete)) {
                if (logPosition < 0) { logPosition = stream.Length; return; }
                if (stream.Length < logPosition) logPosition = 0;
                if (stream.Length == logPosition) return;
                stream.Position = logPosition;
                using (var reader = new StreamReader(stream, new UTF8Encoding(false, false), true, 4096, true)) {
                    string line;
                    while ((line = reader.ReadLine()) != null) {
                        Match match = ChatLine.Match(line);
                        if (!match.Success) continue;
                        string message = match.Groups["text"].Value.Trim();
                        if (!ShouldTranslate(message)) continue;
                        while (pending.Count >= 100) pending.Dequeue();
                        pending.Enqueue(new ChatMessage { id = nextMessageId++, channel = match.Groups["channel"].Value.Trim(), sender = match.Groups["sender"].Value.Trim(), text = message });
                    }
                    logPosition = stream.Position;
                }
            }
        } catch (IOException) { }
        catch (UnauthorizedAccessException) { status.Text = "Sohbet günlüğü okunamadı"; }
    }

    bool ShouldTranslate(string text) {
        if (String.IsNullOrWhiteSpace(text) || text.Length < 2) return false;
        if (text.Length > 600) return true;
        return Regex.IsMatch(text, @"[A-Za-zÀ-ÿА-Яа-я]", RegexOptions.CultureInvariant);
    }

    async Task TranslatePending() {
        if (!toggle.Checked || busy || pending.Count == 0 || DateTime.UtcNow < retryAfterUtc) return;
        var batch = new List<ChatMessage>();
        while (pending.Count > 0 && batch.Count < 3) {
            ChatMessage message = pending.Dequeue();
            string known;
            if (cache.TryGetValue(message.text, out known)) {
                if (!String.IsNullOrWhiteSpace(known)) AppendTranslation(message, known);
            } else batch.Add(message);
        }
        if (batch.Count == 0) return;
        busy = true;
        status.Text = "Sohbet Türkçeye çevriliyor…";
        int completed = 0;
        int failed = 0;
        bool limited = false;
        try {
            foreach (ChatMessage message in batch) {
                try {
                    PreparedChatText prepared = ItemNames.Prepare(message.text);
                    string serviceText = String.IsNullOrWhiteSpace(prepared.Text) ? "" : (await RequestTranslation(prepared.Text) ?? "").Trim();
                    string translated = FinalizePreparedTranslation(prepared, serviceText);
                    completed++;
                    if (String.IsNullOrWhiteSpace(prepared.TradeCode) && String.Equals(translated, message.text, StringComparison.CurrentCultureIgnoreCase)) translated = "";
                    cache[message.text] = translated;
                    if (!String.IsNullOrWhiteSpace(translated)) AppendTranslation(message, translated);
                } catch (HttpRequestException ex) {
                    failed++;
                    limited = limited || ex.Message.IndexOf("429", StringComparison.OrdinalIgnoreCase) >= 0;
                    while (pending.Count >= 100) pending.Dequeue();
                    pending.Enqueue(message);
                    WriteDiagnostic(ex);
                }
                if (completed + failed < batch.Count) await Task.Delay(350);
            }
            if (cache.Count > 1000) cache.Clear();
            if (failed == 0) {
                retryAfterUtc = DateTime.MinValue;
                status.Text = "Anahtarsız çeviri hazır • son çeviri " + DateTime.Now.ToString("HH:mm:ss");
            } else if (completed > 0) {
                retryAfterUtc = DateTime.UtcNow.AddSeconds(8);
                status.Text = "Bazı iletiler bekliyor; 8 saniye sonra yeniden denenecek";
            } else {
                retryAfterUtc = DateTime.UtcNow.AddSeconds(limited ? 45 : 15);
                status.Text = limited ? "Çeviri hizmeti yoğun; 45 saniye sonra yeniden denenecek" : "Çeviri bağlantısı kurulamadı; 15 saniye sonra yeniden denenecek";
            }
        } catch (Exception ex) {
            foreach (ChatMessage message in batch) {
                if (cache.ContainsKey(message.text)) continue;
                while (pending.Count >= 100) pending.Dequeue();
                pending.Enqueue(message);
            }
            WriteDiagnostic(ex);
            status.Text = "Çeviri hatası: " + ShortError(ex.Message);
        } finally { busy = false; }
    }

    internal static async Task<string> RequestTranslation(string text) {
        string encoded = Uri.EscapeDataString(text);
        Exception firstError = null;
        try {
            string translated = ParseCompactGoogleResponse(await DownloadString(PrimaryApi + encoded));
            if (!String.IsNullOrWhiteSpace(translated)) return translated;
            throw new InvalidDataException("Birincil çeviri bağlantısı boş yanıt verdi.");
        } catch (Exception ex) { firstError = ex; }
        Exception secondError = null;
        try {
            string translated = ParseDetailedGoogleResponse(await DownloadString(SecondaryApi + encoded));
            if (!String.IsNullOrWhiteSpace(translated)) return translated;
            throw new InvalidDataException("İkinci çeviri bağlantısı boş yanıt verdi.");
        } catch (Exception ex) { secondError = ex; }
        try {
            string source = GuessSourceLanguage(text);
            string fallback = "https://api.mymemory.translated.net/get?q=" + encoded + "&langpair=" + source + "%7Ctr";
            string translated = ParseMyMemoryResponse(await DownloadString(fallback));
            if (!String.IsNullOrWhiteSpace(translated)) return translated;
            throw new InvalidDataException("Yedek çeviri bağlantısı boş yanıt verdi.");
        } catch (Exception thirdError) {
            string message = ShortError(firstError == null ? "" : firstError.Message) + " | " + ShortError(secondError == null ? "" : secondError.Message) + " | " + ShortError(thirdError.Message);
            throw new HttpRequestException(message, thirdError);
        }
    }

    internal static async Task<string> RequestDisplayTranslation(string text) {
        PreparedChatText prepared = ItemNames.Prepare(text);
        string serviceText = String.IsNullOrWhiteSpace(prepared.Text) ? "" : (await RequestTranslation(prepared.Text) ?? "").Trim();
        return FinalizePreparedTranslation(prepared, serviceText);
    }

    static async Task<string> DownloadString(string url) {
        using (var timeout = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(8)))
        using (HttpResponseMessage response = await Http.GetAsync(url, HttpCompletionOption.ResponseContentRead, timeout.Token)) {
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStringAsync();
        }
    }

    static string ParseCompactGoogleResponse(string response) {
        object[] root = Json.DeserializeObject(response) as object[];
        if (root == null || root.Length == 0) return "";
        object[] pair = root[0] as object[];
        return pair == null || pair.Length == 0 ? "" : Convert.ToString(pair[0]);
    }

    static string ParseDetailedGoogleResponse(string response) {
        var root = Json.DeserializeObject(response) as Dictionary<string, object>;
        if (root == null || !root.ContainsKey("sentences")) return "";
        object[] sentences = root["sentences"] as object[];
        if (sentences == null) return "";
        var result = new StringBuilder();
        foreach (object item in sentences) {
            var sentence = item as Dictionary<string, object>;
            if (sentence != null && sentence.ContainsKey("trans")) result.Append(Convert.ToString(sentence["trans"]));
        }
        return result.ToString();
    }

    static string ParseMyMemoryResponse(string response) {
        var root = Json.DeserializeObject(response) as Dictionary<string, object>;
        if (root == null || !root.ContainsKey("responseData")) return "";
        var data = root["responseData"] as Dictionary<string, object>;
        if (data == null || !data.ContainsKey("translatedText")) return "";
        return WebUtility.HtmlDecode(Convert.ToString(data["translatedText"]));
    }

    static string GuessSourceLanguage(string text) {
        if (Regex.IsMatch(text, @"[А-Яа-я]", RegexOptions.CultureInvariant)) return "ru";
        if (Regex.IsMatch(text, @"\b(je|tu|vous|nous|les|des|une|est|sont|pas|pour|avec|dans|sur|que|qui|votre|guilde|quête|joueur|amis|pensez|faire|permet)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)) return "fr";
        if (Regex.IsMatch(text, @"\b(el|la|los|las|una|es|son|para|con|que|por|donde|gracias|amigos)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)) return "es";
        if (Regex.IsMatch(text, @"\b(der|die|das|und|ist|sind|für|mit|nicht|wo|danke)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)) return "de";
        if (Regex.IsMatch(text, @"\b(os|uma|não|para|com|onde|obrigado|amigos)\b", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)) return "pt";
        return "en";
    }

    void WriteDiagnostic(Exception ex) {
        try {
            Directory.CreateDirectory(settingsDir);
            File.AppendAllText(Path.Combine(settingsDir, "sohbet_cevirici_hata.log"), DateTime.Now.ToString("s") + " | " + ex.GetType().Name + " | " + ShortError(ex.Message) + Environment.NewLine, new UTF8Encoding(false));
        } catch { }
    }

    void AppendTranslation(ChatMessage message, string translated) {
        string line = "[" + message.channel + "] " + message.sender + ": " + translated + Environment.NewLine;
        output.SelectionStart = output.TextLength;
        output.SelectionColor = Color.FromArgb(124, 221, 216);
        output.AppendText(line);
        output.SelectionColor = output.ForeColor;
        if (output.Lines.Length > 40) {
            string[] lines = output.Lines;
            int keep = Math.Min(28, lines.Length);
            output.Text = String.Join(Environment.NewLine, lines, lines.Length - keep, keep);
        }
        output.SelectionStart = output.TextLength;
        output.ScrollToCaret();
    }

    string FindLogForWindow(IntPtr window) {
        if (!String.IsNullOrWhiteSpace(options.LogPath) && File.Exists(options.LogPath)) return options.LogPath;
        try {
            if (gameProcessId > 0) using (Process process = Process.GetProcessById(gameProcessId)) {
                string exe = process.MainModule.FileName;
                DirectoryInfo dir = Directory.GetParent(exe);
                if (dir != null) dir = dir.Parent;
                if (dir != null) dir = dir.Parent;
                if (dir != null) {
                    string candidate = Path.Combine(dir.FullName, "preferences", "logs", "wakfu_chat.log");
                    if (File.Exists(candidate)) return candidate;
                }
            }
        } catch { }
        foreach (string root in new[] { Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles) }) {
            string candidate = Path.Combine(root, "Steam", "steamapps", "common", "Wakfu", "preferences", "logs", "wakfu_chat.log");
            if (File.Exists(candidate)) return candidate;
        }
        return "";
    }

    IntPtr FindWakfuWindow() {
        IntPtr best = IntPtr.Zero; int bestArea = 0; gameProcessId = 0;
        foreach (string processName in new[] { "Wakfu", "javaw", "java" }) foreach (Process process in Process.GetProcessesByName(processName)) using (process) try {
            IntPtr hWnd = process.MainWindowHandle;if (hWnd == IntPtr.Zero) continue;
            string title = process.MainWindowTitle ?? "";if (!String.Equals(processName,"Wakfu",StringComparison.OrdinalIgnoreCase) && title.IndexOf("WAKFU",StringComparison.OrdinalIgnoreCase) < 0) continue;
            RECT r;if (!GetWindowRect(hWnd,out r)) continue;int area=Math.Max(0,r.Right-r.Left)*Math.Max(0,r.Bottom-r.Top);
            if (area > bestArea) { bestArea = area; best = hWnd; gameProcessId = process.Id; }
        } catch { }
        return best;
    }

    TranslatorSettings LoadSettings() {
        try {
            if (File.Exists(settingsPath)) {
                TranslatorSettings loaded = Json.Deserialize<TranslatorSettings>(File.ReadAllText(settingsPath, Encoding.UTF8)) ?? new TranslatorSettings();
                loaded.ProtectedApiKey = "";
                return loaded;
            }
        } catch { }
        return new TranslatorSettings { OffsetX = 18, OffsetY = -296 };
    }

    void SaveSettings() {
        try { Directory.CreateDirectory(settingsDir); File.WriteAllText(settingsPath, Json.Serialize(options), new UTF8Encoding(false)); } catch { }
    }

    static string ShortError(string value) {
        if (String.IsNullOrWhiteSpace(value)) return "bilinmeyen hata";
        value = value.Replace("\r", " ").Replace("\n", " ");
        return value.Length > 90 ? value.Substring(0, 90) + "…" : value;
    }

    [StructLayout(LayoutKind.Sequential)] struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool ReleaseCapture();
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr hWnd, int message, int wParam, int lParam);
}
