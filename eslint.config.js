// @ts-check
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import pluginCypress from 'eslint-plugin-cypress';
import eslintConfigPrettier from 'eslint-config-prettier/flat';
import svelteConfig from './svelte.config.js';

export default defineConfig([
	// ── Global ignores (mirrors former .eslintignore) ──────────────────────
	{
		ignores: [
			'.DS_Store',
			'node_modules/**',
			'build/**',
			'.svelte-kit/**',
			'package/**',
			// Generated / vendored bundles — never lint these. The compiled
			// SvelteKit output is copied into the backend static dir for serving,
			// and Pyodide ships its own minified WASM runtime. Linting them
			// produced ~46k phantom errors that drowned out real source issues
			// and made the husky/lint-staged pre-commit hook unusable.
			'backend/bcgpt/static/**',
			'static/pyodide/**',
			'src/lib/pyodide/**',
			'coverage/**',
			'cypress/videos/**',
			'cypress/screenshots/**',
			'**/.omc/**',
			'**/.omo/**',
			'**/.sisyphus/**',
			'.env',
			'.env.*',
			'!.env.example',
			'pnpm-lock.yaml',
			'package-lock.json',
			'yarn.lock'
		]
	},

	// ── Base JS recommended ────────────────────────────────────────────────
	js.configs.recommended,

	// ── TypeScript recommended (spreads multiple config objects) ──────────
	...tseslint.configs.recommended,

	// ── Svelte recommended (registers svelte-eslint-parser + rules) ───────
	...svelte.configs.recommended,

	// ── Global language options (browser + Node environment) ──────────────
	{
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			globals: {
				...globals.browser,
				...globals.node,
				...globals.es2021
			}
		}
	},

	// ── Project rule tuning ────────────────────────────────────────────────
	// Allow an underscore prefix to mark an intentionally-unused binding. This
	// is the canonical escape hatch for positional callback params, caught
	// errors, and array-destructuring holes that must exist but aren't read.
	{
		rules: {
			'@typescript-eslint/no-unused-vars': [
				'error',
				{
					args: 'after-used',
					argsIgnorePattern: '^_',
					varsIgnorePattern: '^_',
					caughtErrors: 'all',
					caughtErrorsIgnorePattern: '^_',
					destructuredArrayIgnorePattern: '^_',
					ignoreRestSiblings: true
				}
			]
		}
	},

	// ── .svelte files: wire TypeScript parser through svelte-eslint-parser ─
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				// svelte-eslint-parser delegates TS tokens to @typescript-eslint/parser
				parser: tseslint.parser,
				extraFileExtensions: ['.svelte'],
				// Pass Svelte compiler config so the parser understands preprocessors
				svelteConfig
			}
		}
	},

	// ── Cypress: scope to cypress/** only ─────────────────────────────────
	{
		files: ['cypress/**/*.cy.{js,ts}', 'cypress/**/*.{js,ts}'],
		extends: [pluginCypress.configs.recommended]
	},

	// ── Prettier: MUST come last to override formatting rules ─────────────
	eslintConfigPrettier
]);
