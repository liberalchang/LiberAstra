using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace LiberAstraLauncher
{
    internal static class Program
    {
        private const string MutexName = @"Local\LiberAstraLauncher-C4E8A1B2-7D3F-4E15-9A60-2F8B6C1D4E70";
        private const string DefaultHost = "0.0.0.0";
        private const int DefaultPort = 8000;
        private static readonly object LogLock = new object();
        private static readonly Encoding Utf8NoBom = new UTF8Encoding(false);

        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string root = AppDomain.CurrentDomain.BaseDirectory;
            string local = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LiberAstra");
            string dataDir = Path.Combine(local, "data");
            string logDir = Path.Combine(local, "logs");
            string stateFile = Path.Combine(local, "runtime.port");
            Directory.CreateDirectory(dataDir);
            Directory.CreateDirectory(logDir);

            bool created;
            using (Mutex mutex = new Mutex(true, MutexName, out created))
            {
                if (!created)
                {
                    OpenExisting(stateFile);
                    return;
                }

                string host = Environment.GetEnvironmentVariable("LIBERASTRA_HOST");
                if (string.IsNullOrEmpty(host))
                {
                    host = DefaultHost;
                }
                int port = ReadPort(Environment.GetEnvironmentVariable("LIBERASTRA_PORT"), DefaultPort);

                if (IsHealthy(port))
                {
                    OpenBrowser(port);
                    return;
                }
                if (!CanBind(port))
                {
                    MessageBox.Show(
                        "端口 " + port + " 已被其他程序占用。\r\n请关闭占用该端口的程序后重试。",
                        "LiberAstra", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                string logFile = Path.Combine(logDir, "server.log");
                Process process;
                try
                {
                    process = StartServer(root, host, port, dataDir, logFile);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(
                        "无法启动 LiberAstra：\r\n" + ex.Message + "\r\n\r\n日志：" + logFile,
                        "LiberAstra", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                try
                {
                    WaitUntilHealthy(process, port);
                }
                catch (Exception ex)
                {
                    KillTree(process);
                    MessageBox.Show(
                        "LiberAstra 启动失败：\r\n" + ex.Message + "\r\n\r\n日志：" + logFile,
                        "LiberAstra", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                File.WriteAllText(stateFile, port.ToString());
                OpenBrowser(port);

                using (LauncherContext context = new LauncherContext(process, port, dataDir, stateFile))
                {
                    Application.Run(context);
                }
            }
        }

        private static Process StartServer(string root, string host, int port, string dataDir, string logFile)
        {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = Path.Combine(root, "runtime", "python.exe");
            info.Arguments = "-m uvicorn liberastra.main:app --host " + host + " --port " + port;
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.StandardOutputEncoding = Encoding.UTF8;
            info.StandardErrorEncoding = Encoding.UTF8;
            info.EnvironmentVariables["LIBERASTRA_DATA_DIR"] = dataDir;
            info.EnvironmentVariables["LIBERASTRA_HOST"] = host;
            info.EnvironmentVariables["LIBERASTRA_PORT"] = port.ToString();
            info.EnvironmentVariables["PLAYWRIGHT_BROWSERS_PATH"] = Path.Combine(root, "ms-playwright");
            info.EnvironmentVariables["PYTHONPATH"] = Path.Combine(root, "backend");
            info.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            info.EnvironmentVariables["PATH"] = Path.Combine(root, "runtime") + ";" + Environment.GetEnvironmentVariable("PATH");

            Process process = new Process();
            process.StartInfo = info;
            process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data != null)
                {
                    AppendLog(logFile, e.Data);
                }
            };
            process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data != null)
                {
                    AppendLog(logFile, e.Data);
                }
            };

            AppendLog(logFile, "===== " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " =====");
            AppendLog(logFile, "PORT=" + port + " HOST=" + host);
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            return process;
        }

        private static void WaitUntilHealthy(Process process, int port)
        {
            DateTime deadline = DateTime.UtcNow.AddSeconds(90);
            while (DateTime.UtcNow < deadline)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException("服务进程已退出，退出码 " + process.ExitCode + "。");
                }
                if (IsHealthy(port))
                {
                    return;
                }
                Thread.Sleep(300);
            }
            throw new TimeoutException("等待服务就绪超时（90 秒）。");
        }

        private static void OpenExisting(string stateFile)
        {
            string raw = null;
            try
            {
                if (File.Exists(stateFile))
                {
                    raw = File.ReadAllText(stateFile).Trim();
                }
            }
            catch
            {
            }

            int port = ReadPort(raw, DefaultPort);
            DateTime deadline = DateTime.UtcNow.AddSeconds(10);
            while (DateTime.UtcNow < deadline)
            {
                if (IsHealthy(port))
                {
                    OpenBrowser(port);
                    return;
                }
                Thread.Sleep(250);
            }
            MessageBox.Show(
                "LiberAstra 已经在运行，但服务尚未就绪。请稍后重试。",
                "LiberAstra", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private static int ReadPort(string raw, int fallback)
        {
            int port;
            if (!string.IsNullOrEmpty(raw) && int.TryParse(raw, out port) && port > 0 && port < 65536)
            {
                return port;
            }
            return fallback;
        }

        private static bool CanBind(int port)
        {
            try
            {
                TcpListener listener = new TcpListener(IPAddress.Any, port);
                listener.Start();
                listener.Stop();
                return true;
            }
            catch
            {
                return false;
            }
        }

        internal static bool IsHealthy(int port)
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(
                    "http://127.0.0.1:" + port + "/healthz");
                request.Timeout = 1000;
                request.ReadWriteTimeout = 1000;
                request.Proxy = null;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                using (StreamReader reader = new StreamReader(response.GetResponseStream()))
                {
                    string body = reader.ReadToEnd();
                    return response.StatusCode == HttpStatusCode.OK
                        && body.IndexOf("\"ok\"", StringComparison.Ordinal) >= 0;
                }
            }
            catch
            {
                return false;
            }
        }

        internal static void OpenBrowser(int port)
        {
            try
            {
                ProcessStartInfo info = new ProcessStartInfo("http://127.0.0.1:" + port);
                info.UseShellExecute = true;
                Process.Start(info);
            }
            catch
            {
            }
        }

        internal static void OpenFolder(string path)
        {
            try
            {
                ProcessStartInfo info = new ProcessStartInfo(path);
                info.UseShellExecute = true;
                Process.Start(info);
            }
            catch
            {
            }
        }

        internal static void KillTree(Process process)
        {
            if (process == null)
            {
                return;
            }
            try
            {
                if (!process.HasExited)
                {
                    ProcessStartInfo info = new ProcessStartInfo(
                        "taskkill", "/PID " + process.Id + " /T /F");
                    info.UseShellExecute = false;
                    info.CreateNoWindow = true;
                    Process killer = Process.Start(info);
                    if (killer != null)
                    {
                        killer.WaitForExit(5000);
                    }
                }
            }
            catch
            {
                try
                {
                    process.Kill();
                }
                catch
                {
                }
            }
        }

        internal static void AppendLog(string file, string line)
        {
            try
            {
                lock (LogLock)
                {
                    File.AppendAllText(file, line + Environment.NewLine, Utf8NoBom);
                }
            }
            catch
            {
            }
        }
    }

    internal sealed class LauncherContext : ApplicationContext
    {
        private readonly Process _process;
        private readonly int _port;
        private readonly string _dataDir;
        private readonly string _stateFile;
        private readonly NotifyIcon _notifyIcon;
        private readonly System.Windows.Forms.Timer _timer;
        private bool _exiting;

        public LauncherContext(Process process, int port, string dataDir, string stateFile)
        {
            _process = process;
            _port = port;
            _dataDir = dataDir;
            _stateFile = stateFile;

            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Items.Add("打开界面", null, delegate { Program.OpenBrowser(_port); });
            menu.Items.Add("打开数据目录", null, delegate { Program.OpenFolder(_dataDir); });
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出", null, delegate { Exit(); });

            _notifyIcon = new NotifyIcon();
            _notifyIcon.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            _notifyIcon.Text = "LiberAstra";
            _notifyIcon.ContextMenuStrip = menu;
            _notifyIcon.DoubleClick += delegate { Program.OpenBrowser(_port); };
            _notifyIcon.Visible = true;

            _timer = new System.Windows.Forms.Timer();
            _timer.Interval = 1000;
            _timer.Tick += delegate
            {
                bool exited;
                try
                {
                    exited = _process.HasExited;
                }
                catch
                {
                    exited = true;
                }
                if (exited)
                {
                    _timer.Stop();
                    OnServerExited();
                }
            };
            _timer.Start();
        }

        private void OnServerExited()
        {
            if (_exiting)
            {
                return;
            }
            _exiting = true;
            HideTray();
            try
            {
                File.Delete(_stateFile);
            }
            catch
            {
            }
            MessageBox.Show(
                "LiberAstra 服务已停止。\r\n日志：%LOCALAPPDATA%\\LiberAstra\\logs",
                "LiberAstra", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            ExitThread();
        }

        private void Exit()
        {
            _exiting = true;
            Program.KillTree(_process);
            HideTray();
            try
            {
                File.Delete(_stateFile);
            }
            catch
            {
            }
            ExitThread();
        }

        private void HideTray()
        {
            try
            {
                _notifyIcon.Visible = false;
                _notifyIcon.Dispose();
            }
            catch
            {
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                try
                {
                    _timer.Stop();
                    _timer.Dispose();
                }
                catch
                {
                }
                if (!_exiting)
                {
                    Program.KillTree(_process);
                }
                HideTray();
                try
                {
                    File.Delete(_stateFile);
                }
                catch
                {
                }
            }
            base.Dispose(disposing);
        }
    }
}
