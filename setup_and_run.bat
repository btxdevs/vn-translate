@echo off
setlocal enabledelayedexpansion

REM --- Configuration ---
set VENV_NAME=venv
set PYTHON_EXE=python
set REQUIREMENTS_FILE=requirements.txt
set MAIN_SCRIPT=main.py
set SETUP_FLAG_FILE=%VENV_NAME%\.setup_complete

REM --- Function to check if command exists ---
:command_exists
where %1 >nul 2>nul
exit /b %errorlevel%

REM --- Check if Python is available ---
echo Checking for Python (%PYTHON_EXE%)...
call :command_exists %PYTHON_EXE%
if %errorlevel% neq 0 (
    echo ERROR: Python executable '%PYTHON_EXE%' not found in PATH.
    echo Please install Python 3.8+ and ensure it's added to your system PATH.
    goto :error_exit
) else (
    echo Python found.
)

REM --- Check if already set up ---
if exist "%VENV_NAME%" (
    if exist "%SETUP_FLAG_FILE%" (
        echo Virtual environment '%VENV_NAME%' already set up.
        goto :run_app
    ) else (
        echo Virtual environment '%VENV_NAME%' exists but setup flag not found.
        echo Consider deleting the '%VENV_NAME%' folder and re-running if setup failed previously.
        echo Attempting to run the app anyway...
        goto :run_app
    )
)

REM --- Start Setup ---
echo Creating virtual environment '%VENV_NAME%'...

REM Create the virtual environment (Quote the executable)
"%PYTHON_EXE%" -m venv "%VENV_NAME%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment '%VENV_NAME%'.
    echo Check permissions and Python installation.
    goto :error_exit
)
echo Virtual environment created successfully.

echo Installing dependencies from "%REQUIREMENTS_FILE%"...
echo This may take a while, especially for PyTorch and OCR libraries...

REM Define the path to the Python executable within the venv
set VENV_PYTHON="%VENV_NAME%\Scripts\python.exe"

REM Use the Python interpreter inside the venv to run pip install (Quote executable and requirements file)
%VENV_PYTHON% -m pip install -r "%REQUIREMENTS_FILE%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies. Check network connection and "%REQUIREMENTS_FILE%".
    echo You might need to install C++ Build Tools or specific CUDA versions manually first.
    echo Deleting potentially incomplete venv folder. Please re-run the script.
    rmdir /s /q "%VENV_NAME%" > nul 2>&1
    goto :error_exit
)

REM Create setup complete flag
echo Setup Complete > "%SETUP_FLAG_FILE%"
if %errorlevel% neq 0 (
    echo WARNING: Could not create setup flag file "%SETUP_FLAG_FILE%". Setup might run again next time.
)

echo Dependencies installed successfully. Environment setup complete.

:run_app
echo ---
echo Launching Visual Novel Translator...
echo ---
REM Define the path to the Python executable within the venv (needed again if jumped directly here)
set VENV_PYTHON="%VENV_NAME%\Scripts\python.exe"
REM Run the main application using the Python interpreter from the virtual environment (Quote executable and script)
%VENV_PYTHON% "%MAIN_SCRIPT%"

if %errorlevel% neq 0 (
    echo ---
    echo WARNING: Application exited with an error (code %errorlevel%). Check console output above for details.
    echo ---
) else (
    echo ---
    echo Application closed.
    echo ---
)
goto :end

:error_exit
echo ---
echo Setup failed. Please check the error messages above.
echo ---
pause
exit /b 1

:end
echo Script finished.
endlocal
pause
exit /b 0