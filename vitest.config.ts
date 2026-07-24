import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node',
		globals: true
	},
	define: {
		VITE_APP_VERSION: JSON.stringify('0.0.0-test'),
		VITE_APP_BUILD_HASH: JSON.stringify('test-build')
	}
});
