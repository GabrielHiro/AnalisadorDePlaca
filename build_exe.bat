@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON="

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
    goto :found_python
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3"
    goto :found_python
)

if exist "%LocalAppData%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe" (
    set "PYTHON=%LocalAppData%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe"
    goto :found_python
)

echo Python nao encontrado no PATH.
echo Instale Python 3.10+ em https://www.python.org/downloads/
echo Marque a opcao "Add python.exe to PATH" na instalacao.
goto :error

:found_python
echo Usando: %PYTHON%
echo.
echo Instalando dependencias de build...
%PYTHON% -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

echo.
echo Gerando executavel...
%PYTHON% -m PyInstaller --noconfirm --clean AnalisadorDePlacas.spec
if errorlevel 1 goto :error

echo.
echo Concluido: dist\AnalisadorDePlacas.exe
goto :end

:error
echo.
echo Falha ao gerar o executavel.
exit /b 1

:end
endlocal
