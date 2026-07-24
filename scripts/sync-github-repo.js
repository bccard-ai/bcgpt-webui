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
	const result = spawnSync(command, args, { stdio: 'inherit', ...options });

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
	'.sisyphus/'
];

const stagingRoot = mkdtempSync(resolve(tmpdir(), 'bcgpt-github-sync-'));
const sourceRsyncArgs = [
	'--archive',
	'--include=.env.example',
	'--include=.github/',
	'--exclude=.*/',
	'--include=static/pyodide/',
	'--include=static/pyodide/pyodide-lock.json',
	'--exclude=static/pyodide/*',
	...exclusions.flatMap((pattern) => [`--exclude=${pattern}`]),
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
	run('rsync', sourceRsyncArgs);

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
console.log(`  git -C ${deploymentRoot} add -A`);
console.log(`  git -C ${deploymentRoot} commit -m "release: <summary>"`);
