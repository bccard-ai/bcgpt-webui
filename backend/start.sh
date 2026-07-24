#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

# Add conditional Playwright browser installation
if [[ "${RAG_WEB_LOADER_ENGINE,,}" == "playwright" ]]; then
    if [[ -z "${PLAYWRIGHT_WS_URI}" ]]; then
        echo "Installing Playwright browsers..."
        playwright install chromium
        playwright install-deps chromium
    fi

    python -c "import nltk; nltk.download('punkt_tab')"
fi

KEY_FILE=.bcgpt_secret_key

PORT="${PORT:-8090}"
HOST="${HOST:-0.0.0.0}"
if test "$BCGPT_SECRET_KEY $BCGPT_JWT_SECRET_KEY" = " "; then
  echo "Loading BCGPT_SECRET_KEY from file, not provided as an environment variable."

  if ! [ -e "$KEY_FILE" ]; then
    echo "Generating BCGPT_SECRET_KEY"
    echo $(head -c 32 /dev/random | base64) > "$KEY_FILE"
  fi

  echo "Loading BCGPT_SECRET_KEY from $KEY_FILE"
  BCGPT_SECRET_KEY=$(cat "$KEY_FILE")
fi

if [[ "${USE_OLLAMA_DOCKER,,}" == "true" ]]; then
    echo "USE_OLLAMA is set to true, starting ollama serve."
    ollama serve &
fi

if [[ "${USE_CUDA_DOCKER,,}" == "true" ]]; then
  echo "CUDA is enabled, appending LD_LIBRARY_PATH to include torch/cudnn & cublas libraries."
  _pyver=$(python -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
  export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib/$_pyver/site-packages/torch/lib:/usr/local/lib/$_pyver/site-packages/nvidia/cudnn/lib"
fi

# Check if SPACE_ID is set, if so, configure for space
if [ -n "$SPACE_ID" ]; then
  echo "Configuring for HuggingFace Space deployment"
  if [ -n "$ADMIN_USER_EMAIL" ] && [ -n "$ADMIN_USER_PASSWORD" ]; then
    echo "Admin user configured, creating"
    BCGPT_SECRET_KEY="$BCGPT_SECRET_KEY" uvicorn bcgpt.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips '${FORWARDED_ALLOW_IPS:-127.0.0.1}' $([ -z "$DISABLE_UVLOOP" ] && echo "--loop uvloop --http httptools") &
    app_pid=$!
    echo "Waiting for app to start..."
    while ! curl -s http://localhost:8090/health > /dev/null; do
      sleep 1
    done
    echo "Creating admin user..."
    curl \
      -X POST "http://localhost:8090/api/v1/auths/signup" \
      -H "accept: application/json" \
      -H "Content-Type: application/json" \
      -d "{ \"email\": \"${ADMIN_USER_EMAIL}\", \"password\": \"${ADMIN_USER_PASSWORD}\", \"name\": \"Admin\" }"
    echo "Shutting down app..."
    kill $app_pid
  fi

  export BCGPT_URL=${SPACE_HOST}
fi

BCGPT_SECRET_KEY="$BCGPT_SECRET_KEY" exec uvicorn bcgpt.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips '${FORWARDED_ALLOW_IPS:-127.0.0.1}' $([ -z "$DISABLE_UVLOOP" ] && echo "--loop uvloop --http httptools")
