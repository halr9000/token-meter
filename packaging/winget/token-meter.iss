#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceRoot
  #error SourceRoot is required
#endif
#ifndef OutputRoot
  #error OutputRoot is required
#endif

[Setup]
AppId={{69DAA038-2CF9-44B9-99F5-D27E5C2A2B9D}
AppName=Token Meter
AppVersion={#AppVersion}
AppPublisher=Splunk
AppPublisherURL=https://github.com/splunk/token-meter
DefaultDirName={localappdata}\Programs\Token Meter
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir={#OutputRoot}
OutputBaseFilename=token-meter-{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
UninstallDisplayName=Token Meter

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}\source"; Flags: ignoreversion recursesubdirs createallsubdirs

[Code]
procedure RunLifecycle(Action: String);
var
  ResultCode: Integer;
  Arguments: String;
begin
  Arguments := '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\source\scripts\package-windows.ps1') +
    '" -Action ' + Action + ' -PackageManager winget';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Arguments, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    RaiseException('Token Meter could not start its per-user lifecycle helper.');
  if ResultCode <> 0 then
    RaiseException('Token Meter lifecycle failed. The previous runtime is retained when restoration is possible.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunLifecycle('install');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RunLifecycle('uninstall');
end;
