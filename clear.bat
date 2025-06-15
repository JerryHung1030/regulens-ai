@echo off
chcp 65001 > nul
echo 正在清除 Regulens-AI 的快取、輸出目錄和設定...

REM 設定目標目錄
set CACHE_DIR=%~dp0cache
set OUTPUT_DIR=%~dp0output
set CONFIG_DIR=%USERPROFILE%\.config\regulens-ai
set REGULENS_DIR=%USERPROFILE%\regulens-ai
set SETTINGS_FILE=%USERPROFILE%\.regulens-ai.json
set PROJECTS_DIR=%~dp0projects
set TEMP_INDEX_DIR=%~dp0temp_index_cache_*

REM 清除快取目錄
if exist "%CACHE_DIR%" (
    echo 正在清除快取目錄: %CACHE_DIR%
    rmdir /s /q "%CACHE_DIR%"
    if exist "%CACHE_DIR%" (
        echo 警告: 無法清除快取目錄
    ) else (
        echo 快取目錄已清除
    )
) else (
    echo 快取目錄不存在
)

REM 清除輸出目錄
if exist "%OUTPUT_DIR%" (
    echo 正在清除輸出目錄: %OUTPUT_DIR%
    rmdir /s /q "%OUTPUT_DIR%"
    if exist "%OUTPUT_DIR%" (
        echo 警告: 無法清除輸出目錄
    ) else (
        echo 輸出目錄已清除
    )
) else (
    echo 輸出目錄不存在
)

REM 清除設定目錄
if exist "%CONFIG_DIR%" (
    echo 正在清除設定目錄: %CONFIG_DIR%
    rmdir /s /q "%CONFIG_DIR%"
    if exist "%CONFIG_DIR%" (
        echo 警告: 無法清除設定目錄
    ) else (
        echo 設定目錄已清除
    )
) else (
    echo 設定目錄不存在
)

REM 清除 Regulens-AI 主目錄
if exist "%REGULENS_DIR%" (
    echo 正在清除 Regulens-AI 主目錄: %REGULENS_DIR%
    rmdir /s /q "%REGULENS_DIR%"
    if exist "%REGULENS_DIR%" (
        echo 警告: 無法清除 Regulens-AI 主目錄
    ) else (
        echo Regulens-AI 主目錄已清除
    )
) else (
    echo Regulens-AI 主目錄不存在
)

REM 清除設定檔
if exist "%SETTINGS_FILE%" (
    echo 正在清除設定檔: %SETTINGS_FILE%
    del /f /q "%SETTINGS_FILE%"
    if exist "%SETTINGS_FILE%" (
        echo 警告: 無法清除設定檔
    ) else (
        echo 設定檔已清除
    )
) else (
    echo 設定檔不存在
)

REM 清除專案目錄
if exist "%PROJECTS_DIR%" (
    echo 正在清除專案目錄: %PROJECTS_DIR%
    rmdir /s /q "%PROJECTS_DIR%"
    if exist "%PROJECTS_DIR%" (
        echo 警告: 無法清除專案目錄
    ) else (
        echo 專案目錄已清除
    )
) else (
    echo 專案目錄不存在
)

REM 清除臨時索引目錄
for %%i in (%TEMP_INDEX_DIR%) do (
    if exist "%%i" (
        echo 正在清除臨時索引目錄: %%i
        rmdir /s /q "%%i"
        if exist "%%i" (
            echo 警告: 無法清除臨時索引目錄 %%i
        ) else (
            echo 臨時索引目錄 %%i 已清除
        )
    )
)

echo 清除操作完成
pause 