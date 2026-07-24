/*
 * SPDX-FileCopyrightText: 2026 BC Card
 * SPDX-License-Identifier: Apache-2.0
 */

import { get } from 'svelte/store';
import { synthesizeOpenAISpeech } from '$lib/apis/audio';
import { config, settings, TTSWorker } from '$lib/stores';
import { logger } from '$lib/utils/logger';
import { getMessageContentParts } from '$lib/utils/text';
import { KokoroWorker } from '$lib/workers/KokoroWorker';

interface CreateMessageTTSConfig {
	getMessageContent: () => string;
	toastInfo: (msg: string) => void;
	toastError: (msg: string) => void;
}

export function createMessageTTS(config_deps: CreateMessageTTSConfig) {
	let speaking = $state(false);
	let loadingSpeech = $state(false);
	let speakingIdx: number | undefined;
	let audioParts: Record<number, HTMLAudioElement | null> = {};

	function playAudio(idx: number): Promise<void> {
		return new Promise((res) => {
			speakingIdx = idx;
			const audio = audioParts[idx];
			if (!audio) return res();

			audio.play();
			audio.onended = async () => {
				await new Promise((r) => setTimeout(r, 300));
				if (Object.keys(audioParts).length - 1 === idx) {
					speaking = false;
				}
				res();
			};
		});
	}

	async function toggleSpeakMessage(): Promise<void> {
		if (speaking) {
			try {
				speechSynthesis.cancel();
				if (speakingIdx !== undefined && audioParts[speakingIdx]) {
					audioParts[speakingIdx]!.pause();
					audioParts[speakingIdx]!.currentTime = 0;
				}
			} catch {
				// Speech synthesis may fail on some browsers
			}
			speaking = false;
			speakingIdx = undefined;
			return;
		}

		const content = config_deps.getMessageContent();
		if (!content.trim().length) {
			config_deps.toastInfo('No content to speak');
			return;
		}

		speaking = true;

		if (get(config).audio.tts.engine === '') {
			let voices: SpeechSynthesisVoice[] = [];
			const getVoicesLoop = setInterval(() => {
				voices = speechSynthesis.getVoices();
				if (voices.length > 0) {
					clearInterval(getVoicesLoop);

					const voice =
						voices
							?.filter(
								(v) =>
									v.voiceURI ===
									(get(settings)?.audio?.tts?.voice ?? get(config)?.audio?.tts?.voice)
							)
							?.at(0) ?? undefined;

					const speak = new SpeechSynthesisUtterance(content);
					speak.rate = get(settings).audio?.tts?.playbackRate ?? 1;

					speak.onend = () => {
						speaking = false;
						if (get(settings).conversationMode) {
							document.getElementById('voice-input-button')?.click();
						}
					};

					if (voice) speak.voice = voice;
					speechSynthesis.speak(speak);
				}
			}, 100);
		} else {
			await handleExternalTTS(content);
		}
	}

	async function handleExternalTTS(content: string): Promise<void> {
		loadingSpeech = true;

		const parts: string[] = getMessageContentParts(
			content,
			get(config)?.audio?.tts?.split_on ?? 'punctuation'
		);

		if (!parts.length) {
			config_deps.toastInfo('No content to speak');
			speaking = false;
			loadingSpeech = false;
			return;
		}

		audioParts = parts.reduce(
			(acc, _sentence, idx) => {
				acc[idx] = null;
				return acc;
			},
			{} as typeof audioParts
		);

		const lastPlayedAudioPromise = Promise.resolve();

		if (get(settings).audio?.tts?.engine === 'browser-kokoro') {
			await synthesizeViaKokoro(parts, lastPlayedAudioPromise);
		} else {
			await synthesizeViaOpenAI(parts, lastPlayedAudioPromise);
		}
	}

	async function synthesizeViaKokoro(parts: string[], lastPromise: Promise<void>): Promise<void> {
		if (!get(TTSWorker)) {
			await TTSWorker.set(
				new KokoroWorker({
					dtype: get(settings).audio?.tts?.engineConfig?.dtype ?? 'fp32'
				})
			);
			await get(TTSWorker).init();
		}

		for (const [idx, sentence] of parts.entries()) {
			const blob = await get(TTSWorker)
				.generate({
					text: sentence,
					voice: get(settings)?.audio?.tts?.voice ?? get(config)?.audio?.tts?.voice
				})
				.catch((error: unknown) => {
					logger.error('chat', 'TTS synthesis error', undefined, error);
					config_deps.toastError(`${error}`);
					speaking = false;
					loadingSpeech = false;
				});

			if (blob) {
				const audio = new Audio(blob);
				audio.playbackRate = get(settings).audio?.tts?.playbackRate ?? 1;
				audioParts[idx] = audio;
				loadingSpeech = false;
				lastPromise = lastPromise.then(() => playAudio(idx));
			}
		}
	}

	async function synthesizeViaOpenAI(parts: string[], lastPromise: Promise<void>): Promise<void> {
		for (const [idx, sentence] of parts.entries()) {
			const res = await synthesizeOpenAISpeech(
				'',
				get(settings)?.audio?.tts?.defaultVoice === get(config).audio.tts.voice
					? (get(settings)?.audio?.tts?.voice ?? get(config)?.audio?.tts?.voice)
					: get(config)?.audio?.tts?.voice,
				sentence
			).catch((error: unknown) => {
				logger.error('chat', 'TTS synthesis error', undefined, error);
				config_deps.toastError(`${error}`);
				speaking = false;
				loadingSpeech = false;
			});

			if (res) {
				const blob = await res.blob();
				const blobUrl = URL.createObjectURL(blob);
				const audio = new Audio(blobUrl);
				audio.playbackRate = get(settings).audio?.tts?.playbackRate ?? 1;
				audioParts[idx] = audio;
				loadingSpeech = false;
				lastPromise = lastPromise.then(() => playAudio(idx));
			}
		}
	}

	return {
		get speaking() {
			return speaking;
		},
		get loadingSpeech() {
			return loadingSpeech;
		},
		toggleSpeakMessage
	};
}
