; TabisVPN Windows Installer
; Inno Setup 6 script
; Build: iscc TabisVPN_Setup.iss

#define AppName "Tabis VPN"
#define AppVersion "2.4.0"
#define AppPublisher "Tabis VPN"
#define AppURL "https://tabisvpn.site"
#define AppExeName "TabisVPN.exe"

[Setup]
AppId={{8E2A4F3C-1B5D-4E7A-9C2F-3A6B8D0E4F1C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\TabisVPN
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\release
OutputBaseFilename=TabisVPN_Setup
SetupIconFile=ui\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Zapuskat Tabis VPN pri vhode v Windows"; GroupDescription: "Dopolnitelno:"; Flags: unchecked

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Udalit {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TabisVPN"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM {#AppExeName}"; Flags: runhidden; RunOnceId: "KillTabisVPN"

[Code]
function InitializeSetup(): Boolean;
var
  resultCode: Integer;
begin
  Exec('taskkill', '/F /IM {#AppExeName}', '', SW_HIDE, ewWaitUntilTerminated, resultCode);
  Result := True;
end;
