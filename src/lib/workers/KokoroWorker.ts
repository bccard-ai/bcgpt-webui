/**
 * @fileoverview Kokoro TTS Worker manager class.
 *
 * Wraps the Kokoro TTS Web Worker in a typed, promise-based API with
 * request queuing for sequential audio generation.
 *
 * @module workers/KokoroWorker
 */

import WorkerInstance from '$lib/workers/kokoro.worker?worker';
import { logger } from '$lib/utils/logger';

/** A pending TTS request in the processing queue. */
interface TTSRequest {
	/** Text to synthesise. */
	text: string;
	/** Voice identifier. */
	voice: string;
	/** Resolves with the blob URL of the generated audio. */
	resolve: (value: string) => void;
	/** Rejects on generation failure. */
	reject: (reason: unknown) => void;
}

/**
 * Manages the lifecycle of a Kokoro TTS Web Worker.
 *
 * Features:
 * - Lazy initialisation with a single underlying `Worker`.
 * - Sequential request queue — each `generate()` call is processed in order.
 * - Clean teardown via `terminate()`.
 *
 * @example
 * ```ts
 * const worker = new KokoroWorker('fp32');
 * await worker.init();
 * const audioUrl = await worker.generate({ text: 'Hello world', voice: 'af_bella' });
 * // … use audioUrl …
 * worker.terminate();
 * ```
 */
export class KokoroWorker {
	private worker: Worker | null = null;
	private initialized: boolean = false;
	private dtype: string;
	private requestQueue: TTSRequest[] = [];
	private processing: boolean = false;

	/**
	 * @param dtype - Data type for model inference (default `'fp32'`).
	 */
	constructor(dtype: string = 'fp32') {
		this.dtype = dtype;
	}

	/**
	 * Initialise the underlying Web Worker and load the Kokoro TTS model.
	 *
	 * No-op if already initialised.
	 *
	 * @throws When the model fails to load.
	 */
	public async init(): Promise<void> {
		if (this.worker) {
			logger.warn('kokoro', 'KokoroWorker is already initialized.');
			return;
		}

		this.worker = new WorkerInstance();

		// Handle worker messages for queued request resolution
		this.worker.onmessage = (event: MessageEvent) => {
			const { status, error, audioUrl } = event.data;

			if (status === 'init:complete') {
				this.initialized = true;
			} else if (status === 'init:error') {
				logger.error('kokoro', 'KokoroWorker init failed', undefined, error);
				this.initialized = false;
			} else if (status === 'generate:complete') {
				const request = this.requestQueue.shift();
				if (request) {
					request.resolve(audioUrl);
					this.processNextRequest();
				}
			} else if (status === 'generate:error') {
				const request = this.requestQueue.shift();
				if (request) {
					request.reject(new Error(error));
					this.processNextRequest();
				}
			}
		};

		// Wait for the init handshake to complete
		return new Promise<void>((resolve, reject) => {
			this.worker!.postMessage({
				type: 'init',
				payload: { dtype: this.dtype }
			});

			const handleMessage = (event: MessageEvent) => {
				if (event.data.status === 'init:complete') {
					this.worker!.removeEventListener('message', handleMessage);
					this.initialized = true;
					resolve();
				} else if (event.data.status === 'init:error') {
					this.worker!.removeEventListener('message', handleMessage);
					reject(new Error(event.data.error));
				}
			};

			this.worker!.addEventListener('message', handleMessage);
		});
	}

	/**
	 * Generate audio for the given text using the specified voice.
	 *
	 * Requests are queued and processed sequentially. Resolves with a
	 * blob URL that can be set as an `<audio>` element's `src`.
	 *
	 * @param params - `{ text, voice }` parameters.
	 * @returns Promise resolving to the audio blob URL.
	 * @throws When the worker is not initialised or generation fails.
	 */
	public async generate({ text, voice }: { text: string; voice: string }): Promise<string> {
		if (!this.initialized || !this.worker) {
			throw new Error('KokoroTTS Worker is not initialized yet.');
		}

		return new Promise<string>((resolve, reject) => {
			this.requestQueue.push({ text, voice, resolve, reject });
			if (!this.processing) {
				this.processNextRequest();
			}
		});
	}

	/**
	 * Process the next request in the queue.
 *
 * If the queue is empty, sets `processing` to `false`.
	 */
	private processNextRequest(): void {
		if (this.requestQueue.length === 0) {
			this.processing = false;
			return;
		}

		this.processing = true;
		const { text, voice } = this.requestQueue[0]; // Peek — don't remove until complete
		this.worker!.postMessage({ type: 'generate', payload: { text, voice } });
	}

	/**
	 * Terminate the underlying Web Worker and reset all state.
	 *
	 * Safe to call multiple times; subsequent calls are no-ops.
	 */
	public terminate(): void {
		if (this.worker) {
			this.worker.terminate();
			this.worker = null;
			this.initialized = false;
			this.requestQueue = [];
			this.processing = false;
		}
	}
}
