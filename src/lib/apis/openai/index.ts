import { ApiError, openaiClient } from '$lib/apis/client';
import { APP_BASE_URL } from '$lib/constants';
import { logger } from '$lib/utils/logger';

// ---------------------------------------------------------------------------
// Config management (proxied via backend)
// ---------------------------------------------------------------------------

export const getOpenAIConfig = async (token: string = '') => openaiClient.get('/config', { token });

type OpenAIConfig = {
	ENABLE_OPENAI_API: boolean;
	OPENAI_API_BASE_URLS: string[];
	OPENAI_API_KEYS: string[];
	OPENAI_API_CONFIGS: object;
};

export const updateOpenAIConfig = async (token: string = '', config: OpenAIConfig) =>
	openaiClient.post('/config/update', { ...config }, { token });

export const getOpenAIUrls = async (token: string = '') => {
	const res = await openaiClient.get<{ OPENAI_API_BASE_URLS?: string[] }>('/urls', { token });
	return res?.OPENAI_API_BASE_URLS;
};

export const updateOpenAIUrls = async (token: string = '', urls: string[]) => {
	const res = await openaiClient.post<{ OPENAI_API_BASE_URLS?: string[] }>(
		'/urls/update',
		{ urls },
		{ token }
	);
	return res?.OPENAI_API_BASE_URLS;
};

export const getOpenAIKeys = async (token: string = '') => {
	const res = await openaiClient.get<{ OPENAI_API_KEYS?: string[] }>('/keys', { token });
	return res?.OPENAI_API_KEYS;
};

export const updateOpenAIKeys = async (token: string = '', keys: string[]) => {
	const res = await openaiClient.post<{ OPENAI_API_KEYS?: string[] }>(
		'/keys/update',
		{ keys },
		{ token }
	);
	return res?.OPENAI_API_KEYS;
};

// ---------------------------------------------------------------------------
// Direct URL access (raw fetch, no backend proxy)
// ---------------------------------------------------------------------------

export const getOpenAIModelsDirect = async (url: string, key: string) => {
	try {
		const res = await fetch(`${url}/models`, {
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				...(key && { authorization: `Bearer ${key}` })
			}
		});
		if (!res.ok) throw await res.json();
		return res.json();
	} catch (err) {
		throw `OpenAI: ${(err as { error?: { message?: string } })?.error?.message ?? 'Network Problem'}`;
	}
};

// ---------------------------------------------------------------------------
// Proxy-based model listing
// ---------------------------------------------------------------------------

export const getOpenAIModels = async (token: string, urlIdx?: number) => {
	try {
		return await openaiClient.get(`/models${typeof urlIdx === 'number' ? `/${urlIdx}` : ''}`, {
			token
		});
	} catch (err) {
		throw `OpenAI: ${(err as { error?: { message?: string } })?.error?.message ?? 'Network Problem'}`;
	}
};

export const verifyOpenAIConnection = async (
	token: string = '',
	url: string = 'https://api.openai.com/v1',
	key: string = '',
	direct: boolean = false
) => {
	if (!url) {
		throw 'OpenAI: URL is required';
	}

	try {
		if (direct) {
			const res = await fetch(`${url}/models`, {
				method: 'GET',
				headers: {
					Accept: 'application/json',
					Authorization: `Bearer ${key}`,
					'Content-Type': 'application/json'
				}
			});
			if (!res.ok) throw await res.json();
			return res.json();
		} else {
			return await openaiClient.post('/verify', { url, key }, { token });
		}
	} catch (err) {
		throw `OpenAI: ${(err as { error?: { message?: string } })?.error?.message ?? 'Network Problem'}`;
	}
};

// ---------------------------------------------------------------------------
// Streaming completions (raw fetch for SSE)
// ---------------------------------------------------------------------------

export const chatCompletion = async (
	token: string = '',
	body: object,
	url: string = `${APP_BASE_URL}/api`
): Promise<[Response | null, AbortController]> => {
	const controller = new AbortController();

	const res = await fetch(`${url}/chat/completions`, {
		signal: controller.signal,
		method: 'POST',
		credentials: 'include',
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(body)
	}).catch((err) => {
		logger.error('openai', 'Chat Completion failed', err instanceof Error ? err : undefined, err);
		throw err;
	});

	return [res, controller];
};

export const generateOpenAIChatCompletion = async (
	token: string = '',
	body: object,
	url: string = `${APP_BASE_URL}/api`
) => {
	try {
		const res = await fetch(`${url}/chat/completions`, {
			method: 'POST',
			credentials: 'include',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(body)
		});
		if (!res.ok) {
			const payload = await res.json().catch(() => ({}));
			const detail =
				typeof payload?.detail === 'string'
					? payload.detail
					: typeof payload?.error?.message === 'string'
						? payload.error.message
						: `Chat completion failed (${res.status})`;
			throw new ApiError(res.status, detail);
		}
		return res.json();
	} catch (err) {
		if (err instanceof ApiError) throw err;
		throw err instanceof Error ? err : new Error(String(err));
	}
};

export const synthesizeOpenAISpeech = async (
	token: string = '',
	speaker: string = 'alloy',
	text: string = '',
	model: string = 'tts-1'
) => {
	const res = await openaiClient
		.post<Response>(
			'/audio/speech',
			{ model, input: text, voice: speaker },
			{ token, rawResponse: true }
		)
		.catch((err) => {
			logger.error(
				'openai',
				'Synthesize OpenAI Speech failed',
				err instanceof Error ? err : undefined,
				err
			);
			throw err;
		});

	return res;
};
