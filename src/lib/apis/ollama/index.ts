import { ollamaClient } from '$lib/apis/client';
import { logger } from '$lib/utils/logger';

// ---------------------------------------------------------------------------
// Config & connection
// ---------------------------------------------------------------------------

export const verifyOllamaConnection = async (
	token: string = '',
	url: string = '',
	key: string = ''
) => {
	try {
		return await ollamaClient.post('/verify', { url, key }, { token });
	} catch (err) {
		throw `Ollama: ${(err as { error?: { message?: string } })?.error?.message ?? 'Network Problem'}`;
	}
};

export const getOllamaConfig = async (token: string = '') => ollamaClient.get('/config', { token });

type OllamaConfig = {
	ENABLE_OLLAMA_API: boolean;
	OLLAMA_BASE_URLS: string[];
	OLLAMA_API_CONFIGS: object;
};

export const updateOllamaConfig = async (token: string = '', config: OllamaConfig) =>
	ollamaClient.post('/config/update', { ...config }, { token });

export const getOllamaUrls = async (token: string = '') => {
	const res = await ollamaClient.get<{ OLLAMA_BASE_URLS?: string[] }>('/urls', { token });
	return res?.OLLAMA_BASE_URLS;
};

export const updateOllamaUrls = async (token: string = '', urls: string[]) => {
	const res = await ollamaClient.post<{ OLLAMA_BASE_URLS?: string[] }>(
		'/urls/update',
		{ urls },
		{ token }
	);
	return res?.OLLAMA_BASE_URLS;
};

export const getOllamaVersion = async (token: string, urlIdx?: number) => {
	const res = await ollamaClient.get<{ version?: string }>(
		`/api/version${urlIdx ? `/${urlIdx}` : ''}`,
		{ token }
	);
	return res?.version ?? false;
};

export const getOllamaModels = async (token: string = '', urlIdx: null | number = null) => {
	const res = await ollamaClient.get<{ models?: Array<{ model: string; name?: string }> }>(
		`/api/tags${urlIdx !== null ? `/${urlIdx}` : ''}`,
		{ token }
	);
	return (res?.models ?? [])
		.map((model) => ({ id: model.model, name: model.name ?? model.model, ...model }))
		.sort((a, b) => a.name.localeCompare(b.name));
};

// ---------------------------------------------------------------------------
// Streaming / raw fetch endpoints
// ---------------------------------------------------------------------------

export const generatePrompt = async (token: string = '', model: string, conversation: string) => {
	if (conversation === '') {
		conversation = '[no existing conversation]';
	}

	try {
		return await ollamaClient.post(
			'/api/generate',
			{
				model: model,
				prompt: `Conversation:
			${conversation}

			As USER in the conversation above, your task is to continue the conversation. Remember, Your responses should be crafted as if you're a human conversing in a natural, realistic manner, keeping in mind the context and flow of the dialogue. Please generate a fitting response to the last message in the conversation, or if there is no existing conversation, initiate one as a normal person would.
			
			Response:
			`
			},
			{ token, rawResponse: true }
		);
	} catch (err) {
		logger.error('ollama', 'Generate Prompt failed', err instanceof Error ? err : undefined, err);
		return null;
	}
};

export const generateEmbeddings = async (token: string = '', model: string, text: string) => {
	return ollamaClient.post(
		'/api/embeddings',
		{ model, prompt: text },
		{ token, rawResponse: true }
	);
};

export const generateTextCompletion = async (token: string = '', model: string, text: string) => {
	return ollamaClient.post(
		'/api/generate',
		{ model, prompt: text, stream: true },
		{ token, rawResponse: true }
	);
};

export const generateChatCompletion = async (token: string = '', body: object) => {
	const controller = new AbortController();
	const res = await ollamaClient.post('/api/chat', body, {
		token,
		rawResponse: true,
		signal: controller.signal
	});
	return [res, controller];
};

// ---------------------------------------------------------------------------
// Model management
// ---------------------------------------------------------------------------

export const createModel = async (token: string, payload: object, urlIdx: string | null = null) => {
	return ollamaClient.post(`/api/create${urlIdx !== null ? `/${urlIdx}` : ''}`, payload, {
		token,
		rawResponse: true
	});
};

export const deleteModel = async (token: string, tagName: string, urlIdx: string | null = null) =>
	ollamaClient
		.del(`/api/delete${urlIdx !== null ? `/${urlIdx}` : ''}`, { name: tagName }, { token })
		.then(() => true);

export const pullModel = async (token: string, tagName: string, urlIdx: number | null = null) => {
	const controller = new AbortController();

	try {
		const res = await ollamaClient.post(
			`/api/pull${urlIdx !== null ? `/${urlIdx}` : ''}`,
			{ name: tagName },
			{ token, rawResponse: true, signal: controller.signal }
		);
		return [res, controller];
	} catch (err) {
		logger.error('ollama', 'Pull Model failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const downloadModel = async (
	token: string,
	download_url: string,
	urlIdx: string | null = null
) => {
	try {
		return await ollamaClient.post(
			`/models/download${urlIdx !== null ? `/${urlIdx}` : ''}`,
			{ url: download_url },
			{ token, rawResponse: true }
		);
	} catch (err) {
		logger.error('ollama', 'Download Model failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const uploadModel = async (token: string, file: File, urlIdx: string | null = null) => {
	const formData = new FormData();
	formData.append('file', file);

	try {
		return await ollamaClient.post(
			`/models/upload${urlIdx !== null ? `/${urlIdx}` : ''}`,
			formData,
			{ token, rawResponse: true }
		);
	} catch (err) {
		logger.error('ollama', 'Upload Model failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};
