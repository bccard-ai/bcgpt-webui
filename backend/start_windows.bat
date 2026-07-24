:: This method is not recommended, and we recommend you use the `start.sh` file with WSL instead.
@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

:: Get the directory of the current script
SET "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || exit /b

:: Add conditional Playwright browser installation
IF /I "%RAG_WEB_LOADER_ENGINE%" == "playwright" (
    IF "%PLAYWRIGHT_WS_URI%" == "" (
        echo Installing Playwright browsers...
        playwright install chromium
        playwright install-deps chromium
    )

    python -c "import nltk; nltk.download('punkt_tab')"
)

SET "KEY_FILE=.bcgpt_secret_key"
IF "%PORT%"=="" SET PORT=8090
IF "%HOST%"=="" SET HOST=0.0.0.0
SET "BCGPT_SECRET_KEY=%BCGPT_SECRET_KEY%"

:: Check if BCGPT_SECRET_KEY is not set
IF "%BCGPT_SECRET_KEY%" == " " (
    echo Loading BCGPT_SECRET_KEY from file, not provided as an environment variable.

    IF NOT EXIST "%KEY_FILE%" (
        echo Generating BCGPT_SECRET_KEY
        :: Generate a random value to use as a BCGPT_SECRET_KEY in case the user didn't provide one
        SET /p BCGPT_SECRET_KEY=<nul
        FOR /L %%i IN (1,1,12) DO SET /p BCGPT_SECRET_KEY=<!random!>>%KEY_FILE%
        echo BCGPT_SECRET_KEY generated
    )

    echo Loading BCGPT_SECRET_KEY from %KEY_FILE%
    SET /p BCGPT_SECRET_KEY=<%KEY_FILE%
)

:: Execute uvicorn
SET "BCGPT_SECRET_KEY=%BCGPT_SECRET_KEY%"
uvicorn bcgpt.main:app --host "%HOST%" --port "%PORT%" --forwarded-allow-ips '*' --ws auto
:: For ssl user uvicorn bcgpt.main:app --host "%HOST%" --port "%PORT%" --forwarded-allow-ips '*' --ssl-keyfile "key.pem" --ssl-certfile "cert.pem" --ws auto
