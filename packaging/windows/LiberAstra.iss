; LiberAstra Windows 安装包。由 build.ps1 调用 Inno Setup 编译。

#ifndef MyAppVersion
#define MyAppVersion "2.0.10"
#endif

#define MyAppName "LiberAstra"
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
AppMutex=Local\LiberAstraLauncher-C4E8A1B2-7D3F-4E15-9A60-2F8B6C1D4E70
SetupIconFile=assets\liberastra.ico
VersionInfoVersion={#MyAppVersion}
OutputDir=output
OutputBaseFilename=LiberAstra-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\LiberAstra.exe

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: checkedonce

[Files]
Source: "stage\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LiberAstra"; Filename: "{app}\LiberAstra.exe"; IconFilename: "{app}\LiberAstra.exe"; Comment: "启动 LiberAstra"
Name: "{autodesktop}\LiberAstra"; Filename: "{app}\LiberAstra.exe"; IconFilename: "{app}\LiberAstra.exe"; Tasks: desktopicon

[Run]
Filename: "cmd.exe"; Parameters: "/c netsh advfirewall firewall delete rule name=""LiberAstra 8000"" >nul 2>&1 & netsh advfirewall firewall add rule name=""LiberAstra 8000"" dir=in action=allow protocol=TCP localport=8000"; Flags: runhidden
Filename: "{app}\LiberAstra.exe"; Description: "启动 LiberAstra"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""LiberAstra 8000"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"
