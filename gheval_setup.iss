; GHEval Inno Setup Script
; Build installer from onedir output:
;   1. python build.py --onedir
;   2. Open this file in Inno Setup Compiler and click Build

#define MyAppName "GeoHeritage Evaluator"
#define MyAppShortName "GHEval"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "PaleoBytes"
#define MyAppExeName "GHEval.exe"

[Setup]
AppId={{B7A3F2E1-4D5C-4E6F-8A9B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppShortName}
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=GHEval_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Main executable
Source: "dist\GHEval\GHEval.exe"; DestDir: "{app}"; Flags: ignoreversion

; All files in _internal
Source: "dist\GHEval\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
