@echo off
echo Activation acces microphone pour les applications bureau...
echo.
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone" /v "Value" /t REG_SZ /d "Allow" /f
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged" /v "Value" /t REG_SZ /d "Allow" /f
echo.
echo OK - Acces micro bureau active.
echo Relance StreamOracle (lancer.bat).
echo.
pause
