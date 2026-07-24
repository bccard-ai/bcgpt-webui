/**
 * @fileoverview Web Worker for Kokoro TTS (Text-to-Speech) synthesis.
 *
 * Loads a Kokoro TTS model from Hugging Face using either WebGPU (when
 * available) or WASM as the inference backend. Supports initialisation,
 * audio generation, and status queries via `postMessage` commands.
 *
 * ## Message protocol
 *
 * **Inbound** (`event.data`):
 * - `{ type: 'init', payload: { model_id?, dtype } }` — Load the TTS model.
 * - `{ type: 'generate', payload: { text, voice } }` — Synthesise audio.
 * - `{ type: 'status' }` — Query initialisation state.
 *
 * **Outbound** (`self.postMessage`):
 * - `{ status: 'init:start' | 'init:complete' | 'init:error' }`
 * - `{ status: 'generate:start' | 'generate:complete', audioUrl }`
 * - `{ status: 'generate:error', error }`
 * - `{ status: 'status:check', initialized }`
 *
 * @module workers/kokoro.worker
 */

import { env } from '@huggingface/transformers';
import { KokoroTTS } from 'kokoro-js';

// TODO: Below doesn't work as expected, need to investigate further
env.backends.onnx.wasm.wasmPaths = '/wasm/';

/** Kokoro TTS model instance. */
let tts: KokoroTTS | null = null;

/** Whether the model has been successfully loaded. */
let isInitialized = false;

/** Default Hugging Face model ID for Kokoro TTS. */
const DEFAULT_MODEL_ID = 'onnx-community/Kokoro-82M-v1.0-ONNX';

/**
 * Main message handler — dispatches to init / generate / status handlers.
 */
self.onmessage = async (event: MessageEvent) => {
	const { type, payload } = event.data;

	if (type === 'init') {
		const { model_id: modelIdParam, dtype: dtypeParam } = payload;
		const dtype = dtypeParam;
		const model_id = modelIdParam || DEFAULT_MODEL_ID;

		self.postMessage({ status: 'init:start' });

		try {
			tts = await KokoroTTS.from_pretrained(model_id, {
				dtype,
				device: navigator?.gpu ? 'webgpu' : 'wasm'
			});
			isInitialized = true;
			self.postMessage({ status: 'init:complete' });
		} catch (error) {
			isInitialized = false;
			self.postMessage({ status: 'init:error', error: (error as Error).message });
		}
	}

	if (type === 'generate') {
		if (!isInitialized || !tts) {
			self.postMessage({ status: 'generate:error', error: 'TTS model not initialized' });
			return;
		}

		const { text, voice } = payload;
		self.postMessage({ status: 'generate:start' });

		try {
			const rawAudio = await tts.generate(text, { voice });
			const blob = await rawAudio.toBlob();
			const blobUrl = URL.createObjectURL(blob);
			self.postMessage({ status: 'generate:complete', audioUrl: blobUrl });
		} catch (error) {
			self.postMessage({ status: 'generate:error', error: (error as Error).message });
		}
	}

	if (type === 'status') {
		self.postMessage({ status: 'status:check', initialized: isInitialized });
	}
};
