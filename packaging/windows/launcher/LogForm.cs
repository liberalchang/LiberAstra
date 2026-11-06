using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace LiberAstraLauncher
{
    internal sealed class LogSource
    {
        internal readonly string Label;
        internal readonly string Path;
        internal readonly string Folder;

        internal LogSource(string label, string path, string folder)
        {
            Label = label;
            Path = path;
            Folder = folder;
        }
    }

    internal sealed class LogForm : Form
    {
        private const int TailBytes = 512 * 1024;
        private static LogForm _instance;

        private readonly LogSource[] _sources;
        private readonly ComboBox _sourceBox;
        private readonly TextBox _textBox;
        private readonly Label _status;
        private readonly CheckBox _follow;
        private readonly System.Windows.Forms.Timer _timer;
        private LogSource _current;
        private long _position;

        internal static void ShowSingleton(string dataDir)
        {
            if (_instance != null && !_instance.IsDisposed)
            {
                if (_instance.WindowState == FormWindowState.Minimized)
                {
                    _instance.WindowState = FormWindowState.Normal;
                }
                _instance.Activate();
                _instance.BringToFront();
                return;
            }
            _instance = new LogForm(dataDir);
            _instance.Show();
        }

        internal static void CloseSingleton()
        {
            LogForm form = _instance;
            _instance = null;
            if (form != null && !form.IsDisposed)
            {
                form.Close();
            }
        }

        private LogForm(string dataDir)
        {
            Text = "LiberAstra 系统日志";
            Width = 920;
            Height = 620;
            MinimumSize = new Size(640, 360);
            StartPosition = FormStartPosition.CenterScreen;
            ShowInTaskbar = true;
            MinimizeBox = true;
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

            string baseDir = Path.GetDirectoryName(dataDir) ?? dataDir;
            _sources = new LogSource[]
            {
                new LogSource("启动器日志", Path.Combine(baseDir, "logs", "server.log"), Path.Combine(baseDir, "logs")),
                new LogSource("应用日志", Path.Combine(dataDir, "logs", "app.log"), Path.Combine(dataDir, "logs")),
                new LogSource("插件日志：speech", Path.Combine(dataDir, "plugin-logs", "speech.log"), Path.Combine(dataDir, "plugin-logs")),
                new LogSource("插件日志：depth", Path.Combine(dataDir, "plugin-logs", "depth.log"), Path.Combine(dataDir, "plugin-logs"))
            };

            Panel top = new Panel();
            top.Dock = DockStyle.Top;
            top.Height = 40;
            top.Padding = new Padding(8, 7, 8, 5);

            _sourceBox = new ComboBox();
            _sourceBox.DropDownStyle = ComboBoxStyle.DropDownList;
            _sourceBox.Left = 8;
            _sourceBox.Top = 8;
            _sourceBox.Width = 190;
            for (int i = 0; i < _sources.Length; i++)
            {
                _sourceBox.Items.Add(_sources[i].Label);
            }
            _sourceBox.SelectedIndexChanged += delegate { LoadSource(); };
            top.Controls.Add(_sourceBox);

            top.Controls.Add(NewButton("刷新", 206, 60, delegate { LoadTail(); }));
            top.Controls.Add(NewButton("打开日志目录", 276, 100, delegate { OpenCurrentFolder(); }));
            top.Controls.Add(NewButton("复制全部", 386, 80, delegate { CopyAll(); }));
            top.Controls.Add(NewButton("清空视图", 476, 80, delegate { ClearView(); }));

            _follow = new CheckBox();
            _follow.Text = "跟随最新";
            _follow.AutoSize = true;
            _follow.Left = 570;
            _follow.Top = 12;
            _follow.Checked = true;
            top.Controls.Add(_follow);

            _status = new Label();
            _status.Dock = DockStyle.Bottom;
            _status.Height = 24;
            _status.TextAlign = ContentAlignment.MiddleLeft;
            _status.Padding = new Padding(8, 0, 8, 0);
            _status.Text = "选择日志类型";

            _textBox = new TextBox();
            _textBox.Dock = DockStyle.Fill;
            _textBox.Multiline = true;
            _textBox.ReadOnly = true;
            _textBox.ScrollBars = ScrollBars.Both;
            _textBox.WordWrap = false;
            _textBox.MaxLength = int.MaxValue;
            _textBox.Font = new Font("Consolas", 9f);
            _textBox.BackColor = Color.White;
            _textBox.HideSelection = false;

            Controls.Add(_textBox);
            Controls.Add(_status);
            Controls.Add(top);

            _timer = new System.Windows.Forms.Timer();
            _timer.Interval = 1000;
            _timer.Tick += delegate { RefreshLog(); };
            _timer.Start();

            FormClosed += delegate
            {
                if (_instance == this)
                {
                    _instance = null;
                }
            };
            Shown += delegate
            {
                _sourceBox.SelectedIndex = 0;
            };
        }

        private static Button NewButton(string text, int left, int width, EventHandler onClick)
        {
            Button button = new Button();
            button.Text = text;
            button.Left = left;
            button.Top = 7;
            button.Width = width;
            button.Height = 27;
            button.Click += onClick;
            return button;
        }

        private void LoadSource()
        {
            int index = _sourceBox.SelectedIndex;
            if (index < 0 || index >= _sources.Length)
            {
                return;
            }
            _current = _sources[index];
            _position = 0;
            _textBox.Clear();
            LoadTail();
        }

        private void LoadTail()
        {
            if (_current == null)
            {
                return;
            }

            string path = _current.Path;
            try
            {
                if (!File.Exists(path))
                {
                    _textBox.Clear();
                    _position = 0;
                    _status.Text = "暂无日志：" + path;
                    return;
                }

                using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    long length = stream.Length;
                    long start = Math.Max(0, length - TailBytes);
                    stream.Seek(start, SeekOrigin.Begin);
                    int count = (int)(length - start);
                    byte[] buffer = new byte[count];
                    int read = 0;
                    while (read < count)
                    {
                        int chunk = stream.Read(buffer, read, count - read);
                        if (chunk <= 0)
                        {
                            break;
                        }
                        read += chunk;
                    }

                    string text = Encoding.UTF8.GetString(buffer, 0, read);
                    if (start > 0)
                    {
                        int newline = text.IndexOf('\n');
                        if (newline >= 0)
                        {
                            text = text.Substring(newline + 1);
                        }
                        text = "…（仅显示最近 512KB）…\r\n" + text;
                    }
                    _textBox.Text = text;
                    _position = start + read;
                }

                _status.Text = path + "  ·  " + DateTime.Now.ToString("HH:mm:ss");
                ScrollToEnd();
            }
            catch (Exception ex)
            {
                _status.Text = "读取失败：" + ex.Message;
            }
        }

        private void RefreshLog()
        {
            if (_current == null)
            {
                return;
            }

            string path = _current.Path;
            try
            {
                if (!File.Exists(path))
                {
                    if (_textBox.TextLength == 0)
                    {
                        _status.Text = "暂无日志：" + path;
                    }
                    return;
                }

                using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    long length = stream.Length;
                    if (length < _position)
                    {
                        LoadTail();
                        return;
                    }
                    if (length == _position)
                    {
                        return;
                    }

                    stream.Seek(_position, SeekOrigin.Begin);
                    int count = (int)Math.Min(length - _position, TailBytes);
                    byte[] buffer = new byte[count];
                    int read = 0;
                    while (read < count)
                    {
                        int chunk = stream.Read(buffer, read, count - read);
                        if (chunk <= 0)
                        {
                            break;
                        }
                        read += chunk;
                    }
                    if (read <= 0)
                    {
                        return;
                    }

                    int complete = read;
                    for (int i = read - 1; i >= 0; i--)
                    {
                        if (buffer[i] == (byte)'\n')
                        {
                            complete = i + 1;
                            break;
                        }
                    }
                    if (complete <= 0)
                    {
                        return;
                    }

                    string text = Encoding.UTF8.GetString(buffer, 0, complete);
                    _textBox.AppendText(text);
                    _position += complete;
                    _status.Text = path + "  ·  " + DateTime.Now.ToString("HH:mm:ss");
                    if (_follow.Checked)
                    {
                        ScrollToEnd();
                    }
                }
            }
            catch (Exception ex)
            {
                _status.Text = "读取失败：" + ex.Message;
            }
        }

        private void OpenCurrentFolder()
        {
            if (_current == null)
            {
                return;
            }

            try
            {
                if (!System.IO.Directory.Exists(_current.Folder))
                {
                    System.IO.Directory.CreateDirectory(_current.Folder);
                }
                ProcessStartInfo info = new ProcessStartInfo(_current.Folder);
                info.UseShellExecute = true;
                Process.Start(info);
            }
            catch (Exception ex)
            {
                _status.Text = "打开目录失败：" + ex.Message;
            }
        }

        private void CopyAll()
        {
            try
            {
                if (_textBox.TextLength == 0)
                {
                    _status.Text = "暂无日志可复制";
                    return;
                }
                Clipboard.SetText(_textBox.Text);
                _status.Text = "已复制 " + _textBox.TextLength + " 个字符";
            }
            catch (Exception ex)
            {
                _status.Text = "复制失败：" + ex.Message;
            }
        }

        private void ClearView()
        {
            _textBox.Clear();
            if (_current != null && File.Exists(_current.Path))
            {
                try
                {
                    _position = new FileInfo(_current.Path).Length;
                }
                catch
                {
                    _position = 0;
                }
            }
            _status.Text = "视图已清空，新日志会继续追加";
        }

        private void ScrollToEnd()
        {
            _textBox.SelectionStart = _textBox.TextLength;
            _textBox.SelectionLength = 0;
            _textBox.ScrollToCaret();
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (_timer != null)
                {
                    _timer.Stop();
                    _timer.Dispose();
                }
                if (_instance == this)
                {
                    _instance = null;
                }
            }
            base.Dispose(disposing);
        }
    }
}
