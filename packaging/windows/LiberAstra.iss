; LiberAstra Windows 安装包。由 build.ps1 调用 Inno Setup 编译。

#define MyAppName "LiberAstra"
#define MyAppVersion "1.0.5"
#define MyAppPublisher "LiberAstra"
#define MyAppURL "https://github.com/liberalchang/LiberAstra"

[Setup]
AppId={{C4E8A1B2-7D3F-4E15-9A60-2F8B6C1D4E70}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\LiberAstra
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=LiberAstra-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\runtime\python.exe

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: checkedonce

[Files]
Source: "stage\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LiberAstra"; Filename: "{app}\start.cmd"; Comment: "启动 LiberAstra"
Name: "{autodesktop}\LiberAstra"; Filename: "{app}\start.cmd"; Tasks: desktopicon

[Run]
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""LiberAstra 8000"" dir=in action=allow protocol=TCP localport=8000"; Flags: runhidden
Filename: "{app}\start.cmd"; Description: "启动 LiberAstra"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""LiberAstra 8000"""; Flags: runhidden
