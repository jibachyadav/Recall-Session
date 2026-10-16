; Inno Setup script: wraps the PyInstaller folder into one Setup.exe.   iscc /DAppVersion=0.1.0 recall-session.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6F2C9C58-2B0E-4C5C-9D43-7A1E5B7C9A10}
AppName=Recall-Session
AppVersion={#AppVersion}
AppPublisher=Jibach Yadav
AppPublisherURL=https://github.com/jibachyadav/Recall-Session
DefaultDirName={autopf}\Recall-Session
DefaultGroupName=Recall-Session
UninstallDisplayIcon={app}\recall-session.exe
SetupIconFile=..\..\assets\icon.ico
OutputDir=..\..\dist-packages
OutputBaseFilename=Recall-Session-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Files]
Source: "..\..\build-windows\dist\recall-session\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Recall-Session"; Filename: "{app}\recall-session.exe"
Name: "{autodesktop}\Recall-Session"; Filename: "{app}\recall-session.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\recall-session.exe"; Description: "Start Recall-Session"; Flags: nowait postinstall skipifsilent
