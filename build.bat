@echo off
rem MQTTForge - one-shot build script (Windows cmd.exe)
rem
rem   build.bat               run tests, then build sdist + wheel
rem   build.bat --no-tests    skip the test phase
rem
setlocal EnableDelayedExpansion

set "PYTHON=%PYTHON%"
if "%PYTHON%"=="" set "PYTHON=python"

echo ==^> environment
"%PYTHON%" --version || goto :error

set "RUN_TESTS=1"
if "%1"=="--no-tests" set "RUN_TESTS=0"

if "%RUN_TESTS%"=="1" (
    echo ==^> running test suite
    "%PYTHON%" -m unittest discover -s tests -q || goto :error
    echo ==^> running end-to-end self-test
    "%PYTHON%" -m mqttforge selftest || goto :error
)

echo ==^> cleaning previous artifacts
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo ==^> building sdist + wheel
"%PYTHON%" -m build --help >nul 2>&1
if !errorlevel! equ 0 (
    "%PYTHON%" -m build || goto :error
) else (
    echo     'build' module not found - falling back to pip wheel
    "%PYTHON%" -m pip wheel . --no-deps -w dist || goto :error
)

echo ==^> artifacts
dir /b dist

echo ==^> smoke test
"%PYTHON%" -m mqttforge --version || goto :error

echo ==^> build complete
exit /b 0

:error
echo BUILD FAILED with error %errorlevel%
exit /b %errorlevel%
