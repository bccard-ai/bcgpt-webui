import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

import { viteStaticCopy } from 'vite-plugin-static-copy';
import { visualizer } from 'rollup-plugin-visualizer';

// /** @type {import('vite').Plugin} */
// const viteServerConfig = {
// 	name: 'log-request-middleware',
// 	configureServer(server) {
// 		server.middlewares.use((req, res, next) => {
// 			res.setHeader('Access-Control-Allow-Origin', '*');
// 			res.setHeader('Access-Control-Allow-Methods', 'GET');
// 			res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
// 			res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
// 			next();
// 		});
// 	}
// };

export default defineConfig({
	plugins: [
		sveltekit(),
		viteStaticCopy({
			targets: [
				{
					src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

					dest: 'wasm'
				}
			]
		}),
		// Bundle-size report — only emitted when ANALYZE=true (e.g. `npm run analyze`),
		// so normal/CI builds don't regenerate the multi-MB stats.html on every run.
		...(process.env.ANALYZE
			? [visualizer({ open: false, emitFile: false, filename: 'stats.html' })]
			: [])
	],
	define: {
		VITE_APP_VERSION: JSON.stringify(
			process.env.npm_package_version ?? process.env.BUN_PACKAGE_VERSION
		),
		VITE_APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	server: {
		watch: {
			ignored: ['**/backend/**']
		},
		// Make the dev frontend (:5173) behave as same-origin with the backend (:8090).
		// This keeps csrf_token/session cookies same-origin, preventing CSRF (403) errors on POSTs
		// (and the resulting empty chat ID → /chats/ 405 cascade), and keeps artifact iframes
		// same-origin. (The backend runs via uvicorn on 0.0.0.0:8090.)
		proxy: {
			'/api': { target: 'http://localhost:8090', changeOrigin: true },
			'/ollama': { target: 'http://localhost:8090', changeOrigin: true },
			'/openai': { target: 'http://localhost:8090', changeOrigin: true },
			// Bare-root probe endpoint — SystemHealthWidget calls /readyz through
			// appClient(APP_BASE_URL=''). Without an /api prefix and this proxy rule, the SvelteKit
			// dev server returns 404, so forward the request to the backend (:8090).
			'/readyz': { target: 'http://localhost:8090', changeOrigin: true },
			'/ws': { target: 'ws://localhost:8090', ws: true, changeOrigin: true }
		}
	},
	build: {
		sourcemap: true,
		rollupOptions: {
			output: {
				manualChunks(id) {
					if (id.includes('@codemirror/') || id.includes('@tiptap/')) {
						return 'editor-vendor';
					}
				}
			}
		}
	},
	worker: {
		format: 'es'
	}
});
