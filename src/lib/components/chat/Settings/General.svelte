<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import { getLanguages, changeLanguage } from '$lib/i18n';
	import { settings, theme, user } from '$lib/stores';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import AdvancedParams from './Advanced/AdvancedParams.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Callback to persist settings changes. */
		saveSettings: (settings: Record<string, unknown>) => void | Promise<void>;
		/** Callback invoked after settings are successfully saved. */
		onSave?: () => void;
	}

	let { saveSettings, onSave = () => {} }: Props = $props();

	/** Available theme options for the selector. */
	let themes = ['dark', 'light', 'rose-pine dark', 'rose-pine-dawn light', 'oled-dark'];
	let selectedTheme = $state('system');

	let languages: Awaited<ReturnType<typeof getLanguages>> = $state([]);
	let lang = $state($i18n.language);
	let notificationEnabled = $state(false);
	/** System prompt text. */
	let system = $state('');

	/** Whether advanced parameters section is expanded. */
	let showAdvanced = $state(false);

	/**
	 * Toggle browser notification permission and persist the setting.
	 * Shows an error toast if the user denies the permission.
	 */
	const toggleNotification = async () => {
		const permission = await Notification.requestPermission();

		if (permission === 'granted') {
			notificationEnabled = !notificationEnabled;
			saveSettings({ notificationEnabled: notificationEnabled });
		} else {
			toast.error(
				$i18n.t(
					'Response notifications cannot be activated as the website permissions have been denied. Please visit your browser settings to grant the necessary access.'
				)
			);
		}
	};

	// --- Advanced Parameters State ---
	let requestFormat = $state<string | object | null>(null);
	let keepAlive: string | null = $state(null);

	let params = $state({
		// Advanced
		stream_response: null,
		function_calling: null,
		seed: null,
		temperature: null,
		reasoning_effort: null,
		logit_bias: null,
		frequency_penalty: null,
		presence_penalty: null,
		repeat_penalty: null,
		repeat_last_n: null,
		mirostat: null,
		mirostat_eta: null,
		mirostat_tau: null,
		top_k: null,
		top_p: null,
		min_p: null,
		stop: null,
		tfs_z: null,
		num_ctx: null,
		num_batch: null,
		num_keep: null,
		max_tokens: null,
		num_gpu: null
	});

	/**
	 * Validate that a string is valid JSON and is an object.
	 * @param json - The JSON string to validate.
	 * @returns True if the string parses to a valid object.
	 */
	const validateJSON = (json: string): boolean => {
		try {
			const obj = JSON.parse(json);
			return !!(obj && typeof obj === 'object');
		} catch {
			return false;
		}
	};

	/** Toggle the request format between null and 'json'. */
	const toggleRequestFormat = async () => {
		requestFormat = requestFormat === null ? 'json' : null;
		saveSettings({ requestFormat: requestFormat !== null ? requestFormat : undefined });
	};

	/**
	 * Validate and persist all general settings including system prompt,
	 * advanced parameters, keep-alive, and request format.
	 */
	const saveHandler = async () => {
		if (requestFormat !== null && requestFormat !== 'json') {
			if (validateJSON(requestFormat) === false) {
				toast.error($i18n.t('Invalid JSON schema'));
				return;
			} else {
				requestFormat = JSON.parse(requestFormat);
			}
		}

		saveSettings({
			system: system !== '' ? system : undefined,
			params: {
				stream_response: params.stream_response !== null ? params.stream_response : undefined,
				function_calling: params.function_calling !== null ? params.function_calling : undefined,
				seed: (params.seed !== null ? params.seed : undefined) ?? undefined,
				stop: params.stop ? params.stop.split(',').filter((e: string) => e) : undefined,
				temperature: params.temperature !== null ? params.temperature : undefined,
				reasoning_effort: params.reasoning_effort !== null ? params.reasoning_effort : undefined,
				logit_bias: params.logit_bias !== null ? params.logit_bias : undefined,
				frequency_penalty: params.frequency_penalty !== null ? params.frequency_penalty : undefined,
				presence_penalty: params.frequency_penalty !== null ? params.frequency_penalty : undefined,
				repeat_penalty: params.frequency_penalty !== null ? params.frequency_penalty : undefined,
				repeat_last_n: params.repeat_last_n !== null ? params.repeat_last_n : undefined,
				mirostat: params.mirostat !== null ? params.mirostat : undefined,
				mirostat_eta: params.mirostat_eta !== null ? params.mirostat_eta : undefined,
				mirostat_tau: params.mirostat_tau !== null ? params.mirostat_tau : undefined,
				top_k: params.top_k !== null ? params.top_k : undefined,
				top_p: params.top_p !== null ? params.top_p : undefined,
				min_p: params.min_p !== null ? params.min_p : undefined,
				tfs_z: params.tfs_z !== null ? params.tfs_z : undefined,
				num_ctx: params.num_ctx !== null ? params.num_ctx : undefined,
				num_batch: params.num_batch !== null ? params.num_batch : undefined,
				num_keep: params.num_keep !== null ? params.num_keep : undefined,
				max_tokens: params.max_tokens !== null ? params.max_tokens : undefined,
				use_mmap: params.use_mmap !== null ? params.use_mmap : undefined,
				use_mlock: params.use_mlock !== null ? params.use_mlock : undefined,
				num_thread: params.num_thread !== null ? params.num_thread : undefined,
				num_gpu: params.num_gpu !== null ? params.num_gpu : undefined
			},
			keepAlive: keepAlive ? (isNaN(keepAlive) ? keepAlive : parseInt(keepAlive)) : undefined,
			requestFormat: requestFormat !== null ? requestFormat : undefined
		});
		onSave?.();

		requestFormat =
			typeof requestFormat === 'object' ? JSON.stringify(requestFormat, null, 2) : requestFormat;
	};

	onMount(async () => {
		selectedTheme = localStorage.theme ?? 'system';

		languages = await getLanguages();

		notificationEnabled = get(settings).notificationEnabled ?? false;
		system = get(settings).system ?? '';

		requestFormat = get(settings).requestFormat ?? null;
		if (requestFormat !== null && requestFormat !== 'json') {
			requestFormat =
				typeof requestFormat === 'object' ? JSON.stringify(requestFormat, null, 2) : requestFormat;
		}

		keepAlive = get(settings).keepAlive ?? null;

		params = { ...params, ...get(settings).params };
		params.stop = get(settings)?.params?.stop
			? (get(settings)?.params?.stop ?? []).join(',')
			: null;
	});

	/**
	 * Apply a visual theme to the document by setting CSS classes and custom properties.
	 * Handles 'system', 'dark', 'light', 'oled-dark' themes.
	 * @param _theme - The theme identifier to apply.
	 */
	const applyTheme = (_theme: string) => {
		let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

		if (_theme === 'system') {
			themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}

		if (themeToApply === 'dark' && !_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#333');
			document.documentElement.style.setProperty('--color-gray-850', '#262626');
			document.documentElement.style.setProperty('--color-gray-900', '#171717');
			document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
		}

		themes
			.filter((e) => e !== themeToApply)
			.forEach((e) => {
				e.split(' ').forEach((cls) => {
					document.documentElement.classList.remove(cls);
				});
			});

		themeToApply.split(' ').forEach((cls) => {
			document.documentElement.classList.add(cls);
		});

		const metaThemeColor = document.querySelector('meta[name="theme-color"]');
		if (metaThemeColor) {
			if (_theme.includes('system')) {
				const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
					? 'dark'
					: 'light';
				metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
			} else {
				metaThemeColor.setAttribute(
					'content',
					_theme === 'dark'
						? '#171717'
						: _theme === 'oled-dark'
							? '#000000'
							: _theme === 'her'
								? '#983724'
								: '#ffffff'
				);
			}
		}

		if (typeof window !== 'undefined' && window.applyTheme) {
			window.applyTheme();
		}

		if (_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#101010');
			document.documentElement.style.setProperty('--color-gray-850', '#050505');
			document.documentElement.style.setProperty('--color-gray-900', '#000000');
			document.documentElement.style.setProperty('--color-gray-950', '#000000');
			document.documentElement.classList.add('dark');
		}
	};

	/** Persist the selected theme and apply it immediately. */
	const themeChangeHandler = (_theme: string) => {
		theme.set(_theme);
		localStorage.setItem('theme', _theme);
		applyTheme(_theme);
	};
</script>

<div class="flex flex-col h-full justify-between text-sm">
	<div class="  overflow-y-scroll max-h-[28rem] lg:max-h-full">
		<div class="">
			<div class=" mb-1 text-sm font-medium">{$i18n.t('WebUI Settings')}</div>

			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">{$i18n.t('Theme')}</div>
				<div class="flex items-center relative">
					<select
						class=" dark:bg-gray-900 w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent outline-hidden text-right"
						bind:value={selectedTheme}
						placeholder={$i18n.t('Select a theme')}
						onchange={() => themeChangeHandler(selectedTheme)}
					>
						<option value="system">⚙️ {$i18n.t('System')}</option>
						<option value="dark">🌑 {$i18n.t('Dark')}</option>
						<option value="oled-dark">🌃 {$i18n.t('OLED Dark')}</option>
						<option value="light">☀️ {$i18n.t('Light')}</option>
						<option value="her">🌷 Her</option>
						<!-- <option value="rose-pine dark">🪻 {$i18n.t('Rosé Pine')}</option>
						<option value="rose-pine-dawn light">🌷 {$i18n.t('Rosé Pine Dawn')}</option> -->
					</select>
				</div>
			</div>

			<div
				class=" flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">{$i18n.t('Language')}</div>
				<div class="flex items-center relative">
					<select
						class=" dark:bg-gray-900 w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent outline-hidden text-right"
						bind:value={lang}
						placeholder={$i18n.t('Select a language')}
						onchange={() => {
							changeLanguage(lang);
						}}
					>
						{#each languages as language (language['code'])}
							<option value={language['code']}>{language['title']}</option>
						{/each}
					</select>
				</div>
			</div>
			{#if $i18n.language === 'en-US'}
				<div class="mb-2 text-xs text-gray-400 dark:text-gray-500">
					{$i18n.t("Couldn't find your language?")}
					<a
						class=" text-gray-300 font-medium underline"
						href="https://github.com/bccard-ai/bcgpt-webui/blob/main/docs/CONTRIBUTING.md#-translations-and-internationalization"
						target="_blank"
					>
						{$i18n.t('Help us translate BCGPT!')}
					</a>
				</div>
			{/if}

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">{$i18n.t('Notifications')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={toggleNotification}
						type="button"
					>
						{#if notificationEnabled === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>
		</div>

		{#if $user.role === 'admin' || $user?.permissions.chat?.controls}
			<hr class="border-gray-100 dark:border-gray-850 my-3" />

			<div>
				<div class=" my-2.5 text-sm font-medium">{$i18n.t('System Prompt')}</div>
				<textarea
					bind:value={system}
					class="w-full rounded-lg p-4 text-sm bg-white dark:text-gray-300 dark:bg-gray-850 outline-hidden resize-none"
					rows="4"
				></textarea>
			</div>

			<div class="mt-2 space-y-3 pr-1.5">
				<div class="flex justify-between items-center text-sm">
					<div class="  font-medium">{$i18n.t('Advanced Parameters')}</div>
					<button
						class=" text-xs font-medium text-gray-500"
						type="button"
						onclick={() => (showAdvanced = !showAdvanced)}>{showAdvanced ? $i18n.t('Hide') : $i18n.t('Show')}</button
					>
				</div>

				{#if showAdvanced}
					<AdvancedParams admin={$user?.role === 'admin'} bind:params />
					<hr class=" border-gray-100 dark:border-gray-850" />

					<div class=" w-full justify-between">
						<div
							class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
						>
							<div class=" self-center text-md font-medium">{$i18n.t('Keep Alive')}</div>

							<button
								class="p-1 px-3 text-xs flex rounded-sm transition"
								type="button"
								onclick={() => (keepAlive = keepAlive === null ? '5m' : null)}
							>
								{#if keepAlive === null}
									<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
								{:else}
									<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
								{/if}
							</button>
						</div>

						{#if keepAlive !== null}
							<div class="flex mt-1 space-x-2">
								<input
									class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									type="text"
									placeholder={$i18n.t("e.g. '30s','10m'. Valid time units are 's', 'm', 'h'.")}
									bind:value={keepAlive}
								/>
							</div>
						{/if}
					</div>

					<div>
						<div
							class=" flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
						>
							<div class=" self-center text-md font-medium">{$i18n.t('Request Mode')}</div>

							<button
								class="p-1 px-3 text-xs flex rounded-sm transition"
								onclick={toggleRequestFormat}
							>
								{#if requestFormat === null}
									<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
								{:else}
									<!-- <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            class="w-4 h-4 self-center"
                        >
                            <path
                                d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.06 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06l-1.06-1.06a.75.75 0 10-1.061 1.06l1.06 1.06z"
                            />
                        </svg> -->
									<span class="ml-2 self-center"> {$i18n.t('JSON')} </span>
								{/if}
							</button>
						</div>

						{#if requestFormat !== null}
							<div class="flex mt-1 space-x-2">
								<Textarea
									className="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									placeholder={$i18n.t('e.g. "json" or a JSON schema')}
									bind:value={requestFormat}
								/>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			onclick={saveHandler}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</div>
