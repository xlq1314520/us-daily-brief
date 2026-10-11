@echo off
REM 本地备用运行：抓取 + 翻译 + 生成静态页
cd /d "%~dp0"
set PYTHON=C:\Users\ThinkBook16P\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON%" set PYTHON=python
if exist "%~dp0keys.local.bat" call "%~dp0keys.local.bat"
"%PYTHON%" main.py >> run_log.txt 2>&1
