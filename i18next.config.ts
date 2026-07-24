import { defineConfig } from 'i18next-cli';
import type { Plugin, ExtractedKeysMap } from 'i18next-cli';
import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';

const walkDir = async (dir: string, ext: string): Promise<string[]> => {
	const entries = await readdir(dir, { withFileTypes: true });
	const files: string[] = [];
	for (const entry of entries) {
		const fullPath = join(dir, entry.name);
		if (entry.isDirectory() && entry.name !== 'node_modules') {
			files.push(...(await walkDir(fullPath, ext)));
		} else if (entry.isFile() && entry.name.endsWith(ext)) {
			files.push(fullPath);
		}
	}
	return files;
};

const sveltePlugin = (): Plugin => ({
	name: 'svelte-plugin',

	async onLoad(code: string, filePath: string): Promise<string | undefined> {
		if (!filePath.endsWith('.svelte')) return undefined;

		const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/g;
		const scripts: string[] = [];
		let match;
		while ((match = scriptRegex.exec(code)) !== null) {
			scripts.push(match[1]);
		}

		return scripts.length > 0 ? scripts.join('\n') : '';
	},

	async onEnd(keys: ExtractedKeysMap) {
		const srcDir = join(import.meta.dirname, 'src');
		const svelteFiles = await walkDir(srcDir, '.svelte');
		const translationCallRegex = /\$i18n\.t\s*\(\s*['"`]([^'"`]+)['"`]\s*(?:,\s*\{[^}]*\})?\s*\)/g;

		for (const file of svelteFiles) {
			const content = await readFile(file, 'utf-8');
			const templateContent = content
				.replace(/<script[^>]*>[\s\S]*?<\/script>/g, '')
				.replace(/<style[^>]*>[\s\S]*?<\/style>/g, '');

			for (const [, key] of templateContent.matchAll(translationCallRegex)) {
				if (!keys.has(`translation:${key}`)) {
					keys.set(`translation:${key}`, {
						key,
						ns: 'translation',
						defaultValue: ''
					});
				}
			}
		}
	}
});

const getLocales = async (): Promise<string[]> => {
	const languagesPath = join(import.meta.dirname, 'src/lib/i18n/locales/languages.json');
	const languages = JSON.parse(await readFile(languagesPath, 'utf-8'));
	return languages.map((l: { code: string }) => l.code);
};

export default defineConfig({
	locales: await getLocales(),

	extract: {
		input: ['src/**/*.{js,ts,svelte}'],
		output: 'src/lib/i18n/locales/{{language}}/{{namespace}}.json',

		defaultNS: 'translation',
		defaultValue: '',
		keySeparator: false,
		nsSeparator: false,
		contextSeparator: '_',
		pluralSeparator: '_',

		sort: true,
		indentation: 2,
		removeUnusedKeys: false,

		functions: ['t', '*.t', 'i18next.t']
	},

	plugins: [sveltePlugin()]
});
