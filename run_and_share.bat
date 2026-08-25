@echo off
cd /d "%~dp0"
set CLOUDFLARED="C:\Users\Vishwas Vaish\ngrok\cloudflared.exe"

echo Starting the price checker app...
start "Price Checker App - keep this window open" cmd /k python -m streamlit run app.py --server.port 8501 --server.headless true

echo Waiting for it to boot...
timeout /t 6 /nobreak >nul

echo Starting the public tunnel...
start "PUBLIC LINK - copy the https://...trycloudflare.com URL from here" cmd /k %CLOUDFLARED% tunnel --url http://localhost:8501

echo.
echo Two windows just opened - keep BOTH of them open the whole time:
echo   1. "Price Checker App"  - runs the app itself
echo   2. "PUBLIC LINK"        - shows your shareable URL (a line ending in trycloudflare.com)
echo.
echo Copy that trycloudflare.com URL from window 2 and send it to your friends.
echo Closing either window, closing your laptop lid, or shutting down stops the link.
echo.
pause
