@echo off
title Visual Novel Translator Setup and Run
setlocal

REM --- Configuration ---
set VENV_DIR=.venv
set REQUIREMENTS_CPU_FILE=requirements.txt
set REQUIREMENTS_CUDA_FILE=requirements_cuda.txt
set MAIN_SCRIPT=main.py
set CHOSEN_REQUIREMENTS_FILE=

REM --- Check for Python ---
echo Checking for Python installation...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH. Please install Python 3 and ensure it's added to your PATH.
    pause
    goto :eof
)
echo Python found.

REM --- Check for Virtual Environment ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment in "%VENV_DIR%".
        pause
        goto :eof
    )
    echo Virtual environment created successfully.
    set NEEDS_INSTALL=1
) else (
    echo Virtual environment found.
    set NEEDS_INSTALL=0
)

REM --- Activate Virtual Environment ---
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    pause
    goto :eof
)

REM --- Check if installation is needed (if venv existed) ---
if "%NEEDS_INSTALL%"=="0" (
    echo Checking if core dependencies are installed...
    pip show opencv-python >nul 2>nul
    if %errorlevel% neq 0 (
        echo Core dependencies not found. Triggering installation.
        set NEEDS_INSTALL=1
    ) else (
        echo Core dependencies seem to be installed. Skipping installation check.
    )
)

REM --- Install Requirements if Needed ---
REM This block is parsed even if NEEDS_INSTALL is 0, so special characters need escaping
if "%NEEDS_INSTALL%"=="1" (
    REM --- Ask user for installation type ---
    :ask_install_type
    echo.
    echo ----------------------------------------------------------------------
    echo  Choose installation type:
    REM Escaped parentheses below using ^
    echo    (1^) CPU-only ^(Recommended if unsure or no NVIDIA GPU^)
    echo    (2^) CUDA ^(GPU^) support ^(Requires NVIDIA GPU + CUDA setup^)
    echo ----------------------------------------------------------------------
    set /p INSTALL_CHOICE="  Enter choice (1 or 2): "

    if "%INSTALL_CHOICE%"=="1" (
        set CHOSEN_REQUIREMENTS_FILE=%REQUIREMENTS_CPU_FILE%
        echo Selected CPU-only requirements file: %CHOSEN_REQUIREMENTS_FILE%
    ) else if "%INSTALL_CHOICE%"=="2" (
        set CHOSEN_REQUIREMENTS_FILE=%REQUIREMENTS_CUDA_FILE%
        echo Selected CUDA (GPU^) requirements file: %CHOSEN_REQUIREMENTS_FILE%
    ) else (
        echo Invalid choice. Please enter '1' or '2'.
        goto :ask_install_type
    )
    echo.

    REM --- Check if chosen file exists ---
    if not exist "%CHOSEN_REQUIREMENTS_FILE%" (
        echo ERROR: Requirements file "%CHOSEN_REQUIREMENTS_FILE%" not found!
        pause
        goto :eof
    )

    REM --- Install chosen requirements ---
    echo Installing dependencies from %CHOSEN_REQUIREMENTS_FILE%...
    pip install -r "%CHOSEN_REQUIREMENTS_FILE%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies. Please check %CHOSEN_REQUIREMENTS_FILE%, your internet connection, and CUDA setup if applicable.
        pause
        goto :eof
    )
    echo Dependencies installed successfully.
)

REM --- Run the Application ---
echo Starting Visual Novel Translator...
echo ====================================
python %MAIN_SCRIPT%
if %errorlevel% neq 0 (
    echo ERROR: The application exited with an error.
) else (
    echo Application finished.
)
echo ====================================

:cleanup
REM Deactivate is usually not necessary for script termination
echo Script finished. Press any key to exit.
pause >nul

:eof
endlocal
exit /b %errorlevel%