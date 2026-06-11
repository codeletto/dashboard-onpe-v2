@echo off
cd /d "C:\Users\USER\Desktop\dashboard_onpe_v2.0"
echo ===== %date% %time% ===== >> ingesta_log.txt
"venv\Scripts\python.exe" ingesta.py >> ingesta_log.txt 2>&1