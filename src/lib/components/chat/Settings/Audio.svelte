<script lang="ts">
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';

	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import { KokoroTTS } from 'kokoro-js';

	import { settings, config } from '$lib/stores';
	import { getVoices as _getVoices } from '$lib/apis/audio';

	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		saveSettings: (settings: Record<string, unknown>) => void | Promise<void>;

		onSave?: (...args: unknown[]) => void;
	}

	interface VoiceOption {
		id?: string;
		name: string;
		localService?: boolean;
	}

	let { saveSettings, onSave = () => {} }: Props = $props();

	// Audio
	let _conversationMode = false;
	let speechAutoSend = $state(false);
	let responseAutoPlayback = $state(false);
	let nonLocalVoices = $state(false);

	let STTEngine = $state('');

	let TTSEngine = $state('');
	let TTSEngineConfig = $state({});

	let TTSModel = $state(null);
	let TTSModelProgress = $state(null);
	let _TTSModelLoading = false;

	let voices = $state<VoiceOption[]>([]);
	let voice = $state('');

	// Audio speed control
	let playbackRate = $state(1);
	const speedOptions = [2, 1.75, 1.5, 1.25, 1, 0.75, 0.5];

	const getVoices = async () => {
		if (TTSEngine === 'browser-kokoro') {
			if (!TTSModel) {
				await loadKokoro();
			}

			voices = Object.entries(TTSModel.voices).map(([key, value]) => {
				return {
					id: key,
					name: value.name,
					localService: false
				};
			});
		} else {
			if (get(config).audio.tts.engine === '') {
				const getVoicesLoop = setInterval(async () => {
					voices = await speechSynthesis.getVoices();

					// do your loop
					if (voices.length > 0) {
						clearInterval(getVoicesLoop);
					}
				}, 100);
			} else {
				const res = await _getVoices('').catch((e) => {
					toast.error(`${e}`);
				});

				if (res) {
					voices = res.voices;
				}
			}
		}
	};

	const toggleResponseAutoPlayback = async () => {
		responseAutoPlayback = !responseAutoPlayback;
		saveSettings({ responseAutoPlayback: responseAutoPlayback });
	};

	const toggleSpeechAutoSend = async () => {
		speechAutoSend = !speechAutoSend;
		saveSettings({ speechAutoSend: speechAutoSend });
	};

	onMount(async () => {
		playbackRate = get(settings).audio?.tts?.playbackRate ?? 1;
		_conversationMode = get(settings).conversationMode ?? false;
		speechAutoSend = get(settings).speechAutoSend ?? false;
		responseAutoPlayback = get(settings).responseAutoPlayback ?? false;

		STTEngine = get(settings)?.audio?.stt?.engine ?? '';

		TTSEngine = get(settings)?.audio?.tts?.engine ?? '';
		TTSEngineConfig = get(settings)?.audio?.tts?.engineConfig ?? {};

		if (get(settings)?.audio?.tts?.defaultVoice === get(config).audio.tts.voice) {
			voice = get(settings)?.audio?.tts?.voice ?? get(config).audio.tts.voice ?? '';
		} else {
			voice = get(config).audio.tts.voice ?? '';
		}

		nonLocalVoices = get(settings).audio?.tts?.nonLocalVoices ?? false;

		await getVoices();
	});

	const onTTSEngineChange = async () => {
		if (TTSEngine === 'browser-kokoro') {
			await loadKokoro();
		}
	};

	const loadKokoro = async () => {
		if (TTSEngine === 'browser-kokoro') {
			voices = [];

			if (TTSEngineConfig?.dtype) {
				TTSModel = null;
				TTSModelProgress = null;
				_TTSModelLoading = true;

				const model_id = 'onnx-community/Kokoro-82M-v1.0-ONNX';

				TTSModel = await KokoroTTS.from_pretrained(model_id, {
					dtype: TTSEngineConfig.dtype, // Options: "fp32", "fp16", "q8", "q4", "q4f16"
					device: navigator?.gpu ? 'webgpu' : 'wasm', // Detect WebGPU
					progress_callback: (e) => {
						TTSModelProgress = e;
					}
				});

				await getVoices();

				// const rawAudio = await tts.generate(inputText, {
				// 	// Use `tts.list_voices()` to list all available voices
				// 	voice: voice
				// });

				// const blobUrl = URL.createObjectURL(await rawAudio.toBlob());
				// const audio = new Audio(blobUrl);

				// audio.play();
			}
		}
	};
	$effect(() => {
		if (TTSEngine && TTSEngineConfig) {
			onTTSEngineChange();
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(async () => {
		saveSettings({
			audio: {
				stt: {
					engine: STTEngine !== '' ? STTEngine : undefined
				},
				tts: {
					engine: TTSEngine !== '' ? TTSEngine : undefined,
					engineConfig: TTSEngineConfig,
					playbackRate: playbackRate,
					voice: voice !== '' ? voice : undefined,
					defaultVoice: $config?.audio?.tts?.voice ?? '',
					nonLocalVoices: $config.audio.tts.engine === '' ? nonLocalVoices : undefined
				}
			}
		});
		onSave?.();
	})}
>
	<div class=" space-y-3 overflow-y-scroll max-h-[28rem] lg:max-h-full">
		<div>
			<div class=" mb-1 text-sm font-medium">{$i18n.t('STT Settings')}</div>

			{#if $config.audio.stt.engine !== 'web'}
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">{$i18n.t('Speech-to-Text Engine')}</div>
					<div class="flex items-center relative">
						<select
							class="dark:bg-gray-850 p-1 px-2 border-1 pr-5 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500 rounded-md"
							bind:value={STTEngine}
							placeholder={$i18n.t('Select an engine')}
						>
							<option value="">{$i18n.t('Default')}</option>
							<option value="web">{$i18n.t('Web API')}</option>
						</select>
					</div>
				</div>
			{/if}

			<div
				class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Instant Auto-Send After Voice Transcription')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition"
					onclick={() => {
						toggleSpeechAutoSend();
					}}
					type="button"
				>
					{#if speechAutoSend === true}
						<span class="ml-2 self-center">{$i18n.t('On')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Off')}</span>
					{/if}
				</button>
			</div>
		</div>

		<div>
			<div class=" mb-1 text-sm font-medium">{$i18n.t('TTS Settings')}</div>

			<div
				class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">{$i18n.t('Text-to-Speech Engine')}</div>
				<div class="flex items-center relative">
					<select
						class="dark:bg-gray-850 p-1 px-2 border-1 pr-5 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500 rounded-md"
						bind:value={TTSEngine}
						placeholder={$i18n.t('Select an engine')}
					>
						<option value="">{$i18n.t('Default')}</option>
						<option value="browser-kokoro">{$i18n.t('Kokoro.js (Browser)')}</option>
					</select>
				</div>
			</div>

			{#if TTSEngine === 'browser-kokoro'}
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">{$i18n.t('Kokoro.js Dtype')}</div>
					<div class="flex items-center relative">
						<select
							class="dark:bg-gray-850 p-1 px-2 border-1 pr-5 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500 rounded-md"
							bind:value={TTSEngineConfig.dtype}
							placeholder={$i18n.t('Select dtype')}
						>
							<option value="" disabled selected>{$i18n.t('Select dtype')}</option>
							<option value="fp32">fp32</option>
							<option value="fp16">fp16</option>
							<option value="q8">q8</option>
							<option value="q4">q4</option>
						</select>
					</div>
				</div>
			{/if}

			<div
				class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">{$i18n.t('Auto-playback response')}</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition"
					onclick={() => {
						toggleResponseAutoPlayback();
					}}
					type="button"
				>
					{#if responseAutoPlayback === true}
						<span class="ml-2 self-center">{$i18n.t('On')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Off')}</span>
					{/if}
				</button>
			</div>

			<div
				class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">{$i18n.t('Speech Playback Speed')}</div>

				<div class="flex items-center relative">
					<select
						class="dark:bg-gray-850 p-1 px-2 border-1 pr-5 border-gray-300 dark:border-gray-700 focus:text-blue-600 focus:ring-0 focus:border-gray-400 dark:focus:border-gray-500 rounded-md"
						bind:value={playbackRate}
					>
						{#each speedOptions as option (option)}
							<option value={option} selected={playbackRate === option}>{option}x</option>
						{/each}
					</select>
				</div>
			</div>
		</div>

		<hr class=" border-gray-100 dark:border-gray-850" />

		{#if TTSEngine === 'browser-kokoro'}
			{#if TTSModel}
				<div>
					<div class=" mb-2.5 text-sm font-medium">{$i18n.t('Set Voice')}</div>
					<div class="flex w-full">
						<div class="flex-1">
							<input
								list="voice-list"
								class="w-full rounded-lg py-2 px-4 text-sm bg-white dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								bind:value={voice}
								placeholder={$i18n.t('Select a voice')}
							/>

							<datalist id="voice-list">
								{#each voices as voice (voice.id)}
									<option value={voice.id}>{voice.name}</option>
								{/each}
							</datalist>
						</div>
					</div>
				</div>
			{:else}
				<div>
					<div class=" mb-2.5 text-sm font-medium flex gap-2 items-center">
						<Spinner className="size-4" />

						<div class=" text-sm font-medium shimmer">
							{$i18n.t('Loading Kokoro.js...')}
							{TTSModelProgress && TTSModelProgress.status === 'progress'
								? `(${Math.round(TTSModelProgress.progress * 10) / 10}%)`
								: ''}
						</div>
					</div>

					<div class="text-xs text-gray-500">
						{$i18n.t('Please do not close the settings page while loading the model.')}
					</div>
				</div>
			{/if}
		{:else if $config.audio.tts.engine === ''}
			<div>
				<div class=" mb-2.5 text-sm font-medium">{$i18n.t('Set Voice')}</div>
				<div class="flex w-full">
					<div class="flex-1">
						<select
							class="w-full rounded-lg py-2 px-4 text-sm bg-white dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							bind:value={voice}
						>
							<option value="" selected={voice !== ''}>{$i18n.t('Default')}</option>
							{#each voices.filter((v) => nonLocalVoices || v.localService === true) as _voice (_voice.name)}
								<option
									value={_voice.name}
									class="bg-gray-100 dark:bg-gray-700"
									selected={voice === _voice.name}>{_voice.name}</option
								>
							{/each}
						</select>
					</div>
				</div>
				<div class="flex items-center justify-between my-1.5">
					<div class="text-xs">
						{$i18n.t('Allow non-local voices')}
					</div>

					<div class="mt-1">
						<Switch bind:state={nonLocalVoices} />
					</div>
				</div>
			</div>
		{:else if $config.audio.tts.engine !== ''}
			<div>
				<div class=" mb-2.5 text-sm font-medium">{$i18n.t('Set Voice')}</div>
				<div class="flex w-full">
					<div class="flex-1">
						<input
							list="voice-list"
							class="w-full rounded-lg py-2 px-4 text-sm bg-white dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							bind:value={voice}
							placeholder={$i18n.t('Select a voice')}
						/>

						<datalist id="voice-list">
							{#each voices as voice (voice.id)}
								<option value={voice.id}>{voice.name}</option>
							{/each}
						</datalist>
					</div>
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
