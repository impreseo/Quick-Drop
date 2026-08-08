#define MyAppName "QuickDrop"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "impreseo"
#define MyAppURL "https://github.com/impreseo/Quick-Drop"
#define MyAppExeName "QuickDrop.exe"

[Setup]
AppId={{3D01D71B-739A-4BF6-9C67-F0A7190D2508}
AppName={#MyAppName}
LicenseFile=..\LICENSE
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=https://github.com/impreseo/Quick-Drop/issues
AppUpdatesURL=https://github.com/impreseo/Quick-Drop/releases/latest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\release
OutputBaseFilename=QuickDrop-Setup-{#MyAppVersion}
SetupIconFile=..\src\quickdrop\assets\quickdrop.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=QuickDrop local file transfer installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\QuickDrop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QuickDrop"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\QuickDrop"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch QuickDrop"; Flags: nowait postinstall skipifsilent
