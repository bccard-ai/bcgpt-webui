import {
	APP_BASE_URL,
	API_BASE_URL,
	OLLAMA_API_BASE_URL,
	OPENAI_API_BASE_URL,
	AUDIO_API_BASE_URL,
	IMAGES_API_BASE_URL,
	RETRIEVAL_API_BASE_URL,
	AGENTS_API_BASE_URL
} from '$lib/constants';
import type { ZodType } from 'zod';

export interface RequestOptions extends RequestInit {
	timeout?: number;
	rawResponse?: boolean;
	token?: string;
	responseSchema?: ZodType;
}

export class ApiError extends Error {
	readonly status: number;
	readonly detail: string;

	constructor(status: number, detail: string) {
		super(detail);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
	}
}

export class ApiClient {
	private baseUrl: string;
	private defaultTimeout = 30_000;

	constructor(baseUrl: string = API_BASE_URL) {
		this.baseUrl = baseUrl;
	}

	async get<T>(path: string, opts?: RequestOptions): Promise<T> {
		return this.request<T>('GET', path, undefined, opts);
	}

	async post<T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> {
		return this.request<T>('POST', path, body, opts);
	}

	async put<T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> {
		return this.request<T>('PUT', path, body, opts);
	}

	async patch<T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> {
		return this.request<T>('PATCH', path, body, opts);
	}

	async del<T>(path: string, body?: unknown, opts?: RequestOptions): Promise<T> {
		return this.request<T>('DELETE', path, body, opts);
	}

	private async request<T>(
		method: string,
		path: string,
		body?: unknown,
		opts?: RequestOptions
	): Promise<T> {
		const {
			timeout: timeoutMs = this.defaultTimeout,
			rawResponse = false,
			token,
			signal: externalSignal,
			headers: customHeaders,
			responseSchema,
			...passThrough
		} = opts ?? {};

		const url = this.resolveUrl(path);

		const controller = new AbortController();
		const timeoutId = setTimeout(
			() => controller.abort(new DOMException('Request timed out', 'TimeoutError')),
			timeoutMs
		);

		if (externalSignal) {
			if (externalSignal.aborted) {
				clearTimeout(timeoutId);
				controller.abort();
			} else {
				externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
			}
		}

		try {
			const headers = this.buildHeaders(token, customHeaders);

			const init: RequestInit = {
				...passThrough,
				method,
				headers,
				credentials: 'include',
				signal: controller.signal
			};

			if (body !== undefined && method !== 'GET' && method !== 'HEAD') {
				if (body instanceof FormData) {
					if (headers instanceof Headers) {
						headers.delete('Content-Type');
					} else {
						delete (headers as Record<string, string>)['Content-Type'];
					}
					init.body = body;
				} else {
					init.body = JSON.stringify(body);
				}
			}

			const response = await fetch(url, init);

			if (!response.ok) {
				throw await this.extractError(response);
			}

			if (rawResponse) {
				return response as unknown as T;
			}

			const data: T = (await response.json()) as T;

			if (responseSchema) {
				const result = responseSchema.safeParse(data);
				if (!result.success) {
					console.warn(
						`[ApiClient] Response schema validation failed for ${method} ${path}:`,
						result.error
					);
				}
			}

			return data;
		} finally {
			clearTimeout(timeoutId);
		}
	}

	private resolveUrl(path: string): string {
		if (path.startsWith('http://') || path.startsWith('https://')) {
			return path;
		}
		return `${this.baseUrl}/${path.replace(/^\/+/, '')}`;
	}

	private buildHeaders(token?: string, customHeaders?: HeadersInit): Headers {
		const headers = new Headers({
			'Content-Type': 'application/json',
			Accept: 'application/json'
		});

		const resolvedToken = token ?? this.getStoredToken();
		if (resolvedToken) {
			headers.set('Authorization', `Bearer ${resolvedToken}`);
		} else {
			const csrfToken = this.getCsrfToken();
			if (csrfToken) {
				headers.set('X-CSRF-Token', csrfToken);
			}
		}

		if (customHeaders) {
			if (customHeaders instanceof Headers) {
				customHeaders.forEach((value, key) => headers.set(key, value));
			} else if (Array.isArray(customHeaders)) {
				for (const [key, value] of customHeaders) {
					headers.set(key, value);
				}
			} else {
				for (const [key, value] of Object.entries(customHeaders)) {
					headers.set(key, value);
				}
			}
		}

		return headers;
	}

	private getStoredToken(): string | null {
		return null;
	}

	private getCsrfToken(): string | null {
		try {
			const match = document.cookie
				.split(';')
				.map((c) => c.trim())
				.find((c) => c.startsWith('csrf_token='));
			return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null;
		} catch {
			return null;
		}
	}

	private async extractError(response: Response): Promise<ApiError> {
		let detail = response.statusText;

		try {
			const body: unknown = await response.json();
			if (typeof body === 'object' && body !== null) {
				const obj = body as Record<string, unknown>;
				detail =
					(typeof obj.detail === 'string' ? obj.detail : null) ??
					(typeof obj.message === 'string' ? obj.message : null) ??
					response.statusText;
			} else if (typeof body === 'string') {
				detail = body;
			}
		} catch {
			// statusText already set as default
		}

		return new ApiError(response.status, detail);
	}
}

/** Client for endpoints under `/api/` (not `/api/v1/`). Uses `APP_BASE_URL` directly. */
export const appClient = new ApiClient(APP_BASE_URL);

/** Singleton client pre-configured with `API_BASE_URL` (`/api/v1`). */
export const apiClient = new ApiClient();

/** Client for Ollama proxy endpoints (`/ollama`). */
export const ollamaClient = new ApiClient(OLLAMA_API_BASE_URL);

/** Client for OpenAI-compatible proxy endpoints (`/openai`). */
export const openaiClient = new ApiClient(OPENAI_API_BASE_URL);

/** Client for audio endpoints (`/api/v1/audio`). */
export const audioClient = new ApiClient(AUDIO_API_BASE_URL);

/** Client for image generation endpoints (`/api/v1/images`). */
export const imagesClient = new ApiClient(IMAGES_API_BASE_URL);

/** Client for retrieval/RAG endpoints (`/api/v1/retrieval`). */
export const retrievalClient = new ApiClient(RETRIEVAL_API_BASE_URL);

/** Client for agent endpoints (`/api/v1/agents`). */
export const agentsClient = new ApiClient(AGENTS_API_BASE_URL);
