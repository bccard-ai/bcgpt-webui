const packages = [
	'micropip',
	'packaging',
	'requests',
	'beautifulsoup4',
	'numpy',
	'pandas',
	'matplotlib',
	'scikit-learn',
	'scipy',
	'regex',
	'sympy',
	'tiktoken',
	'seaborn',
	'pytz'
];

import { loadPyodide } from 'pyodide';
import { writeFile, readFile, copyFile, readdir, rmdir } from 'fs/promises';

// ── TUI Spinner ────────────────────────────────────────────────
const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
let _spinnerFrame = 0;
let _spinnerTimer = null;
let _spinnerPrefix = '';

const _origStdoutWrite = process.stdout.write.bind(process.stdout);
const _origStderrWrite = process.stderr.write.bind(process.stderr);

function _suppressOutput(chunk) {
	if (typeof chunk === 'string' && _spinnerTimer) return true;
	return false;
}

process.stdout.write = (chunk, encoding, callback) => {
	if (_suppressOutput(chunk)) return true;
	return _origStdoutWrite(chunk, encoding, callback);
};
process.stderr.write = (chunk, encoding, callback) => {
	if (_suppressOutput(chunk)) return true;
	return _origStderrWrite(chunk, encoding, callback);
};

function _restoreOutput() {
	process.stdout.write = _origStdoutWrite;
	process.stderr.write = _origStderrWrite;
}

function startSpinner(prefix) {
	_spinnerPrefix = prefix;
	_spinnerFrame = 0;
	_spinnerTimer = setInterval(() => {
		_origStdoutWrite(`\r\x1b[K${SPINNER_FRAMES[_spinnerFrame]} ${_spinnerPrefix}`);
		_spinnerFrame = (_spinnerFrame + 1) % SPINNER_FRAMES.length;
	}, 80);
}

function updateSpinnerText(prefix) {
	_spinnerPrefix = prefix;
}

function stopSpinner(successMsg) {
	if (_spinnerTimer) {
		clearInterval(_spinnerTimer);
		_spinnerTimer = null;
	}
	if (successMsg) {
		_origStdoutWrite(`\r\x1b[K✔ ${successMsg}\n`);
	}
	if (!_spinnerTimer) {
		_restoreOutput();
	}
}

function spinForStep(label, step, total) {
	updateSpinnerText(`${label} [${step}/${total}]`);
}
// ───────────────────────────────────────────────────────────────

/**
 * Loading network proxy configurations from the environment variables.
 * Bun natively supports HTTP/HTTPS proxies via standard env vars:
 *   HTTPS_PROXY, HTTP_PROXY, ALL_PROXY
 * No manual dispatcher setup is needed — Bun.fetch and the global fetch
 * automatically pick up these environment variables.
 */
function initNetworkProxyFromEnv() {
	const allProxy = process.env.all_proxy || process.env.ALL_PROXY;
	const httpsProxy = process.env.https_proxy || process.env.HTTPS_PROXY;
	const httpProxy = process.env.http_proxy || process.env.HTTP_PROXY;
	const proxy = httpsProxy || allProxy || httpProxy;

	if (proxy) {
		process.stdout.write(`Network proxy "${proxy}" detected from env (Bun native support)\n`);
	}
}

async function downloadPackages() {
	const total = packages.length;

	startSpinner('Loading Pyodide runtime...');
	let pyodide;
	try {
		pyodide = await loadPyodide({
			packageCacheDir: 'static/pyodide',
			stdout: () => {},
			stderr: () => {}
		});
	} catch (err) {
		stopSpinner(null);
		process.stderr.write(`Failed to load Pyodide: ${err}\n`);
		return;
	}

	const packageJson = JSON.parse(await readFile('package.json'));
	const pyodideVersion = packageJson.dependencies.pyodide.replace('^', '');

	try {
		const pyodidePackageJson = JSON.parse(await readFile('static/pyodide/package.json'));
		const pyodidePackageVersion = pyodidePackageJson.version.replace('^', '');

		if (pyodideVersion !== pyodidePackageVersion) {
			updateSpinnerText('Version mismatch, cleaning cache...');
			await rmdir('static/pyodide', { recursive: true });
		}
	} catch {
		// Pyodide package not found – first download, fine.
	}

	spinForStep('Loading micropip', 0, total);
	await pyodide.loadPackage('micropip', { messageCallback: () => {} });
	const micropip = pyodide.pyimport('micropip');

	for (let i = 0; i < packages.length; i++) {
		spinForStep(`Installing ${packages[i]}`, i + 1, total);
		try {
			await micropip.install(packages[i], { messageCallback: () => {} });
		} catch (err) {
			stopSpinner(null);
			process.stderr.write(`Package installation failed (${packages[i]}): ${err}\n`);
			return;
		}
	}

	updateSpinnerText('Freezing lock file...');
	try {
		const lockFile = await micropip.freeze();
		await writeFile('static/pyodide/pyodide-lock.json', lockFile);
	} catch (err) {
		stopSpinner(null);
		process.stderr.write(`Failed to write lock file: ${err}\n`);
		return;
	}

	stopSpinner(`Pyodide packages ready (${total} packages)`);
}

async function copyPyodide() {
	startSpinner('Copying Pyodide files to static...');
	// Copy all files from node_modules/pyodide to static/pyodide
	for await (const entry of await readdir('node_modules/pyodide')) {
		await copyFile(`node_modules/pyodide/${entry}`, `static/pyodide/${entry}`);
	}
	stopSpinner('Pyodide files copied');
}

initNetworkProxyFromEnv();
await downloadPackages();
await copyPyodide();
