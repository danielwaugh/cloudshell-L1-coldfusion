@ECHO OFF
setlocal
set DRIVER_FOLDER=%~dp0
set DRIVER_NAME="coldfusion"
set DRIVER_PYTHON="%DRIVER_FOLDER%\Scripts\python.exe"
set PACKAGES="%DRIVER_FOLDER%\packages"
set QS_PYTHON_PATH="%DRIVER_FOLDER%\..\..\python"

set QS_PYTHON_REGEXP="^2.7.*"
set QS_PYTHON=%1

if not defined QS_PYTHON (
    if exist %QS_PYTHON_PATH% ( for /F %%x in ('dir /b %QS_PYTHON_PATH%') do echo %%x|findstr %QS_PYTHON_REGEXP%>nul&&set QS_PYTHON=%QS_PYTHON_PATH%\%%x\python.exe&&goto INSTALL )
)

if not defined QS_PYTHON set QS_PYTHON="python.exe"

:INSTALL

echo "Python: %QS_PYTHON%"

if not exist %DRIVER_PYTHON% %QS_PYTHON% -m virtualenv --system-site-packages "%DRIVER_FOLDER%\"
if exist %PACKAGES% %DRIVER_PYTHON% -m pip install -r "%DRIVER_FOLDER%\requirements.txt" --no-index -f %PACKAGES%
if not exist %PACKAGES% %DRIVER_PYTHON% -m pip install -r "%DRIVER_FOLDER%\requirements.txt"
REM copy "%DRIVER_FOLDER%\driver_exe_template" "%DRIVER_FOLDER%\..\%DRIVER_NAME%.exe"
copy "%DRIVER_FOLDER%\driver_exe_template" "%DRIVER_FOLDER%\dist\%DRIVER_NAME%.exe"
endlocal