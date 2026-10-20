PORT="${PORT:-8090}"
uvicorn bcgpt.main:app --port "$PORT" --host "${HOST:-127.0.0.1}" --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" --reload