<script lang="ts">
	/**
	 * Admin Audio Settings
	 *
	 * Configures speech-to-text (STT) and text-to-speech (TTS) engines
	 * including Whisper (Local), OpenAI, ElevenLabs, Azure, and Deepgram.
	 */
	import { preventDefault } from 'svelte/legacy';
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import { getBackendConfig } from '$lib/apis';
	import {
		getAudioConfig,
		updateAudioConfig,
		getModels as fetchTtsModels,
		getVoices as fetchTtsVoices
	} from '$lib/apis/audio';
	import { config } from '$lib/stores';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import { TTS_RESPONSE_SPLIT } from '$lib/types';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	interface Props {
		/** Callback invoked after settings are successfully saved */
		saveHandler: () => void;
		/** Optional additional save callback */
		onSave?: (...args: unknown[]) => void;
	}

	let { saveHandler, onSave = () => {} }: Props = $props();

	const i18n = getContext<Writable<i18nType>>('i18n');

	// --- TTS State ---
	let TTS_OPENAI_API_BASE_URL = $state('');
	let TTS_OPENAI_API_KEY = $state('');
	let TTS_API_KEY = $state('');
	let TTS_ENGINE = $state('');
	let TTS_MODEL = $state('');
	let TTS_VOICE = $state('');
	let TTS_SPLIT_ON: TTS_RESPONSE_SPLIT = $state(TTS_RESPONSE_SPLIT.PUNCTUATION);
	let TTS_AZURE_SPEECH_REGION = $state('');
	let TTS_AZURE_SPEECH_OUTPUT_FORMAT = $state('');

	// --- STT State ---
	let STT_OPENAI_API_BASE_URL = $state('');
	let STT_OPENAI_API_KEY = $state('');
	let STT_ENGINE = $state('');
	let STT_MODEL = $state('');
	let STT_WHISPER_MODEL = $state('');
	let STT_DEEPGRAM_API_KEY = $state('');
	let STT_WHISPER_MODEL_LOADING = $state(false);

	// --- Available voices/models ---
	let voices: SpeechSynthesisVoice[] = $state([]);
	let models: Awaited<ReturnType<typeof fetchTtsModels>>['models'] = $state([]);

	/** Fetch available TTS models from the configured engine */
	const getModels = async () => {
		if (TTS_ENGINE === '') {
			models = [];
			return;
		}
		const res = await fetchTtsModels('').catch((e) => {
			toast.error(`${e}`);
		});
		if (res) {
			models = res.models;
		}
	};

	/** Fetch available TTS voices (browser or API-based depending on engine) */
	const getVoices = async () => {
		if (TTS_ENGINE === '') {
			// Poll for browser voices (they load asynchronously)
			const voicePollInterval = setInterval(() => {
				voices = speechSynthesis.getVoices();
				if (voices.length > 0) {
					clearInterval(voicePollInterval);
					voices.sort((a, b) => a.name.localeCompare(b.name, $i18n.resolvedLanguage));
				}
			}, 100);
		} else {
			const res = await fetchTtsVoices('').catch((e) => {
				toast.error(`${e}`);
			});
			if (res) {
				voices = res.voices;
				voices.sort((a, b) => a.name.localeCompare(b.name, $i18n.resolvedLanguage));
			}
		}
	};

	/** Persist audio configuration to the backend */
	const updateConfigHandler = async () => {
		const res = await updateAudioConfig('', {
			tts: {
				OPENAI_API_BASE_URL: TTS_OPENAI_API_BASE_URL,
				OPENAI_API_KEY: TTS_OPENAI_API_KEY,
				API_KEY: TTS_API_KEY,
				ENGINE: TTS_ENGINE,
				MODEL: TTS_MODEL,
				VOICE: TTS_VOICE,
				SPLIT_ON: TTS_SPLIT_ON,
				AZURE_SPEECH_REGION: TTS_AZURE_SPEECH_REGION,
				AZURE_SPEECH_OUTPUT_FORMAT: TTS_AZURE_SPEECH_OUTPUT_FORMAT
			},
			stt: {
				OPENAI_API_BASE_URL: STT_OPENAI_API_BASE_URL,
				OPENAI_API_KEY: STT_OPENAI_API_KEY,
				ENGINE: STT_ENGINE,
				MODEL: STT_MODEL,
				WHISPER_MODEL: STT_WHISPER_MODEL,
				DEEPGRAM_API_KEY: STT_DEEPGRAM_API_KEY
			}
		});

		if (res) {
			saveHandler();
			config.set(await getBackendConfig());
		}
	};

	/** Update the Whisper model with loading state */
	const sttModelUpdateHandler = async () => {
		STT_WHISPER_MODEL_LOADING = true;
		await updateConfigHandler();
		STT_WHISPER_MODEL_LOADING = false;
	};

	/** Handle TTS engine change - update config, refresh voices/models */
	const handleTtsEngineChange = async (e: Event) => {
		const target = e.target as HTMLSelectElement;
		await updateConfigHandler();
		await getVoices();
		await getModels();

		if (target.value === 'openai') {
			TTS_VOICE = 'alloy';
			TTS_MODEL = 'tts-1';
		} else {
			TTS_VOICE = '';
			TTS_MODEL = '';
		}
	};

	/** Handle form submission */
	const handleSubmit = async () => {
		await updateConfigHandler();
		onSave?.();
	};

	onMount(async () => {
		const res = await getAudioConfig('');

		if (res) {
			TTS_OPENAI_API_BASE_URL = res.tts.OPENAI_API_BASE_URL;
			TTS_OPENAI_API_KEY = res.tts.OPENAI_API_KEY;
			TTS_API_KEY = res.tts.API_KEY;
			TTS_ENGINE = res.tts.ENGINE;
			TTS_MODEL = res.tts.MODEL;
			TTS_VOICE = res.tts.VOICE;
			TTS_SPLIT_ON = res.tts.SPLIT_ON || TTS_RESPONSE_SPLIT.PUNCTUATION;
			TTS_AZURE_SPEECH_OUTPUT_FORMAT = res.tts.AZURE_SPEECH_OUTPUT_FORMAT;
			TTS_AZURE_SPEECH_REGION = res.tts.AZURE_SPEECH_REGION;

			STT_OPENAI_API_BASE_URL = res.stt.OPENAI_API_BASE_URL;
			STT_OPENAI_API_KEY = res.stt.OPENAI_API_KEY;
			STT_ENGINE = res.stt.ENGINE;
			STT_MODEL = res.stt.MODEL;
			STT_WHISPER_MODEL = res.stt.WHISPER_MODEL;
			STT_DEEPGRAM_API_KEY = res.stt.DEEPGRAM_API_KEY;
		}

		await getVoices();
		await getModels();
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(handleSubmit)}
>
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<div class="mb-2.5">
			<InfoCallout>
				{$i18n.t(
					'Configure the speech-to-text (STT) and text-to-speech (TTS) engines used for voice input and audio responses.'
				)}
			</InfoCallout>
		</div>

		<!-- Speech-to-Text (STT) -->
		<SettingsSection title={$i18n.t('Speech-to-Text (STT)')}>
			<div>
				<Field inline separator label={$i18n.t('Speech-to-Text Engine')}>
					<Select
						class="w-44"
						bind:value={STT_ENGINE}
						items={[
							{ value: '', label: $i18n.t('Whisper (Local)') },
							{ value: 'openai', label: 'OpenAI' },
							{ value: 'web', label: $i18n.t('Web API') },
							{ value: 'deepgram', label: 'Deepgram' }
						]}
					/>
				</Field>

				{#if STT_ENGINE === 'openai'}
					<div class="mt-2 flex w-full gap-2">
						<div class="flex-1 min-w-0">
							<Input
								size="sm"
								placeholder={$i18n.t('API Base URL')}
								bind:value={STT_OPENAI_API_BASE_URL}
								required
							/>
						</div>
						<div class="flex-1 min-w-0">
							<SensitiveInput placeholder={$i18n.t('API Key')} bind:value={STT_OPENAI_API_KEY} />
						</div>
					</div>

					<hr class="border-gray-100 dark:border-gray-850 my-2" />

					<Field class="mt-1" label={$i18n.t('STT Model')}>
						<Input
							size="sm"
							list="stt-model-list"
							bind:value={STT_MODEL}
							placeholder={$i18n.t('Select a model')}
						/>
						<datalist id="stt-model-list">
							<option value="whisper-1"></option>
						</datalist>
					</Field>
				{:else if STT_ENGINE === 'deepgram'}
					<div class="mt-2 flex w-full gap-2">
						<div class="flex-1 min-w-0">
							<SensitiveInput placeholder={$i18n.t('API Key')} bind:value={STT_DEEPGRAM_API_KEY} />
						</div>
					</div>

					<hr class="border-gray-100 dark:border-gray-850 my-2" />

					<Field class="mt-1" label={$i18n.t('STT Model')}>
						<Input
							size="sm"
							bind:value={STT_MODEL}
							placeholder={$i18n.t('Select a model (optional)')}
						/>
						<p class="mt-1 text-xs text-muted-foreground">
							{$i18n.t('Leave model field empty to use the default model.')}
							<a
								class="font-medium text-primary underline"
								href="https://developers.deepgram.com/docs/models"
								target="_blank"
							>
								{$i18n.t('Click here to see available models.')}
							</a>
						</p>
					</Field>
				{:else if STT_ENGINE === ''}
					<Field class="mt-1" label={$i18n.t('STT Model')}>
						<div class="flex w-full items-center gap-2">
							<div class="flex-1 min-w-0">
								<Input
									size="sm"
									placeholder={$i18n.t('Set whisper model')}
									bind:value={STT_WHISPER_MODEL}
								/>
							</div>
							<Button
								class="shrink-0"
								variant="secondary"
								size="sm"
								onclick={sttModelUpdateHandler}
								disabled={STT_WHISPER_MODEL_LOADING}
							>
								{#if STT_WHISPER_MODEL_LOADING}
									<div class="self-center">
										<svg
											class="w-4 h-4"
											viewBox="0 0 24 24"
											fill="currentColor"
											xmlns="http://www.w3.org/2000/svg"
										>
											<style>
												.spinner_ajPY {
													transform-origin: center;
													animation: spinner_AtaB 0.75s infinite linear;
												}
												@keyframes spinner_AtaB {
													100% {
														transform: rotate(360deg);
													}
												}
											</style>
											<path
												d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
												opacity=".25"
											/>
											<path
												d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
												class="spinner_ajPY"
											/>
										</svg>
									</div>
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 16 16"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z"
										/>
										<path
											d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z"
										/>
									</svg>
								{/if}
							</Button>
						</div>
						<p class="mt-1 text-xs text-muted-foreground">
							{$i18n.t('BCGPT uses faster-whisper internally.')}
							<a
								class="font-medium text-primary underline"
								href="https://github.com/SYSTRAN/faster-whisper"
								target="_blank"
							>
								{$i18n.t(
									'Click here to learn more about faster-whisper and see the available models.'
								)}
							</a>
						</p>
					</Field>
				{/if}
			</div>
		</SettingsSection>

		<!-- Text-to-Speech (TTS) -->
		<SettingsSection title={$i18n.t('Text-to-Speech (TTS)')}>
			<div>
				<Field inline separator label={$i18n.t('Text-to-Speech Engine')}>
					<div class="relative flex items-center">
						<select
							class="flex h-8 w-44 cursor-pointer appearance-none rounded-md border border-input bg-background px-3 pr-8 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							bind:value={TTS_ENGINE}
							onchange={handleTtsEngineChange}
						>
							<option value="">{$i18n.t('Web API')}</option>
							<option value="transformers">{$i18n.t('Transformers')} ({$i18n.t('Local')})</option>
							<option value="openai">{$i18n.t('OpenAI')}</option>
							<option value="elevenlabs">{$i18n.t('ElevenLabs')}</option>
							<option value="azure">{$i18n.t('Azure AI Speech')}</option>
						</select>
						<ChevronDown
							className="pointer-events-none absolute end-2.5 top-1/2 size-3.5 -translate-y-1/2 opacity-60"
							strokeWidth="2.5"
						/>
					</div>
				</Field>

				{#if TTS_ENGINE === 'openai'}
					<div class="mt-2 flex w-full gap-2">
						<div class="flex-1 min-w-0">
							<Input
								size="sm"
								placeholder={$i18n.t('API Base URL')}
								bind:value={TTS_OPENAI_API_BASE_URL}
								required
							/>
						</div>
						<div class="flex-1 min-w-0">
							<SensitiveInput placeholder={$i18n.t('API Key')} bind:value={TTS_OPENAI_API_KEY} />
						</div>
					</div>
				{:else if TTS_ENGINE === 'elevenlabs'}
					<div class="mt-2 flex w-full gap-2">
						<div class="flex-1 min-w-0">
							<Input size="sm" placeholder={$i18n.t('API Key')} bind:value={TTS_API_KEY} required />
						</div>
					</div>
				{:else if TTS_ENGINE === 'azure'}
					<div class="mt-2 flex w-full gap-2">
						<div class="flex-1 min-w-0">
							<Input size="sm" placeholder={$i18n.t('API Key')} bind:value={TTS_API_KEY} required />
						</div>
						<div class="flex-1 min-w-0">
							<Input
								size="sm"
								placeholder={$i18n.t('Azure Region')}
								bind:value={TTS_AZURE_SPEECH_REGION}
								required
							/>
						</div>
					</div>
				{/if}

				<hr class="border-gray-100 dark:border-gray-850 my-2" />

				<!-- Voice/Model Selection by Engine -->
				{#if TTS_ENGINE === ''}
					<Field class="mt-1" label={$i18n.t('TTS Voice')}>
						<Select
							bind:value={TTS_VOICE}
							items={[
								{ value: '', label: $i18n.t('Default') },
								...voices.map((voice) => ({
									value: voice.voiceURI,
									label: voice.name.replace('+', ', ')
								}))
							]}
						/>
					</Field>
				{:else if TTS_ENGINE === 'transformers'}
					<Field class="mt-1" label={$i18n.t('TTS Model')}>
						<Input
							size="sm"
							list="tts-model-list"
							bind:value={TTS_MODEL}
							placeholder={$i18n.t('CMU ARCTIC speaker embedding name')}
						/>
						<datalist id="tts-model-list">
							<option value="tts-1"></option>
						</datalist>
						<p class="mt-1 text-xs text-muted-foreground">
							{$i18n.t('BCGPT uses SpeechT5 and CMU Arctic speaker embeddings.')}
							To learn more about SpeechT5,
							<a
								class="font-medium text-primary underline"
								href="https://github.com/microsoft/SpeechT5"
								target="_blank"
							>
								{$i18n.t('click here', { name: 'SpeechT5' })}.
							</a>
							To see the available CMU Arctic speaker embeddings,
							<a
								class="font-medium text-primary underline"
								href="https://huggingface.co/datasets/Matthijs/cmu-arctic-xvectors"
								target="_blank"
							>
								{$i18n.t('click here')}.
							</a>
						</p>
					</Field>
				{:else if TTS_ENGINE === 'openai' || TTS_ENGINE === 'elevenlabs'}
					<div class="mt-1 flex w-full gap-2">
						<Field class="w-full" label={$i18n.t('TTS Voice')}>
							<Input
								size="sm"
								list="voice-list"
								bind:value={TTS_VOICE}
								placeholder={$i18n.t('Select a voice')}
							/>
							<datalist id="voice-list">
								{#each voices as voice (voice.id)}
									<option value={voice.id}>{voice.name}</option>
								{/each}
							</datalist>
						</Field>
						<Field class="w-full" label={$i18n.t('TTS Model')}>
							<Input
								size="sm"
								list="tts-model-list"
								bind:value={TTS_MODEL}
								placeholder={$i18n.t('Select a model')}
							/>
							<datalist id="tts-model-list">
								{#each models as model (model.id)}
									<option value={model.id}></option>
								{/each}
							</datalist>
						</Field>
					</div>
				{:else if TTS_ENGINE === 'azure'}
					<div class="mt-1 flex w-full gap-2">
						<Field class="w-full" label={$i18n.t('TTS Voice')}>
							<Input
								size="sm"
								list="voice-list"
								bind:value={TTS_VOICE}
								placeholder={$i18n.t('Select a voice')}
							/>
							<datalist id="voice-list">
								{#each voices as voice (voice.id)}
									<option value={voice.id}>{voice.name}</option>
								{/each}
							</datalist>
						</Field>
						<Field class="w-full">
							<div class="mb-1 text-sm font-medium text-foreground">
								{$i18n.t('Output format')}
								<a
									class="font-medium text-primary underline"
									href="https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech?tabs=streaming#audio-outputs"
									target="_blank"
								>
									<small>{$i18n.t('Available list')}</small>
								</a>
							</div>
							<Input
								size="sm"
								list="tts-model-list"
								bind:value={TTS_AZURE_SPEECH_OUTPUT_FORMAT}
								placeholder={$i18n.t('Select a output format')}
							/>
						</Field>
					</div>
				{/if}
			</div>
		</SettingsSection>

		<!-- Advanced TTS Output -->
		<SettingsSection title={$i18n.t('Advanced TTS Output')} open={false}>
			<!-- Response Splitting -->
			<Field inline separator label={$i18n.t('Response splitting')}>
				<div class="relative flex items-center">
					<select
						class="flex h-8 w-44 cursor-pointer appearance-none rounded-md border border-input bg-background px-3 pr-8 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						aria-label={$i18n.t('Select how to split message text for TTS requests')}
						bind:value={TTS_SPLIT_ON}
					>
						{#each Object.values(TTS_RESPONSE_SPLIT) as split (split)}
							<option value={split}
								>{$i18n.t(split.charAt(0).toUpperCase() + split.slice(1))}</option
							>
						{/each}
					</select>
					<ChevronDown
						className="pointer-events-none absolute end-2.5 top-1/2 size-3.5 -translate-y-1/2 opacity-60"
						strokeWidth="2.5"
					/>
				</div>
			</Field>
			<p class="mt-2 text-xs text-muted-foreground">
				{$i18n.t(
					"Control how message text is split for TTS requests. 'Punctuation' splits into sentences, 'paragraphs' splits into paragraphs, and 'none' keeps the message as a single string."
				)}
			</p>
		</SettingsSection>
	</div>

	<div class="flex justify-end pt-3">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
