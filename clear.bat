@echo off
REM 清除 Regulens AI 相關的配置和緩存文件

REM 清除配置目錄
if exist "%USERPROFILE%\.config\regulens-ai" (
    rmdir /s /q "%USERPROFILE%\.config\regulens-ai"
)

REM 清除配置文件
if exist "%USERPROFILE%\.regulens-ai.json" (
    del /f /q "%USERPROFILE%\.regulens-ai.json"
)

REM 清除緩存目錄
if exist "%USERPROFILE%\regulens-ai\cache" (
    rmdir /s /q "%USERPROFILE%\regulens-ai\cache"
)

REM 清除輸出目錄
if exist "%USERPROFILE%\regulens-ai\output" (
    rmdir /s /q "%USERPROFILE%\regulens-ai\output"
)

echo 清除完成！
pause 