@echo off
chcp 65001 > nul
echo Clearing Regulens-AI cache and output directories...

REM Set target directories
set CACHE_DIR=%~dp0cache
set OUTPUT_DIR=%~dp0output

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

echo Clear operation completed
pause 