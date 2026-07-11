[Setup]
AppId={{A8D7D4B7-7111-4E3C-A8F9-8D781B0AB1F4}
AppName=FilesGoThere
AppVersion=1.0.0
AppVerName=FilesGoThere 1.0.0
AppPublisher=TivuStream
AppPublisherURL=https://filesgothere.com
AppSupportURL=https://github.com/buio2005/FilesGoThere/issues
AppUpdatesURL=https://github.com/buio2005/FilesGoThere/releases
DefaultDirName={autopf}\FilesGoThere
DefaultGroupName=FilesGoThere
AllowNoIcons=yes
LicenseFile=..\LICENSE
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\filesgothere.ico
UninstallDisplayIcon={app}\FilesGoThere.exe
OutputDir=..\dist
OutputBaseFilename=FilesGoThere-Setup-v1.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FilesGoThere\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FilesGoThere"; Filename: "{app}\FilesGoThere.exe"; IconFilename: "{app}\FilesGoThere.exe"
Name: "{group}\Uninstall FilesGoThere"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FilesGoThere"; Filename: "{app}\FilesGoThere.exe"; IconFilename: "{app}\FilesGoThere.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FilesGoThere.exe"; Description: "{cm:LaunchProgram,FilesGoThere}"; Flags: nowait postinstall skipifsilent
