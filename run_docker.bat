@echo off
REM Gemini MCP Server Docker Runner for Windows
REM This script starts the Gemini MCP Server in a Docker container

echo Starting Gemini MCP Server (Docker)...

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo Creating .env file template...
    echo GEMINI_API_KEY=your-gemini-api-key-here > .env
    echo.
    echo Please edit .env file and add your GEMINI_API_KEY
    echo Then run this script again.
    exit /b 1
)

REM Check if GEMINI_API_KEY is set in .env
findstr /r "GEMINI_API_KEY=..*[^ ]" .env >nul
if errorlevel 1 (
    echo Error: GEMINI_API_KEY is not set in .env file
    echo Please edit .env file and add your API key
    exit /b 1
)

REM Get the HOST_PORT from .env if set, otherwise use default
set HOST_PORT=8000
for /f "tokens=2 delims==" %%a in ('findstr /b "HOST_PORT=" .env 2^>nul') do set HOST_PORT=%%a

REM Build and start the container
echo Building and starting container...
docker-compose up -d --build

if %errorlevel% equ 0 (
    echo.
    echo ✅ Gemini MCP Server is running at http://localhost:%HOST_PORT%
    echo.
    echo To view logs: docker-compose logs -f
    echo To stop: docker-compose down
    echo.
    echo Configure your MCP client with:
    echo   URL: http://localhost:%HOST_PORT%
    echo   Transport: sse
) else (
    echo.
    echo ❌ Failed to start Gemini MCP Server
    echo Check the logs with: docker-compose logs
)