import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const deploymentRoot = resolve(
	process.env.GITHUB_SYNC_DIR ?? resolve(projectRoot, '..', 'bcgpt-webui-github')
);

if (deploymentRoot === projectRoot) {
	throw new Error('GITHUB_SYNC_DIR cannot point to this development repository.');
}

const run = (command, args, options = {}) => {
	const result = spawnSync(command, args, {
		stdio: options.input === undefined ? 'inherit' : ['pipe', 'inherit', 'inherit'],
		...options
	});

	if (result.error) {
		throw result.error;
	}

	if (result.status !== 0) {
		throw new Error(`${command} exited with status ${result.status}.`);
	}
};

if (!existsSync(deploymentRoot)) {
	mkdirSync(deploymentRoot, { recursive: true });
	run('git', ['init', '--initial-branch=main'], { cwd: deploymentRoot });
	console.log(`Created deployment repository: ${deploymentRoot}`);
} else {
	const gitCheck = spawnSync('git', ['rev-parse', '--is-inside-work-tree'], {
		cwd: deploymentRoot,
		stdio: 'ignore'
	});

	if (gitCheck.status !== 0) {
		throw new Error(
			`Deployment directory exists but is not a Git repository: ${deploymentRoot}\n` +
				'Initialize it with Git first, or set GITHUB_SYNC_DIR to another directory.'
		);
	}
}

const exclusions = [
	'.git/',
	'.claude/',
	// Runtime/private artifacts that live in the dev worktree (some even
	// git-tracked internally) but must never reach the public mirror:
	// user uploads / local DBs, and the HF embedding-model cache (~106MB,
	// symlinked blobs).
	'backend/data/',
	'backend/models/',
	'.codegraph',
	'.DS_Store',
	'.env',
	'.env.*',
	'node_modules/',
	'.svelte-kit/',
	'build/',
	'docs/',
	'package/',
	'coverage/',
	'htmlcov/',
	'.venv/',
	'venv/',
	'env/',
	'__pycache__/',
	'*.py[cod]',
	'*.egg-info/',
	'.mypy_cache/',
	'.pytest_cache/',
	'.ruff_cache/',
	'.omc/',
	'.omo/',
	'.playwright-mcp/',
	'.sisyphus/',
	// Internal documents and stale build output that are tracked in the dev
	// repo but are not part of the public source release.
	'ARTICLE.md',
	'LICENSE_NOTICE_REVIEW.md',
	'stats.html',
	'backend/bcgpt/static/_app/',
	'backend/bcgpt/static/index.html',
	// Secrets that tools may drop into the worktree.
	'.bcgpt_secret_key',
	'.webui_secret_key',
	'*.pem',
	'*.key',
	'*.p12',
	'*.pfx',
	'*.sqlite',
	'*.db',
	'*.log'
];

// Only files tracked by git in the dev repo are candidates for the mirror, so
// untracked local files (dumps, notes, keys) can never be published.
const trackedFiles = spawnSync('git', ['ls-files', '-z'], {
	cwd: projectRoot,
	encoding: 'buffer',
	maxBuffer: 64 * 1024 * 1024
});
if (trackedFiles.status !== 0) {
	throw new Error('git ls-files failed in the dev repository.');
}

const stagingRoot = mkdtempSync(resolve(tmpdir(), 'bcgpt-github-sync-'));
// With --files-from every tracked file is listed explicitly, so a directory
// pattern ("docs/") alone would not stop its files: also exclude "docs/**".
const asRsyncPatterns = (pattern) =>
	pattern.endsWith('/') ? [pattern, `${pattern}**`] : [pattern];

const sourceRsyncArgs = [
	'--archive',
	'--from0',
	'--files-from=-',
	'--include=.env.example',
	'--include=.github/',
	'--include=.github/**',
	'--exclude=.*/',
	'--exclude=.*/**',
	'--include=static/pyodide/',
	'--include=static/pyodide/pyodide-lock.json',
	'--exclude=static/pyodide/*',
	...exclusions.flatMap(asRsyncPatterns).map((pattern) => `--exclude=${pattern}`),
	`${projectRoot}/`,
	`${stagingRoot}/`
];

const destinationRsyncArgs = [
	'--archive',
	'--delete',
	'--include=.env.example',
	'--exclude=.git/',
	'--exclude=.env',
	'--exclude=.env.*',
	`${stagingRoot}/`,
	`${deploymentRoot}/`
];

try {
	run('rsync', sourceRsyncArgs, { input: trackedFiles.stdout });

	// Hatch maps the root changelog into the installed Python package. Keep the
	// public mirror's package tree self-contained as well, so source-based
	// backend runs can load it through package data.
	const packageChangelog = resolve(stagingRoot, 'backend', 'bcgpt', 'CHANGELOG.md');
	mkdirSync(dirname(packageChangelog), { recursive: true });
	copyFileSync(resolve(projectRoot, 'CHANGELOG.md'), packageChangelog);

	run('rsync', destinationRsyncArgs);
} finally {
	rmSync(stagingRoot, { recursive: true, force: true });
}

console.log(`\nSynchronized source to ${deploymentRoot}`);
console.log('Review and publish it independently:');
console.log(`  git -C ${deploymentRoot} status`);
console.log(`  git -C ${deploymentRoot} diff --stat`);
console.log('  Run a secret scan (e.g. gitleaks detect) before staging, then add');
console.log('  the reviewed paths explicitly and commit.');
