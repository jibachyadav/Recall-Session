# Build the Windows installer.  Run in PowerShell from the project folder:  powershell -File packaging\windows\build.ps1
# Needs: Python 3.12 and Inno Setup 6 (iscc).  Output: dist-packages\Recall-Session-<version>-Setup.exe and a .zip
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$version = (Get-Content "$root\VERSION").Trim()
$work = "$root\build-windows"
Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $work, "$root\dist-packages" -Force | Out-Null

Write-Host "== 1/3  build environment"
python -m venv "$work\venv"
& "$work\venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$work\venv\Scripts\python.exe" -m pip install -q -r "$root\requirements.txt" pyinstaller
& "$work\venv\Scripts\python.exe" "$root\packaging\make_icon.py"
& "$work\venv\Scripts\python.exe" "$root\packaging\fetch_models.py"

Write-Host "== 2/3  bundle the program"
Push-Location $work
& "$work\venv\Scripts\pyinstaller.exe" "$root\packaging\recall-session.spec" --noconfirm --distpath "$work\dist" --workpath "$work\pyi"
Pop-Location
# The program has no console window, so it writes its self-test result to a file; we wait for it and read the file.
$log = "$work\selftest.log"
$env:RECALL_SELFTEST_LOG = $log
$env:RECALL_SESSION_DATA = "$work\selftest-data"
$test = Start-Process "$work\dist\recall-session\recall-session.exe" -ArgumentList "--self-test" -Wait -PassThru
if (Test-Path $log) { Get-Content $log }
if ($test.ExitCode -ne 0) { throw "The packaged program failed its self-test (exit code $($test.ExitCode))." }

Write-Host "== 3/3  installer and zip"
Compress-Archive -Path "$work\dist\recall-session" -DestinationPath "$root\dist-packages\recall-session-windows-x64.zip" -Force
iscc "/DAppVersion=$version" "$root\packaging\windows\recall-session.iss"
Get-ChildItem "$root\dist-packages"
