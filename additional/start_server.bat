@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo Starting Utility ERP Odoo 16 Server...
echo URL: http://localhost:8170
echo Database: invoice_utility_erp

netstat -ano | findstr /R /C:":8170.*LISTENING" >nul
if not errorlevel 1 (
    echo Odoo is already running on port 8170.
    echo Open http://localhost:8170 instead of starting another server.
    pause
    exit /b 1
)

D:\odoo-16.0\odoo-16.0\venv\Scripts\python.exe F:\invo-system\odoo_project_launcher.py -c F:\invo-system\invoice_utility_erp.conf
pause
