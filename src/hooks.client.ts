import type { HandleClientError } from '@sveltejs/kit';

export const handleError: HandleClientError = async ({ error, event, status, message }) => {
	console.error('[Client Error]', { status, message, url: event.url.pathname }, error);

	return {
		message: 'An unexpected error occurred'
	};
};
