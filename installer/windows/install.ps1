# Installs LineBuilder into this folder: its own Python 3.11, legacy Brightway2 and the app (Windows 10/11), then
# builds its Brightway project from your ecoinvent 3.12 cutoff. Needs internet once, no administrator rights.
# Nothing outside this folder is changed except one shortcut "LineBuilder" on the desktop (no PATH, no registry,
# no conda; the Brightway data stay in this folder, so the Activity Browser and its projects are not touched).
# Started by "Install LineBuilder.cmd"; written for Windows PowerShell 5.1 (on every Windows 10/11).
# Errors of programs (uv, python) are checked through their exit code: in PowerShell 5.1 'Stop' would also abort on
# their harmless messages on stderr. Cmdlets that must not fail carry -ErrorAction Stop.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'   # the progress bar of Invoke-WebRequest slows downloads down a lot
$Dir = $PSScriptRoot
$Tools = Join-Path $Dir '.tools'
$Venv = Join-Path $Dir '.venv'
$Log = Join-Path $Dir 'installation-log.txt'
$Name = 'LineBuilder'
$UvVersion = '0.9.5'
# The x64 build on every PC (Windows on ARM runs x64 programs as well).
$UvSha = '515dc53d7553f1357d0abc1f70acd921fbb9e30230b1d9a08737236daa6ee920'
$Python = 'cpython-3.11-windows-x86_64-none'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Tools 'python'   # Python stays inside this folder
$env:UV_CACHE_DIR = Join-Path $Tools 'cache'
$env:UV_PYTHON_PREFERENCE = 'only-managed'              # never another Python of this PC (conda, python.org, Store)
$env:UV_NO_CONFIG = '1'                                 # ignore uv settings of this user
$env:BRIGHTWAY2_DIR = Join-Path $Dir 'brightway'        # Brightway projects of LineBuilder only

function Fail($text) {
    Write-Host ''
    Write-Host "ERROR: $text" -ForegroundColor Red
    Write-Host "Log: $Log"
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

try {
    New-Item -ItemType Directory -Force -Path $Tools -ErrorAction Stop | Out-Null
    New-Item -ItemType Directory -Force -Path $env:BRIGHTWAY2_DIR -ErrorAction Stop | Out-Null   # legacy bw2data needs it
    $probe = Join-Path $Tools '.write-test'
    Set-Content -Path $probe -Value 'x' -ErrorAction Stop
    Remove-Item $probe -ErrorAction Stop
} catch {
    Write-Host "ERROR: no write access to $Dir" -ForegroundColor Red
    Write-Host 'Move the folder into your user folder (e.g. C:\Users\<name>\LineBuilder), not into Program Files.'
    exit 1
}
Start-Transcript -Path $Log -Force | Out-Null

Write-Host "${Name}: installation"
Write-Host "Folder: $Dir"
Write-Host ("Windows {0}, {1}" -f [Environment]::OSVersion.Version, $env:PROCESSOR_ARCHITECTURE)
Write-Host ''

try {
    $Uv = Join-Path $Tools 'uv.exe'
    if (-not (Test-Path $Uv)) {
        Write-Host "1/4  Loading the installer tool uv $UvVersion …"
        # The release archive straight from GitHub, checked against a pinned checksum. No install script.
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $zip = Join-Path $Tools 'uv.zip'
        $url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
        $ok = $false
        foreach ($i in 1..3) {
            try { Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 120 -ErrorAction Stop; $ok = $true; break }
            catch { Start-Sleep -Seconds 3 }
        }
        if (-not $ok) { Fail 'Download of uv failed (github.com). Check the internet connection and run it again.' }
        if ((Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower() -ne $UvSha) {
            Remove-Item $zip
            Fail 'uv download corrupted, run it again.'
        }
        Expand-Archive -Path $zip -DestinationPath $Tools -Force -ErrorAction Stop
        Remove-Item $zip
        if (-not (Test-Path $Uv)) { Fail 'uv not found.' }
    }

    Write-Host '2/4  Loading Python 3.11 …'
    & $Uv venv --quiet --allow-existing --python $Python $Venv
    if ($LASTEXITCODE -ne 0) { Fail 'Python 3.11 could not be set up.' }
    $Py = Join-Path $Venv 'Scripts\python.exe'

    Write-Host '3/4  Loading Brightway2 and the app, this takes a few minutes …'
    # requirements-lock.txt holds the SHA-256 checksum of every package file: uv installs a file only when it matches.
    # A mismatch stops the installation; only versions that do not fit this PC fall back to the newest matching ones
    # (requirements-app.txt, without checksums).
    $Errs = Join-Path $Tools 'lock-errors.txt'
    & $Uv pip install --quiet --require-hashes --python $Py -r (Join-Path $Dir 'requirements-lock.txt') 2> $Errs
    if ($LASTEXITCODE -ne 0) {
        Get-Content $Errs | ForEach-Object { Write-Host "$_" }
        if (Select-String -Path $Errs -Pattern 'hash mismatch' -Quiet) {
            Fail 'A downloaded package does not match its checksum, so it was not installed. Run the installation again later; if it happens again, send installation-log.txt.'
        }
        Write-Host '     The tested versions do not fit this PC, using the newest matching ones (without checksums) …'
        & $Uv pip install --quiet --python $Py -r (Join-Path $Dir 'requirements-app.txt')
        if ($LASTEXITCODE -ne 0) { Fail 'The packages could not be installed. Check the internet connection and run it again.' }
    }
    Remove-Item $Errs -ErrorAction SilentlyContinue
    & $Py -c 'import brightway2, bw2io, flask, yaml, xlsxwriter, py7zr'
    if ($LASTEXITCODE -ne 0) { Fail 'Installation check failed.' }
    Remove-Item -Recurse -Force (Join-Path $Tools 'cache') -ErrorAction SilentlyContinue   # downloads only
} catch {
    Fail ("Installation stopped: {0} Check the internet connection and run it again." -f $_.Exception.Message)
}

# a shortcut on the desktop that starts "Start LineBuilder.cmd" in this folder
try {
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut((Join-Path $Desktop "$Name.lnk"))
    $Link.TargetPath = Join-Path $Dir 'Start LineBuilder.cmd'
    $Link.WorkingDirectory = $Dir
    $Icon = Join-Path $Dir 'linebuilder.ico'
    if (Test-Path $Icon) { $Link.IconLocation = "$Icon,0" }
    $Link.Description = "Start $Name"
    $Link.Save()
    Write-Host "A shortcut `"$Name`" is on the desktop."
} catch {
    Write-Host "No desktop shortcut (not allowed here). Start $Name with `"Start LineBuilder`" in this folder."
}

Write-Host ''
if (Test-Path (Join-Path $Dir 'linebuilder_config.json')) {
    Write-Host '4/4  The Brightway project is already set up.'
} else {
    Write-Host '4/4  Setting up the Brightway project with ecoinvent 3.12 cutoff: from its download (.7z or folder),'
    Write-Host '     or an existing Activity Browser 2 project that has it (licensed, not included).'
    Push-Location $Dir
    & $Py (Join-Path $Dir 'setup_ecoinvent.py')
    Pop-Location
    if (Test-Path (Join-Path $Dir 'linebuilder_config.json')) {
        Write-Host '     Brightway project ready.'
    } else {
        Write-Host '     The Brightway project is not set up yet. "Start LineBuilder" asks for ecoinvent again.'
    }
}

Write-Host ''
Write-Host "Done. Start $Name with the icon `"$Name`" on the desktop, or `"Start LineBuilder`" in this folder." -ForegroundColor Green
Stop-Transcript | Out-Null
exit 0
