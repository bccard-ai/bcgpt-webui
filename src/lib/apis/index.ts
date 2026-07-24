import { convertOpenApiToToolPayload, removeEmojis } from '$lib/utils';
import { getOpenAIModelsDirect } from './openai';
import { apiClient, appClient } from './client';

import { toast } from 'svelte-sonner';
import { logger } from '$lib/utils/logger';

function extractJsonField<T>(response: string, fieldName: string): T | null {
	const start = response.indexOf('{');
	const end = response.lastIndexOf('}');

	if (start !== -1 && end !== -1) {
		try {
			const json = response.substring(start, end + 1);
			const parsed = JSON.parse(json);
			if (parsed && parsed[fieldName] !== undefined) {
				return parsed[fieldName] as T;
			}
		} catch {
			// JSON parse failed — fall through to return null
		}
	}
	return null;
}

type CompletionResponse = { choices?: Array<{ message?: { content?: string } }> };

async function taskCompletion(
	endpoint: string,
	token: string,
	payload: Record<string, unknown>,
	errorLabel: string
): Promise<CompletionResponse> {
	try {
		return await apiClient.post<CompletionResponse>(`/tasks/${endpoint}/completions`, payload, {
			token
		});
	} catch (err) {
		logger.error('apis', errorLabel, err instanceof Error ? err : undefined, err);
		throw err;
	}
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export const getModels = async (
	token: string = '',
	connections: object | null = null,
	base: boolean = false
) => {
	let res: { data?: object[] };
	try {
		res = await appClient.get(`/api/models${base ? '/base' : ''}`, { token });
	} catch (err) {
		logger.error('apis', 'Get Models failed', err instanceof Error ? err : undefined, err);
		throw err;
	}

	let models = res?.data ?? [];

	if (connections && !base) {
		let localModels = [];

		if (connections) {
			const OPENAI_API_BASE_URLS = connections.OPENAI_API_BASE_URLS;
			const OPENAI_API_KEYS = connections.OPENAI_API_KEYS;
			const OPENAI_API_CONFIGS = connections.OPENAI_API_CONFIGS;

			const requests = [];
			for (const idx in OPENAI_API_BASE_URLS) {
				const url = OPENAI_API_BASE_URLS[idx];

				if (idx.toString() in OPENAI_API_CONFIGS) {
					const apiConfig = OPENAI_API_CONFIGS[idx.toString()] ?? {};

					const enable = apiConfig?.enable ?? true;
					const modelIds = apiConfig?.model_ids ?? [];

					if (enable) {
						if (modelIds.length > 0) {
							const modelList = {
								object: 'list',
								data: modelIds.map((modelId) => ({
									id: modelId,
									name: modelId,
									owned_by: 'openai',
									openai: { id: modelId },
									urlIdx: idx
								}))
							};

							requests.push(Promise.resolve(modelList));
						} else {
							requests.push(
								getOpenAIModelsDirect(url, OPENAI_API_KEYS[idx])
									.then((res) => res)
									.catch(() => {
										return {
											object: 'list',
											data: [],
											urlIdx: idx
										};
									})
							);
						}
					} else {
						requests.push(
							Promise.resolve({
								object: 'list',
								data: [],
								urlIdx: idx
							})
						);
					}
				}
			}

			const responses = await Promise.all(requests);

			for (const idx in responses) {
				const response = responses[idx];
				const apiConfig = OPENAI_API_CONFIGS[idx.toString()] ?? {};

				let models = Array.isArray(response) ? response : (response?.data ?? []);
				models = models.map((model) => ({ ...model, openai: { id: model.id }, urlIdx: idx }));

				const prefixId = apiConfig.prefix_id;
				if (prefixId) {
					for (const model of models) {
						model.id = `${prefixId}.${model.id}`;
					}
				}

				const tags = apiConfig.tags;
				if (tags) {
					for (const model of models) {
						model.tags = tags;
					}
				}

				localModels = localModels.concat(models);
			}
		}

		models = models.concat(
			localModels.map((model) => ({
				...model,
				name: model?.name ?? model?.id,
				direct: true
			}))
		);

		// Remove duplicates
		const modelsMap = {};
		for (const model of models) {
			modelsMap[model.id] = model;
		}

		models = Object.values(modelsMap);
	}

	return models;
};

// ---------------------------------------------------------------------------
// Chat lifecycle
// ---------------------------------------------------------------------------

type ChatCompletedForm = {
	model: string;
	messages: string[];
	chat_id: string;
	session_id: string;
};

export const chatCompleted = async (token: string, body: ChatCompletedForm) => {
	try {
		return await appClient.post('/api/chat/completed', body, { token });
	} catch (err) {
		logger.error('apis', 'Chat Completed failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

type ChatActionForm = {
	model: string;
	messages: string[];
	chat_id: string;
};

export const chatAction = async (token: string, action_id: string, body: ChatActionForm) => {
	try {
		return await appClient.post(`/api/chat/actions/${action_id}`, body, { token });
	} catch (err) {
		logger.error('apis', 'Chat Action failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export type TaskStopBinding = {
	chat_id: string;
	message_id: string;
};

export type ChatGenerationStatus =
	| 'admitted'
	| 'running'
	| 'stop_requested'
	| 'completed'
	| 'stopped'
	| 'error'
	| 'timed_out';

export type ChatGeneration = {
	generation_id: string;
	turn_id: string | null;
	client_message_id: string | null;
	message_id: string;
	chat_id: string;
	model_id: string | null;
	task_id: string | null;
	status: ChatGenerationStatus;
	terminal_reason: string | null;
	version: number;
	created_at: number;
	updated_at: number;
	terminal_at: number | null;
	durable: true;
	replay?: {
		content: string;
		cursor: number;
		status: ChatGenerationStatus;
		degraded: boolean;
		expires_at: number;
	} | null;
};

export type ChatGenerationReplayTail = {
	generation_id: string;
	chat_id: string;
	message_id: string;
	cursor: number;
	status: ChatGenerationStatus;
	degraded: boolean;
	events: Array<{
		sequence: number;
		type: 'content' | 'terminal' | 'invalid';
		payload: Record<string, unknown>;
	}>;
	expires_at: number;
};

export type TaskStopReceipt = {
	status:
		| 'accepted'
		| 'observed'
		| 'already_terminal'
		| 'already_completed'
		| 'different_generation';
	accepted: boolean;
	observed: boolean;
	terminal: boolean;
	stopped: boolean;
	durable: boolean;
	task_id: string | null;
	generation_id: string;
	chat_id: string | null;
	message_id: string | null;
	generation?: ChatGeneration;
};

export const stopTask = async (token: string, id: string, binding?: TaskStopBinding) => {
	try {
		return await appClient.post<TaskStopReceipt>(
			`/api/tasks/stop/${encodeURIComponent(id)}`,
			binding,
			{ token }
		);
	} catch (err) {
		logger.error('apis', 'Stop Task failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const stopChatGeneration = async (
	token: string,
	generationId: string,
	binding: TaskStopBinding
) => {
	try {
		return await appClient.post<TaskStopReceipt>(
			`/api/chat/generations/${encodeURIComponent(generationId)}/stop`,
			binding,
			{ token }
		);
	} catch (err) {
		logger.error(
			'apis',
			'Stop Chat Generation failed',
			err instanceof Error ? err : undefined,
			err
		);
		throw err;
	}
};

export const getChatGeneration = async (
	token: string,
	generationId: string,
	binding: TaskStopBinding
) => {
	const params = new URLSearchParams({
		chat_id: binding.chat_id,
		message_id: binding.message_id
	});
	return appClient.get<ChatGeneration>(
		`/api/chat/generations/${encodeURIComponent(generationId)}?${params.toString()}`,
		{ token }
	);
};

export const getActiveChatGenerations = async (token: string, chatId: string) => {
	const normalizedChatId = chatId.trim();
	// There is no generation scope until a persisted chat ID exists. Returning
	// an empty result keeps a route transition from requesting `/api/chat//…`,
	// which otherwise receives Vite's HTML fallback instead of JSON.
	if (!normalizedChatId) return { generations: [] };

	return appClient.get<{ generations: ChatGeneration[] }>(
		`/api/chat/${encodeURIComponent(normalizedChatId)}/generations`,
		{ token }
	);
};

export const getChatGenerationEvents = async (
	token: string,
	generationId: string,
	binding: TaskStopBinding,
	after = 0,
	limit = 256
) => {
	const params = new URLSearchParams({
		chat_id: binding.chat_id,
		message_id: binding.message_id,
		after: String(after),
		limit: String(limit)
	});
	return appClient.get<ChatGenerationReplayTail>(
		`/api/chat/generations/${encodeURIComponent(generationId)}/events?${params.toString()}`,
		{ token }
	);
};

// ---------------------------------------------------------------------------
// Tool servers
// ---------------------------------------------------------------------------

export const getToolServerData = async (token: string, url: string) => {
	let error = null;

	const res = await fetch(`${url}/openapi.json`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			logger.error(
				'apis',
				'Get Tool Server Data failed',
				err instanceof Error ? err : undefined,
				err
			);
			if ('detail' in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return {
		openapi: res,
		info: res.info,
		specs: convertOpenApiToToolPayload(res)
	};
};

export const getToolServersData = async (i18n, servers: object[]) => {
	return (
		await Promise.all(
			servers
				.filter((server) => server?.config?.enable)
				.map(async (server) => {
					const data = await getToolServerData(server?.key, server?.url).catch(() => {
						toast.error(
							i18n.t(`Failed to connect to {{URL}} OpenAPI tool server`, {
								URL: server?.url
							})
						);
						return null;
					});

					if (data) {
						const { openapi, info, specs } = data;
						return {
							url: server?.url,
							openapi: openapi,
							info: info,
							specs: specs
						};
					}
				})
		)
	).filter((server) => server);
};

export const executeToolServer = async (
	token: string,
	url: string,
	name: string,
	params: Record<string, unknown>,
	serverData: { openapi: Record<string, unknown>; info: Record<string, unknown>; specs: unknown }
) => {
	let error: string | null;

	try {
		const matchingRoute = Object.entries(serverData.openapi.paths as Record<string, unknown>).find(
			(entry) =>
				Object.entries(entry[1] as Record<string, unknown>).some(
					(entry2) => (entry2[1] as Record<string, unknown>).operationId === name
				)
		);

		if (!matchingRoute) {
			throw new Error(`No matching route found for operationId: ${name}`);
		}

		const [routePath, methods] = matchingRoute;

		const methodEntry = Object.entries(methods as Record<string, unknown>).find(
			(entry) => (entry[1] as Record<string, unknown>).operationId === name
		);

		if (!methodEntry) {
			throw new Error(`No matching method found for operationId: ${name}`);
		}

		const [httpMethod, operation]: [string, Record<string, unknown>] = methodEntry;

		const pathParams: Record<string, unknown> = {};
		const queryParams: Record<string, unknown> = {};
		let bodyParams: Record<string, unknown> = {};

		if (operation.parameters) {
			(operation.parameters as Array<Record<string, unknown>>).forEach((param) => {
				const paramName = param.name as string;
				const paramIn = param.in as string;
				if (Object.hasOwn(params, paramName)) {
					if (paramIn === 'path') {
						pathParams[paramName] = params[paramName];
					} else if (paramIn === 'query') {
						queryParams[paramName] = params[paramName];
					}
				}
			});
		}

		let finalUrl = `${url}${routePath}`;

		Object.entries(pathParams).forEach(([key, value]) => {
			finalUrl = finalUrl.replace(new RegExp(`{${key}}`, 'g'), encodeURIComponent(value));
		});

		if (Object.keys(queryParams).length > 0) {
			const queryString = new URLSearchParams(
				Object.entries(queryParams).map(([k, v]) => [k, String(v)])
			).toString();
			finalUrl += `?${queryString}`;
		}

		if (operation.requestBody && operation.requestBody.content) {
			if (params !== undefined) {
				bodyParams = params;
			} else {
				throw new Error(`Request body expected for operation '${name}' but none found.`);
			}
		}

		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		};

		const requestOptions: RequestInit = {
			method: httpMethod.toUpperCase(),
			headers
		};

		if (['post', 'put', 'patch'].includes(httpMethod.toLowerCase()) && operation.requestBody) {
			requestOptions.body = JSON.stringify(bodyParams);
		}

		const res = await fetch(finalUrl, requestOptions);
		if (!res.ok) {
			const resText = await res.text();
			throw new Error(`HTTP error! Status: ${res.status}. Message: ${resText}`);
		}

		return await res.json();
	} catch (err: unknown) {
		error = err instanceof Error ? err.message : String(err);
		logger.error('apis', 'API Request Error:', error instanceof Error ? error : undefined, error);
		return { error };
	}
};

// ---------------------------------------------------------------------------
// Task config
// ---------------------------------------------------------------------------

export const getTaskConfig = async (token: string = '') => {
	try {
		return await apiClient.get('/tasks/config', { token });
	} catch (err) {
		logger.error('apis', 'Get Task Config failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const updateTaskConfig = async (token: string, config: object) => {
	try {
		return await apiClient.post('/tasks/config/update', config, { token });
	} catch (err) {
		logger.error('apis', 'Update Task Config failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

// ---------------------------------------------------------------------------
// AI generation helpers
// ---------------------------------------------------------------------------

export const generateTitle = async (
	token: string = '',
	model: string,
	messages: string[],
	chat_id?: string
) => {
	const res = await taskCompletion(
		'title',
		token,
		{ model, messages, ...(chat_id && { chat_id }) },
		'Generate Title failed'
	);

	const content = res?.choices?.[0]?.message?.content?.replace(/["']/g, '');
	return content ? removeEmojis(content) : 'New Chat';
};

export const generateTags = async (
	token: string = '',
	model: string,
	messages: string,
	chat_id?: string
) => {
	const res = await taskCompletion(
		'tags',
		token,
		{ model, messages, ...(chat_id && { chat_id }) },
		'Generate Tags failed'
	);

	try {
		const response = res?.choices?.[0]?.message?.content ?? '';
		const sanitizedResponse = response.replace(/[''`]/g, '"');
		const tags = extractJsonField<string[]>(sanitizedResponse, 'tags');
		return Array.isArray(tags) ? tags : [];
	} catch (e) {
		logger.error('apis', 'Failed to parse response: ', e instanceof Error ? e : undefined, e);
		return [];
	}
};

export const generateEmoji = async (
	token: string = '',
	model: string,
	prompt: string,
	chat_id?: string
) => {
	const res = await taskCompletion(
		'emoji',
		token,
		{ model, prompt, ...(chat_id && { chat_id }) },
		'Generate Emoji failed'
	);

	const response = res?.choices?.[0]?.message?.content?.replace(/["']/g, '') ?? null;

	if (response) {
		if (/\p{Extended_Pictographic}/u.test(response)) {
			return response.match(/\p{Extended_Pictographic}/gu)?.[0] ?? null;
		}
	}

	return null;
};

export const generateQueries = async (
	token: string = '',
	model: string,
	messages: object[],
	prompt: string,
	type: string = 'web_search'
) => {
	const res = await taskCompletion(
		'queries',
		token,
		{ model, messages, prompt, type },
		'Generate Queries failed'
	);

	const response = res?.choices?.[0]?.message?.content ?? '';

	try {
		const queries = extractJsonField<string[]>(response, 'queries');
		return Array.isArray(queries) ? queries : [response];
	} catch (e) {
		logger.error('apis', 'Failed to parse response: ', e instanceof Error ? e : undefined, e);
		return [response];
	}
};

export const generateAutoCompletion = async (
	token: string = '',
	model: string,
	prompt: string,
	messages?: object[],
	type: string = 'search query'
) => {
	const res = await taskCompletion(
		'auto',
		token,
		{ model, prompt, ...(messages && { messages }), type, stream: false },
		'Generate Auto Completion failed'
	);

	const response = res?.choices?.[0]?.message?.content ?? '';

	try {
		return extractJsonField<string>(response, 'text') ?? '';
	} catch (e) {
		logger.error('apis', 'Failed to parse response: ', e instanceof Error ? e : undefined, e);
		return '';
	}
};

export const generateMoACompletion = async (
	token: string = '',
	model: string,
	prompt: string,
	responses: string[]
) => {
	const controller = new AbortController();

	try {
		const res = await apiClient.post<Response>(
			'/tasks/moa/completions',
			{
				model: model,
				prompt: prompt,
				responses: responses,
				stream: true
			},
			{ token, rawResponse: true, signal: controller.signal }
		);
		return [res, controller];
	} catch (err) {
		logger.error(
			'apis',
			'Generate MoA Completion failed',
			err instanceof Error ? err : undefined,
			err
		);
		throw err;
	}
};

// ---------------------------------------------------------------------------
// Pipelines
// ---------------------------------------------------------------------------

export const getPipelinesList = async (token: string = '') => {
	try {
		const res = await apiClient.get<{ data?: object[] }>('/pipelines/list', { token });
		return res?.data ?? [];
	} catch (err) {
		logger.error('apis', 'Get Pipelines List failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const uploadPipeline = async (token: string, file: File, urlIdx: string) => {
	const formData = new FormData();
	formData.append('file', file);
	formData.append('urlIdx', urlIdx);

	try {
		return await apiClient.post('/pipelines/upload', formData, { token });
	} catch (err) {
		logger.error('apis', 'Upload Pipeline failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const downloadPipeline = async (token: string, url: string, urlIdx: string) => {
	try {
		return await apiClient.post(
			'/pipelines/add',
			{
				url: url,
				urlIdx: urlIdx
			},
			{ token }
		);
	} catch (err) {
		logger.error('apis', 'Download Pipeline failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const deletePipeline = async (token: string, id: string, urlIdx: string) => {
	try {
		return await apiClient.del(
			'/pipelines/delete',
			{
				id: id,
				urlIdx: urlIdx
			},
			{ token }
		);
	} catch (err) {
		logger.error('apis', 'Delete Pipeline failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const getPipelines = async (token: string, urlIdx?: string) => {
	const params = urlIdx !== undefined ? `?urlIdx=${encodeURIComponent(urlIdx)}` : '';
	try {
		const res = await apiClient.get<{ data?: object[] }>(`/pipelines/${params}`, { token });
		return res?.data ?? [];
	} catch (err) {
		logger.error('apis', 'Get Pipelines failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const getPipelineValves = async (token: string, pipeline_id: string, urlIdx: string) => {
	const params = urlIdx !== undefined ? `?urlIdx=${encodeURIComponent(urlIdx)}` : '';
	try {
		return await apiClient.get(`/pipelines/${pipeline_id}/valves${params}`, { token });
	} catch (err) {
		logger.error('apis', 'Get Pipeline Valves failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const getPipelineValvesSpec = async (token: string, pipeline_id: string, urlIdx: string) => {
	const params = urlIdx !== undefined ? `?urlIdx=${encodeURIComponent(urlIdx)}` : '';
	try {
		return await apiClient.get(`/pipelines/${pipeline_id}/valves/spec${params}`, { token });
	} catch (err) {
		logger.error(
			'apis',
			'Get Pipeline Valves Spec failed',
			err instanceof Error ? err : undefined,
			err
		);
		throw err;
	}
};

export const updatePipelineValves = async (
	token: string = '',
	pipeline_id: string,
	valves: object,
	urlIdx: string
) => {
	const params = urlIdx !== undefined ? `?urlIdx=${encodeURIComponent(urlIdx)}` : '';
	try {
		return await apiClient.post(`/pipelines/${pipeline_id}/valves/update${params}`, valves, {
			token
		});
	} catch (err) {
		logger.error(
			'apis',
			'Update Pipeline Valves failed',
			err instanceof Error ? err : undefined,
			err
		);
		throw err;
	}
};

// ---------------------------------------------------------------------------
// Config (app-level)
// ---------------------------------------------------------------------------

export interface AppBackendConfig {
	user_count?: number;
	version?: string;
	[key: string]: unknown;
}

export const getBackendConfig = async (signal?: AbortSignal): Promise<AppBackendConfig> => {
	try {
		return await appClient.get<AppBackendConfig>('/api/config', { signal });
	} catch (err) {
		logger.error('apis', 'Get Backend Config failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const getChangelog = async () => {
	return appClient.get('/api/changelog');
};

export const getVersionUpdates = async (
	token: string
): Promise<{ current?: string; latest?: string }> => {
	return appClient.get<{ current?: string; latest?: string }>('/api/version/updates', { token });
};

export const getModelFilterConfig = async (token: string) => {
	return appClient.get('/api/config/model/filter', { token });
};

export const updateModelFilterConfig = async (
	token: string,
	enabled: boolean,
	models: string[]
) => {
	try {
		return await appClient.post(
			'/api/config/model/filter',
			{
				enabled: enabled,
				models: models
			},
			{ token }
		);
	} catch (err) {
		logger.error(
			'apis',
			'Update Model Filter Config failed',
			err instanceof Error ? err : undefined,
			err
		);
		throw err;
	}
};

export const getWebhookUrl = async (token: string) => {
	try {
		const res = await appClient.get<{ url?: string }>('/api/webhook', { token });
		return res.url;
	} catch (err) {
		logger.error('apis', 'Get Webhook Url failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const updateWebhookUrl = async (token: string, url: string) => {
	try {
		const res = await appClient.post<{ url?: string }>(
			'/api/webhook',
			{
				url: url
			},
			{ token }
		);
		return res.url;
	} catch (err) {
		logger.error('apis', 'Update Webhook Url failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export const getCommunitySharingEnabledStatus = async (token: string) => {
	return appClient.get('/api/community_sharing', { token });
};

export const toggleCommunitySharingEnabledStatus = async (token: string) => {
	try {
		return await appClient.get('/api/community_sharing/toggle', { token });
	} catch (err) {
		logger.error(
			'apis',
			'Toggle Community Sharing Enabled Status failed',
			err instanceof Error ? err : undefined,
			err
		);
		throw err;
	}
};

export const getModelConfig = async (token: string): Promise<GlobalModelConfig> => {
	try {
		const res = await appClient.get<{ models?: GlobalModelConfig }>('/api/config/models', {
			token
		});
		return res.models ?? [];
	} catch (err) {
		logger.error('apis', 'Get Model Config failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};

export interface ModelConfig {
	id: string;
	name: string;
	meta: ModelMeta;
	base_model_id?: string;
	params: ModelParams;
}

export interface ModelMeta {
	description?: string;
	capabilities?: object;
	profile_image_url?: string;
	hidden?: boolean;
	toolIds?: string[];
	tags?: { name: string }[];
	suggestion_prompts?: { content: string }[] | null;
}

export type ModelParams = Record<string, unknown>;

export type GlobalModelConfig = ModelConfig[];

export const updateModelConfig = async (token: string, config: GlobalModelConfig) => {
	try {
		return await appClient.post(
			'/api/config/models',
			{
				models: config
			},
			{ token }
		);
	} catch (err) {
		logger.error('apis', 'Update Model Config failed', err instanceof Error ? err : undefined, err);
		throw err;
	}
};
