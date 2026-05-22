; NetSwitch 安装脚本 - Inno Setup 6
; 编译前先运行: python generate_icon.py && python build.py

#define MyAppName "NetSwitch"
#define MyAppVersion "{{VERSION}}"
#define MyAppExeName "NetSwitch.exe"

[Setup]
AppId={{B9E4C5A0-7F3D-4A2E-8C6B-1D9F0E2A4B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=NetSwitch
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\installer_output
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"
Name: "startupicon"; Description: "开机自动启动"; GroupDescription: "附加选项:"; Flags: checked

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "NetSwitch"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 NetSwitch"; \
    Flags: nowait skipifsilent unchecked
