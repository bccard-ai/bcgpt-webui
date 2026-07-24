<script lang="ts">
	/**
	 * Admin Connections Settings
	 *
	 * Manages API connections to external model providers: OpenAI, Ollama,
	 * Google Gemini, Anthropic Claude, and Direct Connections.
	 * Each provider can be toggled and configured with multiple connection entries.
	 */
	import { get } from 'svelte/store';

	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';

	import { getOllamaConfig, updateOllamaConfig } from '$lib/apis/ollama';
	import { getOpenAIConfig, updateOpenAIConfig, getOpenAIModels } from '$lib/apis/openai';
	import { getGeminiConfig, updateGeminiConfig } from '$lib/apis/gemini';
	import { getClaudeConfig, updateClaudeConfig } from '$lib/apis/claude';
	import { getModels as _getModels } from '$lib/apis';
	import { getDirectConnectionsConfig, setDirectConnectionsConfig } from '$lib/apis/configs';

	import { config, models, settings, user } from '$lib/stores';

	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';

	import SettingsSection from './SettingsSection.svelte';
	import OpenAIConnection from './Connections/OpenAIConnection.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import OllamaConnection from './Connections/OllamaConnection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Callback invoked after all connections are saved */
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/** Fetch models from the backend with optional direct connections */
	const getModels = async () => {
		return await _getModels(
			'',
			get(config)?.features?.enable_direct_connections && (get(settings)?.directConnections ?? null)
		);
	};

	// --- Ollama connection state ---
	let OLLAMA_BASE_URLS = $state(['']);
	let OLLAMA_API_CONFIGS = $state({});

	// --- OpenAI connection state ---
	let OPENAI_API_KEYS = $state(['']);
	let OPENAI_API_BASE_URLS = $state(['']);
	let OPENAI_API_CONFIGS = $state({});

	// --- Provider enable toggles (null = loading) ---
	let ENABLE_OPENAI_API: null | boolean = $state(null);
	let ENABLE_OLLAMA_API: null | boolean = $state(null);
	let ENABLE_GEMINI_API: null | boolean = $state(null);
	let ENABLE_CLAUDE_API: null | boolean = $state(null);

	// --- Gemini connection state ---
	let GEMINI_API_KEYS: string[] = $state(['']);
	let GEMINI_API_BASE_URL: string = $state('');
	let GEMINI_API_CONFIGS: Record<string, unknown> = {};

	// --- Claude connection state ---
	let CLAUDE_API_KEYS: string[] = $state(['']);
	let CLAUDE_API_BASE_URL: string = $state('');
	let CLAUDE_API_CONFIGS: Record<string, unknown> = {};

	// --- Direct connections ---
	let directConnectionsConfig = $state(null);

	// --- UI state ---
	let pipelineUrls = $state({});
	let showAddOpenAIConnectionModal = $state(false);
	let showAddOllamaConnectionModal = $state(false);

	/** Collapsed groups that auto-open when their feature is already enabled on load. */
	let ollamaOpen = $state(false);
	let advancedOpen = $state(false);

	/**
	 * Persist OpenAI connection config to backend.
	 * Strips trailing slashes from URLs and pads key array to match URL count.
	 * @param silent - If true, suppress success toast (used during batch save)
	 */
	const updateOpenAIHandler = async (silent = false) => {
		if (ENABLE_OPENAI_API !== null) {
			// Remove trailing slashes
			OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS.map((url) => url.replace(/\/$/, ''));

			// Check if API KEYS length is same than API URLS length
			if (OPENAI_API_KEYS.length !== OPENAI_API_BASE_URLS.length) {
				// if there are more keys than urls, remove the extra keys
				if (OPENAI_API_KEYS.length > OPENAI_API_BASE_URLS.length) {
					OPENAI_API_KEYS = OPENAI_API_KEYS.slice(0, OPENAI_API_BASE_URLS.length);
				}

				// if there are more urls than keys, add empty keys
				if (OPENAI_API_KEYS.length < OPENAI_API_BASE_URLS.length) {
					const diff = OPENAI_API_BASE_URLS.length - OPENAI_API_KEYS.length;
					for (let i = 0; i < diff; i++) {
						OPENAI_API_KEYS.push('');
					}
				}
			}

			const res = await updateOpenAIConfig('', {
				ENABLE_OPENAI_API: ENABLE_OPENAI_API,
				OPENAI_API_BASE_URLS: OPENAI_API_BASE_URLS,
				OPENAI_API_KEYS: OPENAI_API_KEYS,
				OPENAI_API_CONFIGS: OPENAI_API_CONFIGS
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (res) {
				if (!silent) {
					toast.success($i18n.t('OpenAI API settings updated'));
				}
				await models.set(await getModels());
			}
		}
	};

	/**
	 * Persist Ollama connection config to backend.
	 * Strips trailing slashes from URLs.
	 * @param silent - If true, suppress success toast
	 */
	const updateOllamaHandler = async (silent = false) => {
		if (ENABLE_OLLAMA_API !== null) {
			// Remove trailing slashes
			OLLAMA_BASE_URLS = OLLAMA_BASE_URLS.map((url) => url.replace(/\/$/, ''));

			const res = await updateOllamaConfig('', {
				ENABLE_OLLAMA_API: ENABLE_OLLAMA_API,
				OLLAMA_BASE_URLS: OLLAMA_BASE_URLS,
				OLLAMA_API_CONFIGS: OLLAMA_API_CONFIGS
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (res) {
				if (!silent) {
					toast.success($i18n.t('Ollama API settings updated'));
				}
				await models.set(await getModels());
			}
		}
	};

	/**
	 * Persist Direct Connections config to backend.
	 * @param silent - If true, suppress success toast
	 */
	const updateDirectConnectionsHandler = async (silent = false) => {
		const res = await setDirectConnectionsConfig('', directConnectionsConfig).catch((error) => {
			toast.error(`${error}`);
		});

		if (res) {
			if (!silent) {
				toast.success($i18n.t('Direct Connections settings updated'));
			}
			await models.set(await getModels());
		}
	};

	/**
	 * Persist Gemini connection config to backend.
	 * @param silent - If true, suppress success toast
	 */
	const updateGeminiHandler = async (silent = false) => {
		if (ENABLE_GEMINI_API !== null) {
			const res = await updateGeminiConfig('', {
				ENABLE_GEMINI_API: ENABLE_GEMINI_API,
				GEMINI_API_KEYS: GEMINI_API_KEYS,
				GEMINI_API_BASE_URL: GEMINI_API_BASE_URL,
				GEMINI_API_CONFIGS: GEMINI_API_CONFIGS
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (res) {
				if (!silent) {
					toast.success($i18n.t('Gemini API settings updated'));
				}
				await models.set(await getModels());
			}
		}
	};

	/**
	 * Persist Claude connection config to backend.
	 * @param silent - If true, suppress success toast
	 */
	const updateClaudeHandler = async (silent = false) => {
		if (ENABLE_CLAUDE_API !== null) {
			const res = await updateClaudeConfig('', {
				ENABLE_CLAUDE_API: ENABLE_CLAUDE_API,
				CLAUDE_API_KEYS: CLAUDE_API_KEYS,
				CLAUDE_API_BASE_URL: CLAUDE_API_BASE_URL,
				CLAUDE_API_CONFIGS: CLAUDE_API_CONFIGS
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (res) {
				if (!silent) {
					toast.success($i18n.t('Claude API settings updated'));
				}
				await models.set(await getModels());
			}
		}
	};

	/**
	 * Append a new OpenAI connection entry and persist.
	 * @param connection - Object with url, key, and optional config
	 */
	const addOpenAIConnectionHandler = async (connection) => {
		OPENAI_API_BASE_URLS = [...OPENAI_API_BASE_URLS, connection.url];
		OPENAI_API_KEYS = [...OPENAI_API_KEYS, connection.key];
		OPENAI_API_CONFIGS[OPENAI_API_BASE_URLS.length - 1] = connection.config;

		await updateOpenAIHandler();
	};

	/**
	 * Append a new Ollama connection entry and persist.
	 * @param connection - Object with url, key, and optional config
	 */
	const addOllamaConnectionHandler = async (connection) => {
		OLLAMA_BASE_URLS = [...OLLAMA_BASE_URLS, connection.url];
		OLLAMA_API_CONFIGS[OLLAMA_BASE_URLS.length - 1] = {
			...connection.config,
			key: connection.key
		};

		await updateOllamaHandler();
	};

	/**
	 * Initialize all provider configs on mount.
	 * Fetches Ollama, OpenAI, Gemini, Claude, and Direct Connections
	 * configs in parallel, then loads pipeline info for enabled OpenAI URLs.
	 */
	onMount(async () => {
		if (get(user).role === 'admin') {
			let ollamaConfig = {};
			let openaiConfig = {};
			let geminiConfig = {};
			let claudeConfig = {};

			await Promise.all([
				(async () => {
					ollamaConfig = await getOllamaConfig('');
				})(),
				(async () => {
					openaiConfig = await getOpenAIConfig('');
				})(),
				(async () => {
					geminiConfig = await getGeminiConfig('').catch(() => ({
						ENABLE_GEMINI_API: false,
						GEMINI_API_KEYS: [''],
						GEMINI_API_BASE_URL: '',
						GEMINI_API_CONFIGS: {}
					}));
				})(),
				(async () => {
					claudeConfig = await getClaudeConfig('').catch(() => ({
						ENABLE_CLAUDE_API: false,
						CLAUDE_API_KEYS: [''],
						CLAUDE_API_BASE_URL: '',
						CLAUDE_API_CONFIGS: {}
					}));
				})(),
				(async () => {
					directConnectionsConfig = await getDirectConnectionsConfig('');
				})()
			]);

			ENABLE_OPENAI_API = openaiConfig.ENABLE_OPENAI_API;
			ENABLE_OLLAMA_API = ollamaConfig.ENABLE_OLLAMA_API;

			OPENAI_API_BASE_URLS = openaiConfig.OPENAI_API_BASE_URLS;
			OPENAI_API_KEYS = openaiConfig.OPENAI_API_KEYS;
			OPENAI_API_CONFIGS = openaiConfig.OPENAI_API_CONFIGS;

			OLLAMA_BASE_URLS = ollamaConfig.OLLAMA_BASE_URLS;
			OLLAMA_API_CONFIGS = ollamaConfig.OLLAMA_API_CONFIGS;

			ENABLE_GEMINI_API = geminiConfig.ENABLE_GEMINI_API ?? false;
			GEMINI_API_KEYS = geminiConfig.GEMINI_API_KEYS ?? [''];
			GEMINI_API_BASE_URL = geminiConfig.GEMINI_API_BASE_URL ?? '';
			GEMINI_API_CONFIGS = geminiConfig.GEMINI_API_CONFIGS ?? {};

			ENABLE_CLAUDE_API = claudeConfig.ENABLE_CLAUDE_API ?? false;
			CLAUDE_API_KEYS = claudeConfig.CLAUDE_API_KEYS ?? [''];
			CLAUDE_API_BASE_URL = claudeConfig.CLAUDE_API_BASE_URL ?? '';
			CLAUDE_API_CONFIGS = claudeConfig.CLAUDE_API_CONFIGS ?? {};

			if (ENABLE_OPENAI_API) {
				// get url and idx
				for (const [idx, url] of OPENAI_API_BASE_URLS.entries()) {
					if (!OPENAI_API_CONFIGS[idx]) {
						// Legacy support, url as key
						OPENAI_API_CONFIGS[idx] = OPENAI_API_CONFIGS[url] || {};
					}
				}

				OPENAI_API_BASE_URLS.forEach(async (url, idx) => {
					OPENAI_API_CONFIGS[idx] = OPENAI_API_CONFIGS[idx] || {};
					if (!(OPENAI_API_CONFIGS[idx]?.enable ?? true)) {
						return;
					}
					const res = await getOpenAIModels('', idx);
					if (res.pipelines) {
						pipelineUrls[url] = true;
					}
				});
			}

			if (ENABLE_OLLAMA_API) {
				for (const [idx, url] of OLLAMA_BASE_URLS.entries()) {
					if (!OLLAMA_API_CONFIGS[idx]) {
						OLLAMA_API_CONFIGS[idx] = OLLAMA_API_CONFIGS[url] || {};
					}
				}
			}

			// Auto-open collapsed groups whose feature is already enabled on load.
			ollamaOpen = !!ENABLE_OLLAMA_API;
			advancedOpen = Boolean(
				(directConnectionsConfig as Record<string, unknown> | null)?.ENABLE_DIRECT_CONNECTIONS
			);
		}
	});

	/**
	 * Save all connection configs in parallel, then invoke onSave callback.
	 * All updates are silent (no individual toasts) — caller handles feedback.
	 */
	const submitHandler = async () => {
		await Promise.all([
			updateOpenAIHandler(true),
			updateOllamaHandler(true),
			updateGeminiHandler(true),
			updateClaudeHandler(true),
			updateDirectConnectionsHandler(true)
		]);

		onSave?.();
	};
</script>

<AddConnectionModal
	bind:show={showAddOpenAIConnectionModal}
	onSubmit={addOpenAIConnectionHandler}
/>

<AddConnectionModal
	ollama
	bind:show={showAddOllamaConnectionModal}
	onSubmit={addOllamaConnectionHandler}
/>

<form
	class="flex flex-col h-full justify-between text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		submitHandler();
	}}
>
	<div class=" overflow-y-scroll scrollbar-hidden h-full">
		<div class="mb-2.5">
			<InfoCallout
				>{$i18n.t(
					'Connect external model providers here by configuring API base URLs and keys for OpenAI, Ollama, Gemini, and Claude. Saved connections make their models available across the workspace.'
				)}</InfoCallout
			>
		</div>
		{#if ENABLE_OPENAI_API !== null && ENABLE_OLLAMA_API !== null && directConnectionsConfig !== null}
			<!-- Hosted Provider Connections -->
			<SettingsSection title={$i18n.t('Hosted Provider Connections')}>
				<div class="my-2">
					<div class="mt-2 space-y-2 pr-1.5">
						<div class="flex justify-between items-center text-sm">
							<div class="  font-medium">{$i18n.t('OpenAI API')}</div>

							<div class="flex items-center">
								<div class="">
									<Switch
										bind:state={ENABLE_OPENAI_API}
										onchange={async () => {
											updateOpenAIHandler();
										}}
									/>
								</div>
							</div>
						</div>

						{#if ENABLE_OPENAI_API}
							<div class="mt-3 ml-1 flex flex-col gap-3 border-l border-border pl-4">
								<div class="flex flex-col gap-3">
									{#each OPENAI_API_BASE_URLS as url, idx (idx)}
										<OpenAIConnection
											pipeline={pipelineUrls[url] ? true : false}
											bind:url={OPENAI_API_BASE_URLS[idx]}
											bind:key={OPENAI_API_KEYS[idx]}
											bind:config={OPENAI_API_CONFIGS[idx]}
											onSubmit={() => {
												updateOpenAIHandler();
											}}
											onDelete={() => {
												OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS.filter(
													(url, urlIdx) => idx !== urlIdx
												);
												OPENAI_API_KEYS = OPENAI_API_KEYS.filter((key, keyIdx) => idx !== keyIdx);

												let newConfig = {};
												OPENAI_API_BASE_URLS.forEach((url, newIdx) => {
													newConfig[newIdx] =
														OPENAI_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
												});
												OPENAI_API_CONFIGS = newConfig;
												updateOpenAIHandler();
											}}
										/>
									{/each}
								</div>
								<Button
									variant="ghost"
									size="sm"
									type="button"
									class="self-start"
									onclick={() => {
										showAddOpenAIConnectionModal = true;
									}}
								>
									<Plus />
									{$i18n.t('Add Connection')}
								</Button>
							</div>
						{/if}
					</div>
				</div>

				<div class="pr-1.5 my-2">
					<div class="flex justify-between items-center text-sm mb-2">
						<div class="font-medium">{$i18n.t('Google Gemini API')}</div>
						<div class="mt-1">
							<Switch
								bind:state={ENABLE_GEMINI_API}
								onchange={async () => {
									updateGeminiHandler();
								}}
							/>
						</div>
					</div>

					{#if ENABLE_GEMINI_API}
						<div class="mt-3 ml-1 flex flex-col gap-3 border-l border-border pl-4">
							<div class="flex flex-col gap-1.5">
								<label for="gemini-base-url" class="text-xs font-medium text-muted-foreground">
									{$i18n.t('API Base URL')}
								</label>
								<Input
									id="gemini-base-url"
									mono
									placeholder="https://generativelanguage.googleapis.com/v1beta"
									bind:value={GEMINI_API_BASE_URL}
									autocomplete="off"
								/>
							</div>
							<div class="flex flex-col gap-1.5">
								<div class="text-xs font-medium text-muted-foreground">{$i18n.t('API Key')}</div>
								<SensitiveInput
									mono
									placeholder={$i18n.t('API Key')}
									bind:value={GEMINI_API_KEYS[0]}
								/>
							</div>
							<div class="text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Enable Google Gemini models (gemini-2.0-flash, gemini-2.5-pro, etc.)')}
							</div>
						</div>
					{/if}
				</div>

				<div class="pr-1.5 my-2">
					<div class="flex justify-between items-center text-sm mb-2">
						<div class="font-medium">{$i18n.t('Anthropic Claude API')}</div>
						<div class="mt-1">
							<Switch
								bind:state={ENABLE_CLAUDE_API}
								onchange={async () => {
									updateClaudeHandler();
								}}
							/>
						</div>
					</div>

					{#if ENABLE_CLAUDE_API}
						<div class="mt-3 ml-1 flex flex-col gap-3 border-l border-border pl-4">
							<div class="flex flex-col gap-1.5">
								<label for="claude-base-url" class="text-xs font-medium text-muted-foreground">
									{$i18n.t('API Base URL')}
								</label>
								<Input
									id="claude-base-url"
									mono
									placeholder="https://api.anthropic.com"
									bind:value={CLAUDE_API_BASE_URL}
									autocomplete="off"
								/>
							</div>
							<div class="flex flex-col gap-1.5">
								<div class="text-xs font-medium text-muted-foreground">{$i18n.t('API Key')}</div>
								<SensitiveInput
									mono
									placeholder={$i18n.t('API Key')}
									bind:value={CLAUDE_API_KEYS[0]}
								/>
							</div>
							<div class="text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Enable Anthropic Claude models (claude-sonnet-4, claude-opus-4, etc.)')}
							</div>
						</div>
					{/if}
				</div>
			</SettingsSection>

			<!-- Self-Hosted / Local (Ollama) -->
			<SettingsSection title={$i18n.t('Self-Hosted / Local (Ollama)')} bind:open={ollamaOpen}>
				<div class="pr-1.5 my-2">
					<div class="flex justify-between items-center text-sm mb-2">
						<div class="  font-medium">{$i18n.t('Ollama API')}</div>

						<div class="mt-1">
							<Switch
								bind:state={ENABLE_OLLAMA_API}
								onchange={async () => {
									updateOllamaHandler();
								}}
							/>
						</div>
					</div>

					{#if ENABLE_OLLAMA_API}
						<div class="my-2 h-px bg-border"></div>

						<div class="">
							<div class="flex justify-between items-center">
								<div class="font-medium">{$i18n.t('Manage Ollama API Connections')}</div>

								<Button
									variant="outline"
									size="sm"
									type="button"
									onclick={() => {
										showAddOllamaConnectionModal = true;
									}}
								>
									<Plus />

									{$i18n.t('Add Connection')}
								</Button>
							</div>

							<div class="flex w-full gap-1.5">
								<div class="flex-1 flex flex-col gap-1.5 mt-1.5">
									{#each OLLAMA_BASE_URLS as _url, idx (idx)}
										<OllamaConnection
											bind:url={OLLAMA_BASE_URLS[idx]}
											bind:config={OLLAMA_API_CONFIGS[idx]}
											{idx}
											onSubmit={() => {
												updateOllamaHandler();
											}}
											onDelete={() => {
												OLLAMA_BASE_URLS = OLLAMA_BASE_URLS.filter((url, urlIdx) => idx !== urlIdx);

												let newConfig = {};
												OLLAMA_BASE_URLS.forEach((url, newIdx) => {
													newConfig[newIdx] =
														OLLAMA_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
												});
												OLLAMA_API_CONFIGS = newConfig;
											}}
										/>
									{/each}
								</div>
							</div>

							<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Trouble accessing Ollama?')}
								<a
									class=" text-gray-300 font-medium underline"
									href="https://github.com/bccard-ai/bcgpt-webui#troubleshooting"
									target="_blank"
								>
									{$i18n.t('Click here for help.')}
								</a>
							</div>
						</div>
					{/if}
				</div>
			</SettingsSection>

			<!-- Advanced -->
			<SettingsSection title={$i18n.t('Advanced')} bind:open={advancedOpen}>
				<div class="pr-1.5 my-2">
					<div class="flex justify-between items-center text-sm">
						<div class="  font-medium">{$i18n.t('Direct Connections')}</div>

						<div class="flex items-center">
							<div class="">
								<Switch
									bind:state={directConnectionsConfig.ENABLE_DIRECT_CONNECTIONS}
									onchange={async () => {
										updateDirectConnectionsHandler();
									}}
								/>
							</div>
						</div>
					</div>

					<div class="mt-1.5">
						<div class="text-xs text-gray-500">
							{$i18n.t(
								'Direct Connections allow users to connect to their own OpenAI compatible API endpoints.'
							)}
						</div>
					</div>
				</div>
			</SettingsSection>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
