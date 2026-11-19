@echo off
setlocal
cd /d "%~dp0" || exit /b 1
title ISCLA QUIZ
set "ISCLA_RUNTIME=.runtime\python-3.13.17\python.exe"
if exist "%ISCLA_RUNTIME%" goto run
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $arch=$env:PROCESSOR_ARCHITEW6432; if (!$arch) {$arch=$env:PROCESSOR_ARCHITECTURE}; $platform=switch ($arch) {'AMD64' {'amd64'} 'ARM64' {'arm64'} 'x86' {'win32'} default {throw 'Arquitectura de Windows no reconocida.'}}; $version='3.13.17'; $sha=@{amd64='9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'; win32='4afd37bc88ed1391209a4c58deb902cd0741a476692412b23d340aff6e9285e7'; arm64='7b58787a047b400edbfcb539aa3cdb4e2ed77bf0f22cae42b7c01cedd7dd6614'}; $work=Join-Path $env:TEMP ('iscla-' + [Guid]::NewGuid().ToString('N')); $cache=Join-Path (Get-Location).Path '.runtime'; $target=Join-Path $cache 'python-3.13.17'; try { $null=New-Item -ItemType Directory -Path $work; $archive=Join-Path $work 'python.zip'; $payload=Join-Path $work 'python'; $uri='https://www.python.org/ftp/python/' + $version + '/python-' + $version + '-embed-' + $platform + '.zip'; Write-Host 'Descargando el componente portatil desde Python.org, solo la primera vez...'; Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $archive -TimeoutSec 120; if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash -ne $sha[$platform]) {throw 'La descarga no coincide con la huella oficial.'}; Expand-Archive -LiteralPath $archive -DestinationPath $payload; $exe=Join-Path $payload 'python.exe'; if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {throw 'No se encontro Python en el paquete.'}; & $exe -B -c 'import sqlite3, hashlib, ssl, http.server, getpass; sqlite3.connect('':memory:'').close()'; if ($LASTEXITCODE -ne 0) {throw 'El componente portatil no pudo iniciarse.'}; $null=New-Item -ItemType Directory -Force -Path $cache; if (Test-Path -LiteralPath $target) {Remove-Item -LiteralPath $target -Recurse -Force}; Move-Item -LiteralPath $payload -Destination $target; } catch {Write-Host ('Error: ' + $_.Exception.Message) -ForegroundColor Red; exit 1} finally {if (Test-Path -LiteralPath $work) {Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue}}"
if errorlevel 1 goto fail
if not exist "%ISCLA_RUNTIME%" goto fail

:run
echo.
echo ISCLA QUIZ - Pega el codigo de registro docente cuando te lo pida.
echo Una vez iniciado, abri http://localhost:8000 en el navegador.
echo No cierres esta ventana durante la partida.
echo.
"%ISCLA_RUNTIME%" -B -c "import runpy,sys;sys.path.insert(0,r'servidor');runpy.run_path(r'servidor/app.py',run_name='__main__')"
if errorlevel 1 goto fail
exit /b 0

:fail
echo.
echo No se pudo iniciar ISCLA QUIZ. Revisa el mensaje previo.
echo La primera apertura necesita Internet y acceso a www.python.org.
pause
exit /b 1
