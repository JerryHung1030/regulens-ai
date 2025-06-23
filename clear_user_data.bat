@echo off
REM 刪除 Regulens-AI 所有用戶資料（logs、cache、output、sample_data 等）
setlocal

set "TARGET=%APPDATA%\regulens-ai"

if exist "%TARGET%" (
    echo 正在刪除 %TARGET% ...
    rmdir /s /q "%TARGET%"
    echo 刪除完成！
) else (
    echo 找不到 %TARGET% ，無需刪除。
)

endlocal
pause 