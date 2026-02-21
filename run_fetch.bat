@echo off
REM Batch script to run auto_fetch.py via Windows Task Scheduler
REM
REM To set up Task Scheduler:
REM 1. Open Task Scheduler (taskschd.msc)
REM 2. Create Basic Task or Create Task
REM 3. Set trigger (e.g., every 1-2 hours)
REM 4. Action: Start a program
REM 5. Program/script: Path to this .bat file
REM 6. Optional: Check "Run whether user is logged on or not"

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the auto-fetch script (UTF-8 encoding prevents charmap errors from NWS text)
set PYTHONIOENCODING=utf-8
python auto_fetch.py --all

REM Log completion
echo Fetch completed at %date% %time% >> logs\scheduler_log.txt
