PORT="${PORT:-8090}"
uvicorn bcgpt.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload