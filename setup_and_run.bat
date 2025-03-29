@echo off
title Visual Novel Translator Setup and Run
setlocal enabledelayedexpansion

REM --- Configuration ---
set VENV_DIR=.venv
set REQUIREMENTS_CPU_FILE=requirements.txt
set REQUIREMENTS_CUDA_FILE=requirements_cuda.txt
set MAIN_SCRIPT=main.py
set CHOICE_FILE_NAME=.install_choice.txt
REM Define the path without quotes initially for easier use inside logic
set CHOICE_FILE_PATH_NOQUOTES=%VENV_DIR%\%CHOICE_FILE_NAME%
set CHOSEN_REQUIREMENTS_FILE=
set SAVED_CHOICE_FILE=

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
REM Use quotes around path for robustness
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment in "%VENV_DIR%".
        pause
        goto :eof
    )
    echo Virtual environment created successfully.
    REM Delete any potentially stale choice file from a previous install (use quotes)
    if exist "%CHOICE_FILE_PATH_NOQUOTES%" del "%CHOICE_FILE_PATH_NOQUOTES%"
) else (
    echo Virtual environment found.
)

REM --- Activate Virtual Environment ---
echo Activating virtual environment...
REM Use quotes around path for robustness
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    pause
    goto :eof
)

REM --- Determine Installation Requirements ---
REM Check if choice file exists using quoted path
if exist "%CHOICE_FILE_PATH_NOQUOTES%" (
    REM Escape parentheses here
    echo Found saved installation choice file ^(%CHOICE_FILE_NAME%^).
    REM Attempt to read the saved requirements file name using quoted path
    REM Clear variable first in case read fails or file is empty
    set "SAVED_CHOICE_FILE="
    set /p SAVED_CHOICE_FILE=<"%CHOICE_FILE_PATH_NOQUOTES%"

    REM Check if the variable was actually set (read successful and file not empty)
    if defined SAVED_CHOICE_FILE (
        REM Trim potential whitespace (important!)
        for /f "tokens=* delims= " %%a in ("!SAVED_CHOICE_FILE!") do set SAVED_CHOICE_FILE=%%a

        REM Validate if the saved file name actually points to an existing requirements file
        REM Use delayed expansion !SAVED_CHOICE_FILE! because it was set within this block
        if exist "!SAVED_CHOICE_FILE!" (
            REM Use /I for case-insensitive comparison
            if /I "!SAVED_CHOICE_FILE!"=="%REQUIREMENTS_CPU_FILE%" (
                set CHOSEN_REQUIREMENTS_FILE=!SAVED_CHOICE_FILE!
                REM Escape parentheses
                echo Using saved choice: CPU-only ^(!CHOSEN_REQUIREMENTS_FILE!^)
            ) else if /I "!SAVED_CHOICE_FILE!"=="%REQUIREMENTS_CUDA_FILE%" (
                set CHOSEN_REQUIREMENTS_FILE=!SAVED_CHOICE_FILE!
                 REM Escape parentheses
                echo Using saved choice: CUDA ^(GPU^) ^(!CHOSEN_REQUIREMENTS_FILE!^)
            ) else (
                echo WARNING: Saved choice file contains unrecognized value '!SAVED_CHOICE_FILE!'. Asking again.
                set CHOSEN_REQUIREMENTS_FILE=
            )
        ) else (
            echo WARNING: Saved choice file points to non-existent requirements file '!SAVED_CHOICE_FILE!'. Asking again.
            set CHOSEN_REQUIREMENTS_FILE=
        )
    ) else (
        echo WARNING: Could not read content from %CHOICE_FILE_NAME% or it is empty. Asking again.
        set CHOSEN_REQUIREMENTS_FILE=
    )
) else (
    echo No saved installation choice found.
    set CHOSEN_REQUIREMENTS_FILE=
)

REM Ask user if choice wasn't loaded successfully
if "%CHOSEN_REQUIREMENTS_FILE%"=="" (
    :ask_install_type
    echo.
    echo ----------------------------------------------------------------------
    REM Escape parentheses
    echo  Choose installation type ^(this choice will be saved^):
    echo    ^(1^) CPU-only ^(Recommended if unsure or no NVIDIA GPU^)
    echo    ^(2^) CUDA ^(GPU^) support ^(Requires NVIDIA GPU + CUDA setup^)
    echo ----------------------------------------------------------------------

    REM Use choice command for more robust input
    choice /c 12 /n /m "Enter choice (1 or 2): "

    REM Check errorlevel set by choice (2 checks first, then 1)
    if errorlevel 2 (
        set CHOSEN_REQUIREMENTS_FILE=%REQUIREMENTS_CUDA_FILE%
        REM Escape parentheses
        echo Selected CUDA ^(GPU^) requirements file: !CHOSEN_REQUIREMENTS_FILE!
    ) else if errorlevel 1 (
        set CHOSEN_REQUIREMENTS_FILE=%REQUIREMENTS_CPU_FILE%
        echo Selected CPU-only requirements file: !CHOSEN_REQUIREMENTS_FILE!
    ) else (
        echo Invalid input detected or cancelled. Please try again.
        goto :ask_install_type
    )

    REM Save the chosen requirements file name to the choice file
    REM Escape parentheses
    echo Saving choice ^(!CHOSEN_REQUIREMENTS_FILE!^) to %CHOICE_FILE_PATH_NOQUOTES%...
    REM Use quotes for the output path redirection
    (echo !CHOSEN_REQUIREMENTS_FILE!)>"%CHOICE_FILE_PATH_NOQUOTES%"
    if errorlevel 1 (
      echo WARNING: Failed to save installation choice to %CHOICE_FILE_NAME%. You may be asked again next time.
    )

    echo.
)

REM --- Verify/Install chosen requirements ---
REM Check if the final chosen file exists (use quotes)
if not exist "!CHOSEN_REQUIREMENTS_FILE!" (
    echo ERROR: Requirements file "!CHOSEN_REQUIREMENTS_FILE!" not found! This should not happen.
    pause
    goto :eof
)

echo Ensuring dependencies from !CHOSEN_REQUIREMENTS_FILE! are installed...
REM Use quotes around the requirements file path
pip install -r "!CHOSEN_REQUIREMENTS_FILE!"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install/verify dependencies. Please check !CHOSEN_REQUIREMENTS_FILE!, your internet connection, and CUDA setup if applicable.
    pause
    goto :eof
)
echo Dependencies are up-to-date according to !CHOSEN_REQUIREMENTS_FILE!.

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
echo Script finished.

:eof
endlocal
exit /b %errorlevel%