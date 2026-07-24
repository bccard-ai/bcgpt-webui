import type { Handle } from '@sveltejs/kit';

/**
 * ⚠️  DEVELOPMENT-ONLY — These headers are NOT applied in production.
 *
 * This project uses `@sveltejs/adapter-static` (SPA mode), so SvelteKit
 * server hooks never execute in the production build.  The Python FastAPI
 * backend (`backend/bcgpt/utils/security_headers.py`) is the authoritative
 * source for security headers in deployed environments.
 *
 * These headers are kept for parity during local `vite dev` sessions.
 */
export const handle: Handle = async ({ event, resolve }) => {
	const response = await resolve(event);

	response.headers.set('X-Content-Type-Options', 'nosniff');
	response.headers.set('X-Frame-Options', 'SAMEORIGIN');
	response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
	response.headers.set('X-XSS-Protection', '0');
	response.headers.set('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=()');

	return response;
};
