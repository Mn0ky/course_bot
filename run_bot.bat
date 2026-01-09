@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Reads shared config from bot_config.json:
rem   webhook_url, discord_user_id, email, edge_driver
rem Required args: --term-name, --term-code, --crn
rem Optional args: --debug-port, --head

set "DEBUG_PORT="
set "HEAD="
set "TERM_NAME="
set "TERM_CODE="
set "CRN="

:parse
if "%~1"=="" goto doneparse

if /I "%~1"=="--debug-port" (set "DEBUG_PORT=%~2" & shift & shift & goto parse)
if /I "%~1"=="--term-name" (set "TERM_NAME=%~2" & shift & shift & goto parse)
if /I "%~1"=="--term-code" (set "TERM_CODE=%~2" & shift & shift & goto parse)
if /I "%~1"=="--crn" (set "CRN=%~2" & shift & shift & goto parse)
if /I "%~1"=="--head" (set "HEAD=1" & shift & goto parse)

echo Unknown argument: %~1
goto usage

:doneparse
if "%TERM_NAME%"=="" goto usage
if "%TERM_CODE%"=="" goto usage
if "%CRN%"=="" goto usage

echo "=========================================="
echo "      Starting Course Registration Bot    "
echo "=========================================="
call Scripts\activate.bat

set "FETCH_ARGS=--term "%TERM_NAME%""
if not "%DEBUG_PORT%"=="" set "FETCH_ARGS=%FETCH_ARGS% --debug-port "%DEBUG_PORT%""
if "%HEAD%"=="1" set "FETCH_ARGS=%FETCH_ARGS% --head"

python fetch_srs_config.py %FETCH_ARGS%

set "REG_ARGS=--crn "%CRN%" --term "%TERM_CODE%""

python test_registration.py %REG_ARGS%

endlocal
exit /b 0

:usage
echo Usage:
echo   .\run_bot.bat --term-name "Spring Semester 2026" --term-code 202601 --crn 11038 [--debug-port ^<port^>] [--head]
endlocal
exit /b 1