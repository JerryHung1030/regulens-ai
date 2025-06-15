@echo off
chcp 65001 > nul
echo Clearing Regulens-AI cache, output directories and settings...

REM Set target directories
set CACHE_DIR=%~dp0cache
set OUTPUT_DIR=%~dp0output
set CONFIG_DIR=%USERPROFILE%\.config\regulens-ai
set REGULENS_DIR=%USERPROFILE%\regulens-ai
set SETTINGS_FILE=%USERPROFILE%\.regulens-ai.json

REM Clear cache directory
if exist "%CACHE_DIR%" (
    echo Clearing cache directory: %CACHE_DIR%
    rmdir /s /q "%CACHE_DIR%"
    if exist "%CACHE_DIR%" (
        echo Warning: Failed to clear cache directory
    ) else (
        echo Cache directory cleared
    )
) else (
    echo Cache directory does not exist
)

REM Clear output directory
if exist "%OUTPUT_DIR%" (
    echo Clearing output directory: %OUTPUT_DIR%
    rmdir /s /q "%OUTPUT_DIR%"
    if exist "%OUTPUT_DIR%" (
        echo Warning: Failed to clear output directory
    ) else (
        echo Output directory cleared
    )
) else (
    echo Output directory does not exist
)

REM Clear config directory
if exist "%CONFIG_DIR%" (
    echo Clearing config directory: %CONFIG_DIR%
    rmdir /s /q "%CONFIG_DIR%"
    if exist "%CONFIG_DIR%" (
        echo Warning: Failed to clear config directory
    ) else (
        echo Config directory cleared
    )
) else (
    echo Config directory does not exist
)

REM Clear regulens-ai directory
if exist "%REGULENS_DIR%" (
    echo Clearing regulens-ai directory: %REGULENS_DIR%
    rmdir /s /q "%REGULENS_DIR%"
    if exist "%REGULENS_DIR%" (
        echo Warning: Failed to clear regulens-ai directory
    ) else (
        echo Regulens-ai directory cleared
    )
) else (
    echo Regulens-ai directory does not exist
)

REM Clear settings file
if exist "%SETTINGS_FILE%" (
    echo Clearing settings file: %SETTINGS_FILE%
    del /f /q "%SETTINGS_FILE%"
    if exist "%SETTINGS_FILE%" (
        echo Warning: Failed to clear settings file
    ) else (
        echo Settings file cleared
    )
) else (
    echo Settings file does not exist
)

echo Clear operation completed
pause 