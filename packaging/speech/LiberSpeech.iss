; Liber Speech 插件安装包。装到本机或另一台 Windows 主机，装完即用 Docker 拉起服务。

#define MyAppName "Liber Speech"
#define MyAppVersion "1.0.3"

[Setup]
AppId={{D5F9B2C3-8E40-4F26-AB71-3A9C7D2E5F81}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=LiberAstra
DefaultDirName={autopf}\LiberSpeech
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=LiberSpeech-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Files]
Source: "stage\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\安装并启动 Liber Speech"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install.ps1"""; WorkingDir: "{app}"

[Run]
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Liber Speech 5555"" dir=in action=allow protocol=TCP localport=5555"; Flags: runhidden
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install.ps1"""; WorkingDir: "{app}"; Description: "立即启动语音插件"; Flags: postinstall waituntilterminated

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Liber Speech 5555"""; Flags: runhidden
Filename: "docker"; Parameters: "compose down"; WorkingDir: "{app}"; Flags: runhidden
