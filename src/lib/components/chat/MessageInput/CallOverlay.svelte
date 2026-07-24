<script lang="ts">
	import { get } from 'svelte/store';
	import { logger } from '$lib/utils/logger';
	import { config, models, settings, showCallOverlay, TTSWorker } from '$lib/stores';
	import { onMount, tick, getContext, onDestroy } from 'svelte';

	import { blobToFile } from '$lib/utils';
	import { generateEmoji } from '$lib/apis';
	import { synthesizeOpenAISpeech, transcribeAudio } from '$lib/apis/audio';

	import { toast } from 'svelte-sonner';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import VideoInputMenu from './CallOverlay/VideoInputMenu.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import type { KokoroWorker } from '$lib/workers/KokoroWorker';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Event target for chat streaming events */
		eventTarget: EventTarget;
		/** Submit a transcribed prompt */
		submitPrompt: (prompt: string, options?: Record<string, unknown>) => Promise<unknown>;
		/** Stop the current response */
		stopResponse: () => void;
		/** Files attached to the chat (bindable, for camera screenshots) */
		files: Record<string, unknown>[];
		/** Current chat ID */
		chatId: string;
		/** The model ID being used */
		modelId: string;
		/** Callback when the overlay is closed */
		onClose?: (...args: unknown[]) => void;
	}

	let {
		eventTarget,
		submitPrompt,
		stopResponse,
		// eslint-disable-next-line no-useless-assignment
		files = $bindable(),
		chatId,
		modelId,
		onClose = () => {}
	}: Props = $props();

	// ---------------------------------------------------------------------------
	// Wake Lock
	// ---------------------------------------------------------------------------

	let wakeLock: WakeLockSentinel | null = null;

	/** Request a screen wake lock to prevent the display from sleeping during a call */
	const requestWakeLock = async (): Promise<void> => {
		try {
			wakeLock = await navigator.wakeLock.request('screen');
			wakeLock.addEventListener('release', () => {
				// Wake lock released
			});
		} catch {
			// Wake Lock may fail due to battery conditions
		}
	};

	// ---------------------------------------------------------------------------
	// Model State
	// ---------------------------------------------------------------------------

	let model = $state<Record<string, unknown> | null>(null);

	// ---------------------------------------------------------------------------
	// Call State
	// ---------------------------------------------------------------------------

	let loading = $state(false);
	let confirmed = false;
	let assistantSpeaking = $state(false);
	let emoji = $state<string | null>(null);

	// ---------------------------------------------------------------------------
	// Camera State
	// ---------------------------------------------------------------------------

	let camera = $state(false);
	let cameraStream = $state<MediaStream | null>(null);
	let videoInputDevices = $state<MediaDeviceInfo[]>([]);
	let selectedVideoInputDeviceId = $state<string | null>(null);

	/** Enumerate available video input devices, including screen share as a virtual option */
	const getVideoInputDevices = async (): Promise<void> => {
		const devices = await navigator.mediaDevices.enumerateDevices();
		videoInputDevices = devices.filter((device) => device.kind === 'videoinput');

		if (navigator.mediaDevices.getDisplayMedia) {
			videoInputDevices = [
				...videoInputDevices,
				{
					deviceId: 'screen',
					label: $i18n.t('Screen Share')
				}
			];
		}

		if (selectedVideoInputDeviceId === null && videoInputDevices.length > 0) {
			selectedVideoInputDeviceId = videoInputDevices[0].deviceId;
		}
	};

	/** Start the video stream from the selected device or screen share */
	const startVideoStream = async (): Promise<void> => {
		const video = document.getElementById('camera-feed') as HTMLVideoElement;
		if (!video) return;

		if (selectedVideoInputDeviceId === 'screen') {
			cameraStream = await navigator.mediaDevices.getDisplayMedia({
				video: { cursor: 'always' },
				audio: false
			});
		} else {
			cameraStream = await navigator.mediaDevices.getUserMedia({
				video: {
					deviceId: selectedVideoInputDeviceId ? { exact: selectedVideoInputDeviceId } : undefined
				}
			});
		}

		if (cameraStream) {
			await getVideoInputDevices();
			video.srcObject = cameraStream;
			await video.play();
		}
	};

	/** Stop all tracks on the current camera stream */
	const stopVideoStream = async (): Promise<void> => {
		if (cameraStream) {
			cameraStream.getTracks().forEach((track) => track.stop());
		}
		cameraStream = null;
	};

	/** Initialize camera by enumerating devices and starting the stream */
	const startCamera = async (): Promise<void> => {
		await getVideoInputDevices();
		if (cameraStream === null) {
			camera = true;
			await tick();
			try {
				await startVideoStream();
			} catch (err) {
				logger.error('call', 'Error accessing webcam', undefined, err);
			}
		}
	};

	/** Stop the camera and release the stream */
	const stopCamera = async (): Promise<void> => {
		await stopVideoStream();
		camera = false;
	};

	/**
	 * Capture a screenshot from the camera feed.
	 * Returns the image as a data URL string.
	 */
	const takeScreenshot = (): string | undefined => {
		const video = document.getElementById('camera-feed') as HTMLVideoElement;
		const canvas = document.getElementById('camera-canvas') as HTMLCanvasElement;
		if (!canvas || !video) return undefined;

		const ctx = canvas.getContext('2d');
		canvas.width = video.videoWidth;
		canvas.height = video.videoHeight;
		ctx!.drawImage(video, 0, 0, video.videoWidth, video.videoHeight);
		return canvas.toDataURL('image/png');
	};

	// ---------------------------------------------------------------------------
	// Audio Recording
	// ---------------------------------------------------------------------------

	const MIN_DECIBELS = -55;
	let chatStreaming = false;
	let rmsLevel = $state(0);
	let hasStartedSpeaking = false;
	let mediaRecorder: MediaRecorder | boolean = false;
	let audioStream = $state<MediaStream | null>(null);
	let audioChunks: Blob[] = [];

	/** Send recorded audio to the transcription API and submit the result */
	const transcribeHandler = async (audioBlob: Blob): Promise<void> => {
		await tick();
		const file = blobToFile(audioBlob, 'recording.wav');

		const res = await transcribeAudio('', file).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res?.text) {
			await submitPrompt(res.text, { _raw: true });
		}
	};

	/**
	 * Callback after recording stops.
	 * If confirmed (silence was detected), transcribe and submit.
	 * Optionally continues listening for the next utterance.
	 */
	const stopRecordingCallback = async (shouldContinue = true): Promise<void> => {
		if (!get(showCallOverlay)) {
			audioChunks = [];
			mediaRecorder = false;
			if (audioStream) {
				audioStream.getTracks().forEach((track) => track.stop());
			}
			audioStream = null;
			return;
		}

		const capturedChunks = audioChunks.slice(0);
		audioChunks = [];
		mediaRecorder = false;

		if (shouldContinue) {
			startRecording();
		}

		if (confirmed) {
			loading = true;
			emoji = null;

			if (cameraStream) {
				const imageUrl = takeScreenshot();
				if (imageUrl) {
					files = [{ type: 'image', url: imageUrl }];
				}
			}

			const audioBlob = new Blob(capturedChunks, { type: 'audio/wav' });
			await transcribeHandler(audioBlob);

			confirmed = false;
			loading = false;
		}
	};

	/** Set up the MediaRecorder with the current audio stream */
	const startRecording = async (): Promise<void> => {
		if (!get(showCallOverlay)) return;

		if (!audioStream) {
			audioStream = await navigator.mediaDevices.getUserMedia({
				audio: {
					echoCancellation: true,
					noiseSuppression: true,
					autoGainControl: true
				}
			});
		}

		mediaRecorder = new MediaRecorder(audioStream);

		mediaRecorder.onstart = () => {
			audioChunks = [];
		};

		mediaRecorder.ondataavailable = (event) => {
			if (hasStartedSpeaking) {
				audioChunks.push(event.data);
			}
		};

		mediaRecorder.onstop = () => {
			stopRecordingCallback();
		};

		analyseAudio(audioStream);
	};

	/** Stop the media recorder and release the audio stream */
	const stopAudioStream = async (): Promise<void> => {
		try {
			if (mediaRecorder && typeof mediaRecorder === 'object') {
				mediaRecorder.stop();
			}
		} catch {
			// Silently ignore errors when stopping the recorder
		}

		if (!audioStream) return;

		audioStream.getAudioTracks().forEach((track) => track.stop());
		audioStream = null;
	};

	// ---------------------------------------------------------------------------
	// Audio Analysis (Voice Activity Detection)
	// ---------------------------------------------------------------------------

	/**
	 * Calculate the Root Mean Square level from time domain audio data.
	 * Used to detect speech volume for the visual indicator.
	 */
	const calculateRMS = (data: Uint8Array): number => {
		let sumSquares = 0;
		for (let i = 0; i < data.length; i++) {
			const normalizedValue = (data[i] - 128) / 128;
			sumSquares += normalizedValue * normalizedValue;
		}
		return Math.sqrt(sumSquares / data.length);
	};

	/**
	 * Set up real-time audio analysis for voice activity detection.
	 * Detects when the user starts and stops speaking, triggering
	 * recording start/stop and silence-based submission.
	 */
	const analyseAudio = (stream: MediaStream): void => {
		const audioContext = new AudioContext();
		const audioStreamSource = audioContext.createMediaStreamSource(stream);

		const analyser = audioContext.createAnalyser();
		analyser.minDecibels = MIN_DECIBELS;
		audioStreamSource.connect(analyser);

		const bufferLength = analyser.frequencyBinCount;
		const domainData = new Uint8Array(bufferLength);
		const timeDomainData = new Uint8Array(analyser.fftSize);

		let lastSoundTime = Date.now();
		hasStartedSpeaking = false;

		const SILENCE_TIMEOUT_MS = 2000;

		const processFrame = () => {
			if (!mediaRecorder || !get(showCallOverlay)) return;

			// Mute detection during assistant speech unless voice interruption is enabled
			if (assistantSpeaking && !(get(settings)?.voiceInterruption ?? false)) {
				analyser.maxDecibels = 0;
				analyser.minDecibels = -1;
			} else {
				analyser.minDecibels = MIN_DECIBELS;
				analyser.maxDecibels = -30;
			}

			analyser.getByteTimeDomainData(timeDomainData);
			analyser.getByteFrequencyData(domainData);

			rmsLevel = calculateRMS(timeDomainData);

			const hasSound = domainData.some((value) => value > 0);
			if (hasSound) {
				if (
					mediaRecorder &&
					typeof mediaRecorder === 'object' &&
					mediaRecorder.state !== 'recording'
				) {
					mediaRecorder.start();
				}

				if (!hasStartedSpeaking) {
					hasStartedSpeaking = true;
					stopAllAudio();
				}

				lastSoundTime = Date.now();
			}

			if (hasStartedSpeaking && Date.now() - lastSoundTime > SILENCE_TIMEOUT_MS) {
				confirmed = true;
				if (mediaRecorder && typeof mediaRecorder === 'object') {
					mediaRecorder.stop();
					return;
				}
			}

			window.requestAnimationFrame(processFrame);
		};

		window.requestAnimationFrame(processFrame);
	};

	// ---------------------------------------------------------------------------
	// Text-to-Speech
	// ---------------------------------------------------------------------------

	let finishedMessages: Record<string, boolean> = {};
	let currentMessageId: string | null = null;
	let currentUtterance: SpeechSynthesisUtterance | null = null;

	/** Speak text using the browser's built-in SpeechSynthesis API */
	const speakSpeechSynthesis = (content: string): Promise<Event> => {
		if (!get(showCallOverlay)) return Promise.resolve({} as Event);

		return new Promise((resolve) => {
			const getVoicesLoop = setInterval(async () => {
				const voices = await speechSynthesis.getVoices();
				if (voices.length === 0) return;

				clearInterval(getVoicesLoop);

				const voice =
					voices
						?.filter(
							(v) =>
								v.voiceURI === (get(settings)?.audio?.tts?.voice ?? get(config)?.audio?.tts?.voice)
						)
						?.at(0) ?? undefined;

				currentUtterance = new SpeechSynthesisUtterance(content);
				currentUtterance.rate = get(settings).audio?.tts?.playbackRate ?? 1;
				if (voice) currentUtterance.voice = voice;

				speechSynthesis.speak(currentUtterance);
				currentUtterance.onend = async (e) => {
					await new Promise((r) => setTimeout(r, 200));
					resolve(e);
				};
			}, 100);
		});
	};

	/** Play an Audio object through the shared audio element */
	const playAudio = (audio: HTMLAudioElement): Promise<Event> => {
		if (!get(showCallOverlay)) return Promise.resolve({} as Event);

		return new Promise((resolve) => {
			const audioElement = document.getElementById('audioElement') as HTMLAudioElement;
			if (!audioElement) return;

			audioElement.src = audio.src;
			audioElement.muted = true;
			audioElement.playbackRate = get(settings).audio?.tts?.playbackRate ?? 1;

			audioElement
				.play()
				.then(() => {
					audioElement.muted = false;
				})
				.catch((error) => {
					logger.error('call', 'Call error', undefined, error);
				});

			audioElement.onended = async (e) => {
				await new Promise((r) => setTimeout(r, 100));
				resolve(e);
			};
		});
	};

	/** Stop all currently playing audio (TTS, streaming response, etc.) */
	const stopAllAudio = async (): Promise<void> => {
		assistantSpeaking = false;

		if (chatStreaming) {
			stopResponse();
		}

		if (currentUtterance) {
			speechSynthesis.cancel();
			currentUtterance = null;
		}

		const audioElement = document.getElementById('audioElement') as HTMLAudioElement;
		if (audioElement) {
			audioElement.muted = true;
			audioElement.pause();
			audioElement.currentTime = 0;
		}
	};

	// ---------------------------------------------------------------------------
	// Audio Caching & Fetching
	// ---------------------------------------------------------------------------

	let audioAbortController = new AbortController();

	/** Cache for pre-fetched audio objects keyed by content string */
	const audioCache = new Map<string, HTMLAudioElement | true>(); // eslint-disable-line svelte/prefer-svelte-reactivity -- non-reactive cache
	/** Cache for emoji strings keyed by content */
	const emojiCache = new Map<string, string>(); // eslint-disable-line svelte/prefer-svelte-reactivity -- non-reactive cache

	/**
	 * Fetch and cache TTS audio for a given content string.
	 * Handles multiple TTS engines: Kokoro (local), OpenAI-compatible, and browser fallback.
	 */
	const fetchAudio = async (content: string): Promise<void> => {
		if (audioCache.has(content)) return;

		try {
			// Optionally generate an emoji for the content
			if (get(settings)?.showEmojiInCall ?? false) {
				const generatedEmoji = await generateEmoji('', modelId, content, chatId);
				if (generatedEmoji) emojiCache.set(content, generatedEmoji);
			}

			if (get(settings).audio?.tts?.engine === 'browser-kokoro') {
				const blob = await (get(TTSWorker) as KokoroWorker | null)
					?.generate({
						text: content,
						voice: get(settings)?.audio?.tts?.voice ?? get(config)?.audio?.tts?.voice ?? ''
					})
					.catch((error) => {
						logger.error('call', 'Call error', undefined, error);
						toast.error(`${error}`);
					});

				if (blob) audioCache.set(content, new Audio(blob));
			} else if (get(config).audio.tts.engine !== '') {
				const res = await synthesizeOpenAISpeech(
					'',
					get(settings)?.audio?.tts?.defaultVoice === get(config).audio.tts.voice
						? (get(settings)?.audio?.tts?.voice ?? get(config)?.audio?.tts?.voice)
						: get(config)?.audio?.tts?.voice,
					content
				).catch((error) => {
					logger.error('call', 'Call error', undefined, error);
					return null;
				});

				if (res) {
					const blob = await res.blob();
					audioCache.set(content, new Audio(URL.createObjectURL(blob)));
				}
			} else {
				audioCache.set(content, true);
			}
		} catch (error) {
			logger.error('call', 'Error synthesizing speech', undefined, error);
		}
	};

	// ---------------------------------------------------------------------------
	// Audio Playback Queue
	// ---------------------------------------------------------------------------

	/** Queue of content strings to speak, keyed by message ID */
	let messageAudioQueues: Record<string, string[]> = {};

	/**
	 * Monitor and play audio for a specific message.
	 * Continuously checks the queue for new content to speak,
	 * waiting for audio to be cached before playing.
	 */
	const monitorAndPlayAudio = async (messageId: string, signal: AbortSignal): Promise<void> => {
		while (!signal.aborted) {
			const queue = messageAudioQueues[messageId];
			if (queue && queue.length > 0) {
				const content = queue.shift()!;

				if (audioCache.has(content)) {
					// Display emoji if available
					if ((get(settings)?.showEmojiInCall ?? false) && emojiCache.has(content)) {
						emoji = emojiCache.get(content)!;
					} else {
						emoji = null;
					}

					if (get(config).audio.tts.engine !== '') {
						try {
							const audio = audioCache.get(content)!;
							await playAudio(audio as HTMLAudioElement);
							await new Promise((resolve) => setTimeout(resolve, 200));
						} catch (error) {
							logger.error('call', 'Error playing audio', undefined, error);
						}
					} else {
						await speakSpeechSynthesis(content);
					}
				} else {
					// Re-queue and wait for audio to be fetched
					queue.unshift(content);
					await new Promise((resolve) => setTimeout(resolve, 200));
				}
			} else if (finishedMessages[messageId] && queue && queue.length === 0) {
				assistantSpeaking = false;
				break;
			} else {
				await new Promise((resolve) => setTimeout(resolve, 200));
			}
		}
	};

	// ---------------------------------------------------------------------------
	// Chat Event Handlers
	// ---------------------------------------------------------------------------

	/** Handle the start of a new chat response stream */
	const chatStartHandler = async (e: CustomEvent): Promise<void> => {
		const { id } = e.detail;
		chatStreaming = true;

		if (currentMessageId !== id) {
			currentMessageId = id;
			audioAbortController.abort();
			audioAbortController = new AbortController();

			assistantSpeaking = true;
			monitorAndPlayAudio(id, audioAbortController.signal);
		}
	};

	/** Handle an incoming chat content chunk (sentence for TTS) */
	const chatEventHandler = async (e: CustomEvent): Promise<void> => {
		const { id, content } = e.detail;

		if (currentMessageId === id) {
			try {
				if (!messageAudioQueues[id]) {
					messageAudioQueues[id] = [content];
				} else {
					messageAudioQueues[id].push(content);
				}

				fetchAudio(content);
			} catch (error) {
				logger.error('call', 'Failed to fetch or play audio', undefined, error);
			}
		}
	};

	/** Handle the end of a chat response stream */
	const chatFinishHandler = async (e: CustomEvent): Promise<void> => {
		const { id } = e.detail;
		finishedMessages[id] = true;
		chatStreaming = false;
	};

	// ---------------------------------------------------------------------------
	// Lifecycle
	// ---------------------------------------------------------------------------

	/** Re-acquire wake lock when tab becomes visible again */
	const handleVisibilityChange = async (): Promise<void> => {
		if (wakeLock !== null && document.visibilityState === 'visible') {
			await requestWakeLock();
		}
	};

	/** Clean up all resources: audio, video, event listeners */
	const cleanup = async (): Promise<void> => {
		await stopAllAudio();
		await stopAudioStream();
		await stopRecordingCallback(false);
		await stopCamera();

		eventTarget.removeEventListener('chat:start', chatStartHandler as (e: Event) => void);
		eventTarget.removeEventListener('chat', chatEventHandler as (e: Event) => void);
		eventTarget.removeEventListener('chat:finish', chatFinishHandler as (e: Event) => void);

		document.removeEventListener('visibilitychange', handleVisibilityChange);

		audioAbortController.abort();
		await tick();
		await stopAllAudio();
	};

	onMount(async () => {
		// Set up wake lock to prevent screen from sleeping
		if ('wakeLock' in navigator) {
			await requestWakeLock();
			document.addEventListener('visibilitychange', handleVisibilityChange);
		}

		model = get(models).find((m) => m.id === modelId) as Record<string, unknown> | null;

		startRecording();

		eventTarget.addEventListener('chat:start', chatStartHandler as (e: Event) => void);
		eventTarget.addEventListener('chat', chatEventHandler as (e: Event) => void);
		eventTarget.addEventListener('chat:finish', chatFinishHandler as (e: Event) => void);

		return async () => {
			await cleanup();
		};
	});

	onDestroy(async () => {
		await cleanup();
	});

	// ---------------------------------------------------------------------------
	// RMS-based sizing helpers for the visual indicator
	// ---------------------------------------------------------------------------

	/** Compute the CSS size class for the main avatar based on RMS level */
	const getAvatarSizeClass = (prefix: string): string => {
		const level = rmsLevel * 100;
		if (level > 4) return `${prefix}-52`;
		if (level > 2) return `${prefix}-48`;
		if (level > 1) return `${prefix}-44`;
		return `${prefix}-40`;
	};

	/** Compute the font size for the emoji display based on RMS level */
	const getEmojiFontSize = (isSmall: boolean): string => {
		const level = rmsLevel * 100;
		if (isSmall) {
			if (level > 4) return '4.5';
			if (level > 2) return '4.25';
			if (level > 1) return '3.75';
			return '3.5';
		}
		if (level > 4) return '13';
		if (level > 2) return '12';
		if (level > 1) return '11.5';
		return '11';
	};

	/** Check if the model has a custom profile image */
	const hasCustomProfileImage = (): boolean =>
		(model?.info?.meta?.profile_image_url ?? '/static/favicon.png') !== '/static/favicon.png';

	/** Get the model profile image URL */
	const getProfileImageUrl = (): string =>
		model?.info?.meta?.profile_image_url ?? '/static/favicon.png';
</script>

{#if $showCallOverlay}
	<div class="max-w-lg w-full h-full max-h-[100dvh] flex flex-col justify-between p-3 md:p-6">
		{#if camera}
			<button
				type="button"
				class="flex justify-center items-center w-full h-20 min-h-20"
				onclick={() => {
					if (assistantSpeaking) stopAllAudio();
				}}
			>
				{#if emoji}
					<div
						class="  transition-all rounded-full"
						style="font-size:{getEmojiFontSize(true)}rem;width: 100%; text-align:center;"
					>
						{emoji}
					</div>
				{:else if loading || assistantSpeaking}
					<svg
						class="size-12 text-gray-900 dark:text-gray-400"
						viewBox="0 0 24 24"
						fill="currentColor"
						xmlns="http://www.w3.org/2000/svg"
						><style>
							.spinner_qM83 {
								animation: spinner_8HQG 1.05s infinite;
							}
							.spinner_oXPr {
								animation-delay: 0.1s;
							}
							.spinner_ZTLf {
								animation-delay: 0.2s;
							}
							@keyframes spinner_8HQG {
								0%,
								57.14% {
									animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
									transform: translate(0);
								}
								28.57% {
									animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
									transform: translateY(-6px);
								}
								100% {
									transform: translate(0);
								}
							}
						</style><circle class="spinner_qM83" cx="4" cy="12" r="3" /><circle
							class="spinner_qM83 spinner_oXPr"
							cx="12"
							cy="12"
							r="3"
						/><circle class="spinner_qM83 spinner_ZTLf" cx="20" cy="12" r="3" /></svg
					>
				{:else}
					<div
						class=" {rmsLevel * 100 > 4
							? ' size-[4.5rem]'
							: rmsLevel * 100 > 2
								? ' size-16'
								: rmsLevel * 100 > 1
									? 'size-14'
									: 'size-12'}  transition-all rounded-full {hasCustomProfileImage()
							? ' bg-cover bg-center bg-no-repeat'
							: 'bg-black dark:bg-white'}  bg-black dark:bg-white"
						style={hasCustomProfileImage()
							? `background-image: url('${getProfileImageUrl()}');`
							: ''}
					></div>
				{/if}
			</button>
		{/if}

		<div class="flex justify-center items-center flex-1 h-full w-full max-h-full">
			{#if !camera}
				<button
					type="button"
					onclick={() => {
						if (assistantSpeaking) stopAllAudio();
					}}
				>
					{#if emoji}
						<div
							class="  transition-all rounded-full"
							style="font-size:{getEmojiFontSize(false)}rem;width:100%;text-align:center;"
						>
							{emoji}
						</div>
					{:else if loading || assistantSpeaking}
						<svg
							class="size-44 text-gray-900 dark:text-gray-400"
							viewBox="0 0 24 24"
							fill="currentColor"
							xmlns="http://www.w3.org/2000/svg"
							><style>
								.spinner_qM83 {
									animation: spinner_8HQG 1.05s infinite;
								}
								.spinner_oXPr {
									animation-delay: 0.1s;
								}
								.spinner_ZTLf {
									animation-delay: 0.2s;
								}
								@keyframes spinner_8HQG {
									0%,
									57.14% {
										animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
										transform: translate(0);
									}
									28.57% {
										animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
										transform: translateY(-6px);
									}
									100% {
										transform: translate(0);
									}
								}
							</style><circle class="spinner_qM83" cx="4" cy="12" r="3" /><circle
								class="spinner_qM83 spinner_oXPr"
								cx="12"
								cy="12"
								r="3"
							/><circle class="spinner_qM83 spinner_ZTLf" cx="20" cy="12" r="3" /></svg
						>
					{:else}
						<div
							class=" {getAvatarSizeClass(
								'size'
							)}  transition-all rounded-full {hasCustomProfileImage()
								? ' bg-cover bg-center bg-no-repeat'
								: 'bg-black dark:bg-white'} "
							style={hasCustomProfileImage()
								? `background-image: url('${getProfileImageUrl()}');`
								: ''}
						></div>
					{/if}
				</button>
			{:else}
				<div class="relative flex video-container w-full max-h-full pt-2 pb-4 md:py-6 px-2 h-full">
					<video
						id="camera-feed"
						autoplay
						class="rounded-2xl h-full min-w-full object-cover object-center"
						playsinline
					></video>

					<canvas id="camera-canvas" style="display:none;"></canvas>

					<div class=" absolute top-4 md:top-8 left-4">
						<button
							type="button"
							class="p-1.5 text-white cursor-pointer backdrop-blur-xl bg-black/10 rounded-full"
							aria-label={$i18n.t('Stop camera')}
							onclick={stopCamera}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 16 16"
								fill="currentColor"
								class="size-6"
							>
								<path
									d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z"
								/>
							</svg>
						</button>
					</div>
				</div>
			{/if}
		</div>

		<div class="flex justify-between items-center pb-2 w-full">
			<div>
				{#if camera}
					<VideoInputMenu
						devices={videoInputDevices}
						onchange={async (e: unknown) => {
							const deviceId = (e as CustomEvent<string>).detail;
							selectedVideoInputDeviceId = deviceId;
							await stopVideoStream();
							await startVideoStream();
						}}
					>
						<button
							class=" p-3 rounded-full bg-gray-50 dark:bg-gray-900"
							type="button"
							aria-label={$i18n.t('Switch camera')}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 20 20"
								fill="currentColor"
								class="size-5"
							>
								<path
									fill-rule="evenodd"
									d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.449-.39Zm1.23-3.723a.75.75 0 0 0 .219-.53V2.929a.75.75 0 0 0-1.5 0V5.36l-.31-.31A7 7 0 0 0 3.239 8.188a.75.75 0 1 0 1.448.389A5.5 5.5 0 0 1 13.89 6.11l.311.31h-2.432a.75.75 0 0 0 0 1.5h4.243a.75.75 0 0 0 .53-.219Z"
									clip-rule="evenodd"
								/>
							</svg>
						</button>
					</VideoInputMenu>
				{:else}
					<Tooltip content={$i18n.t('Camera')}>
						<button
							class=" p-3 rounded-full bg-gray-50 dark:bg-gray-900"
							type="button"
							aria-label={$i18n.t('Camera')}
							onclick={async () => {
								await navigator.mediaDevices.getUserMedia({ video: true });
								startCamera();
							}}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="1.5"
								stroke="currentColor"
								class="size-5"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316Z"
								/>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0ZM18.75 10.5h.008v.008h-.008V10.5Z"
								/>
							</svg>
						</button>
					</Tooltip>
				{/if}
			</div>

			<div>
				<button
					type="button"
					onclick={() => {
						if (assistantSpeaking) stopAllAudio();
					}}
				>
					<div class=" line-clamp-1 text-sm font-medium">
						{#if loading}
							{$i18n.t('Thinking...')}
						{:else if assistantSpeaking}
							{$i18n.t('Tap to interrupt')}
						{:else}
							{$i18n.t('Listening...')}
						{/if}
					</div>
				</button>
			</div>

			<div>
				<button
					class=" p-3 rounded-full bg-gray-50 dark:bg-gray-900"
					aria-label={$i18n.t('Close')}
					onclick={async () => {
						await stopAudioStream();
						await stopVideoStream();
						showCallOverlay.set(false);
						onClose?.();
					}}
					type="button"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="size-5"
					>
						<path
							d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"
						/>
					</svg>
				</button>
			</div>
		</div>
	</div>
{/if}
