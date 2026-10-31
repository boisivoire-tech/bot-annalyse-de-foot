@echo off
REM Fabrication de l'exécutable Windows (à lancer dans le dossier du projet, .venv activé).
REM Résultat : dist\FootballIntelligencePro\FootballIntelligencePro.exe
REM Copiez votre fichier .env à côté de l'exécutable avant de le lancer.

python -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto error

python -m PyInstaller --noconfirm --clean --windowed ^
  --name FootballIntelligencePro ^
  --collect-all customtkinter ^
  --add-data "assets;assets" ^
  --add-data ".env.example;." ^
  main.py
if errorlevel 1 goto error

echo.
echo Build termine : dist\FootballIntelligencePro\FootballIntelligencePro.exe
echo Copiez .env dans dist\FootballIntelligencePro\ avant le premier lancement.
pause
exit /b 0

:error
echo.
echo ERREUR pendant la fabrication. Copiez le message ci-dessus et envoyez-le.
pause
exit /b 1
