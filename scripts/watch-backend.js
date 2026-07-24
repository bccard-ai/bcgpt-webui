#!/usr/bin/env bun

import { spawn, spawnSync } from 'child_process';
import { createHash, randomBytes } from 'crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_DIR = path.resolve(__dirname, '..');
const BACKEND_DIR = path.join(PROJECT_DIR, 'backend');
const REQUIREMENTS = path.join(BACKEND_DIR, 'requirements.txt');
const ENSURE_DB_SCRIPT = path.join(__dirname, 'ensure-db.py');
const CHECK_REQUIREMENTS_SCRIPT = path.join(__dirname, 'check-requirements.py');
// Marker recording the requirements.txt hash last installed (in gitignored node_modules).
const DEPS_MARKER = path.join(PROJECT_DIR, 'node_modules', '.cache', 'bcgpt-deps.hash');

const CYAN = '\x1b[36m';
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const RESET = '\x1b[0m';

const log = (color, tag, msg) => console.log(`${color}[${tag}]${RESET} ${msg}`);

function requirementsHash() {
	return createHash('sha256').update(readFileSync(REQUIREMENTS)).digest('hex');
}

function readMarker() {
	try {
		return readFileSync(DEPS_MARKER, 'utf8').trim();
	} catch {
		return null;
	}
}

function writeMarker(hash) {
	mkdirSync(path.dirname(DEPS_MARKER), { recursive: true });
	writeFileSync(DEPS_MARKER, hash);
}

// Ensure backend dependencies are installed before starting. Installs when:
//   - any pinned requirement is missing from the active `python` env, verified
//     via check-requirements.py (catches drifted / partially-populated envs
//     that the old `import uvicorn` + hash heuristic silently accepted), or
//   - requirements.txt changed since the last successful install (hash marker).
function ensureDependencies() {
	const hash = requirementsHash();

	const depsOk =
		spawnSync('python', [CHECK_REQUIREMENTS_SCRIPT], {
			cwd: BACKEND_DIR,
			stdio: 'ignore'
		}).status === 0;
	const requirementsChanged = readMarker() !== hash;

	if (depsOk && !requirementsChanged) {
		return true;
	}

	const reason = !depsOk ? 'missing backend dependencies' : 'requirements.txt changed';
	log(GREEN, 'watch-backend', `${reason}. Installing backend dependencies...`);

	const install = spawnSync('python', ['-m', 'pip', 'install', '-r', REQUIREMENTS], {
		cwd: BACKEND_DIR,
		stdio: 'inherit'
	});

	if (install.status !== 0) {
		log(RED, 'watch-backend', `Dependency install failed (code: ${install.status}).`);
		return false;
	}

	writeMarker(hash);
	log(GREEN, 'watch-backend', 'Backend dependencies installed.');
	return true;
}

// Ensure the configured database exists. For postgres, if the server is
// reachable but the target database is missing, create it. Best-effort:
// never blocks startup (the backend surfaces real connection errors).
function ensureDatabase() {
	const result = spawnSync('python', [ENSURE_DB_SCRIPT], {
		cwd: BACKEND_DIR,
		stdio: 'inherit'
	});
	if (result.status !== 0) {
		log(RED, 'watch-backend', 'Database check encountered an issue (continuing anyway).');
	}
}

// Persisted dev JWT signing key (gitignored cache dir).
const SECRET_KEY_FILE = path.join(PROJECT_DIR, 'node_modules', '.cache', 'bcgpt-secret-key');

// Resolve a STABLE BCGPT_SECRET_KEY for the dev backend.
//
// BCGPT_SECRET_KEY signs the session JWT that is stored in the HttpOnly `token`
// cookie. If this value changes, every previously-issued cookie fails signature
// verification -> get_current_user() raises 401 -> the SPA's 401 interceptor
// tears down the session and redirects to /auth. The old behaviour generated a
// fresh random key on EVERY (re)start/crash (uvicorn --reload is in-process, but
// any full process exit re-ran this), so restarting `npm run dev` or a backend
// crash silently logged everyone out ("401 on every action").
//
// Precedence:
//   1. An explicit BCGPT_SECRET_KEY from the environment (.env / shell / docker) — never overridden.
//   2. A previously persisted dev key — so JWTs survive restarts and crashes.
//   3. A freshly generated 256-bit key, persisted for next time.
function resolveStableSecretKey() {
	if (process.env.BCGPT_SECRET_KEY) {
		log(GREEN, 'watch-backend', 'Using BCGPT_SECRET_KEY from environment.');
		return process.env.BCGPT_SECRET_KEY;
	}

	try {
		const existing = readFileSync(SECRET_KEY_FILE, 'utf8').trim();
		if (existing) {
			return existing;
		}
	} catch {
		// No persisted key yet — fall through and create one.
	}

	const key = randomBytes(32).toString('base64');
	try {
		mkdirSync(path.dirname(SECRET_KEY_FILE), { recursive: true });
		writeFileSync(SECRET_KEY_FILE, key, { mode: 0o600 });
	} catch (err) {
		log(
			RED,
			'watch-backend',
			`Could not persist dev secret key (${err.message}); sessions will reset on restart.`
		);
	}
	return key;
}

// Computed ONCE for the whole watch lifetime and reused across every (re)spawn,
// so the JWT signing key is stable for the entire dev session.
const SECRET_KEY = resolveStableSecretKey();
// Log only a short fingerprint, never the raw secret.
const SECRET_KEY_FINGERPRINT = createHash('sha256').update(SECRET_KEY).digest('hex').slice(0, 8);

function startBackend(restartCount) {
	log(GREEN, 'watch-backend', `Starting backend... (restart #${restartCount})`);
	log(GREEN, 'watch-backend', `BCGPT_SECRET_KEY fingerprint=${SECRET_KEY_FINGERPRINT} (stable)`);

	const args = [
		'-m',
		'uvicorn',
		'bcgpt.main:app',
		'--port',
		'8090',
		'--host',
		'0.0.0.0',
		'--forwarded-allow-ips',
		'*',
		'--reload'
	];

	const child = spawn('python', args, {
		cwd: BACKEND_DIR,
		stdio: 'inherit',
		// dev (`bun run dev`) uses http://localhost, so disable the Secure flag for auth/session
		// cookies (the production default is true). This lets the browser store the token cookie
		// and prevents 401 errors.
		env: {
			...process.env,
			BCGPT_SECRET_KEY: SECRET_KEY,
			BCGPT_AUTH_COOKIE_SECURE: 'false',
			BCGPT_SESSION_COOKIE_SECURE: 'false'
		}
	});

	child.on('close', (code) => {
		const nextCount = restartCount + 1;
		log(
			RED,
			'watch-backend',
			`Backend process exited (code: ${code}). Restarting in 5 seconds... (restart #${nextCount})`
		);
		setTimeout(() => startBackend(nextCount), 5000);
	});

	child.on('error', (err) => {
		log(RED, 'watch-backend', `Failed to start backend: ${err.message}. Retrying in 5 seconds...`);
		setTimeout(() => startBackend(restartCount), 5000);
	});
}

log(CYAN, 'watch-backend', 'Starting backend watch process...');
log(CYAN, 'watch-backend', 'Backend will auto-restart on crash with 5s delay.');

if (ensureDependencies()) {
	ensureDatabase();
	startBackend(0);
} else {
	log(RED, 'watch-backend', 'Cannot start backend without dependencies. Exiting.');
	process.exit(1);
}
