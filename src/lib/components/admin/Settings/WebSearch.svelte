<script lang="ts">
	/**
	 * Admin Web Search Settings
	 *
	 * Configures web search providers (18 engines including Naver, Google PSE,
	 * Brave, etc.), search result options, query rewrite, domain filtering,
	 * and YouTube loader settings.
	 */
	import { preventDefault } from 'svelte/legacy';

	import { getRAGConfig, updateRAGConfig } from '$lib/apis/retrieval';
	import Switch from '$lib/components/common/Switch.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';

	import { models } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Parent save handler called after form submit */
		saveHandler: () => void;
	}

	let { saveHandler }: Props = $props();

	/** Web search and crawler configuration from backend */
	let webConfig = $state<Record<string, unknown> | null>(null);

	/** Available search engine identifiers */
	let webSearchEngines = $state([
		'naver',
		'searxng',
		'google_pse',
		'brave',
		'kagi',
		'mojeek',
		'bocha',
		'serpstack',
		'serper',
		'serply',
		'searchapi',
		'serpapi',
		'duckduckgo',
		'tavily',
		'jina',
		'bing',
		'exa',
		'perplexity'
	]);

	let youtubeLanguage = $state('en');
	let youtubeTranslation = null;
	let youtubeProxyUrl = $state('');

	/** Query Rewrite section starts collapsed unless already enabled (set on load). */
	let queryRewriteOpen = $state(false);

	const submitHandler = async () => {
		// Convert domain filter string to array before sending
		if (webConfig.search.domain_filter_list) {
			webConfig.search.domain_filter_list = webConfig.search.domain_filter_list
				.split(',')
				.map((domain) => domain.trim())
				.filter((domain) => domain.length > 0);
		} else {
			webConfig.search.domain_filter_list = [];
		}

		await updateRAGConfig('', {
			web: webConfig,
			youtube: {
				language: youtubeLanguage.split(',').map((lang) => lang.trim()),
				translation: youtubeTranslation,
				proxy_url: youtubeProxyUrl
			}
		});

		webConfig.search.domain_filter_list = webConfig.search.domain_filter_list.join(', ');
	};

	onMount(async () => {
		const res = await getRAGConfig('');

		if (res) {
			webConfig = res.web;
			// Convert array back to comma-separated string for display
			if (webConfig?.search?.domain_filter_list) {
				webConfig.search.domain_filter_list = webConfig.search.domain_filter_list.join(', ');
			}

			youtubeLanguage = res.youtube.language.join(',');
			youtubeTranslation = res.youtube.translation;
			youtubeProxyUrl = res.youtube.proxy_url;

			// Auto-open the Query Rewrite group if the feature is already enabled.
			queryRewriteOpen = Boolean(
				(webConfig?.search as Record<string, unknown> | undefined)?.query_rewrite_enabled
			);
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(async () => {
		await submitHandler();
		saveHandler();
	})}
>
	<div class=" space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		{#if webConfig}
			<div class="">
				<div class="mb-2.5">
					<InfoCallout
						>{$i18n.t(
							'Configure the web search provider and crawling options used to fetch live web results for RAG.'
						)}</InfoCallout
					>
				</div>

				<!-- Web Search -->
				<SettingsSection title={$i18n.t('Web Search')}>
					<Field inline separator label={$i18n.t('Web Search')}>
						<Switch bind:state={webConfig.search.enabled} />
					</Field>

					<Field inline separator label={$i18n.t('Web Search Engine')}>
						<select
							class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors cursor-pointer appearance-none focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							bind:value={webConfig.search.engine}
							placeholder={$i18n.t('Select a engine')}
							required
						>
							<option disabled selected value="">{$i18n.t('Select a engine')}</option>
							{#each webSearchEngines as engine (engine)}
								<option value={engine}>{engine}</option>
							{/each}
						</select>
					</Field>
				</SettingsSection>

				<!-- Provider Credentials -->
				<SettingsSection title={$i18n.t('Provider Credentials')}>
					{#if webConfig.search.engine !== ''}
						{#if webConfig.search.engine === 'naver'}
							<div class="flex flex-col gap-2.5">
								<Field label={$i18n.t('Naver Client ID')}>
									<input
										class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
										type="text"
										placeholder={$i18n.t('Enter Naver Client ID')}
										bind:value={webConfig.search.naver_client_id}
										autocomplete="off"
									/>
								</Field>

								<Field label={$i18n.t('Naver Client Secret')}>
									<SensitiveInput
										mono
										placeholder={$i18n.t('Enter Naver Client Secret')}
										bind:value={webConfig.search.naver_client_secret}
									/>
								</Field>

								<Field label={$i18n.t('Naver Search Endpoints')}>
									<div class="flex gap-3 flex-wrap pt-1">
										{#each ['webkr', 'news', 'blog', 'cafearticle', 'kin'] as ep (ep)}
											<label class="flex items-center gap-1.5 text-sm cursor-pointer">
												<input
													type="checkbox"
													class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
													checked={webConfig.search.naver_search_endpoints
														?.split(',')
														.map((s) => s.trim())
														.includes(ep) ?? false}
													onchange={(e: CustomEvent) => {
														let endpoints = (webConfig.search.naver_search_endpoints || 'webkr')
															.split(',')
															.map((s) => s.trim())
															.filter(Boolean);
														if (e.target?.checked) {
															if (!endpoints.includes(ep)) endpoints.push(ep);
														} else {
															endpoints = endpoints.filter((x) => x !== ep);
														}
														webConfig.search.naver_search_endpoints =
															endpoints.length > 0 ? endpoints.join(',') : 'webkr';
													}}
												/>
												{ep}
											</label>
										{/each}
									</div>
								</Field>
							</div>
						{:else if webConfig.search.engine === 'searxng'}
							<Field label={$i18n.t('Searxng Query URL')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="text"
									placeholder={$i18n.t('Enter Searxng Query URL')}
									bind:value={webConfig.search.searxng_query_url}
									autocomplete="off"
								/>
							</Field>
						{:else if webConfig.search.engine === 'google_pse'}
							<div class="flex flex-col gap-2.5">
								<Field label={$i18n.t('Google PSE API Key')}>
									<SensitiveInput
										mono
										placeholder={$i18n.t('Enter Google PSE API Key')}
										bind:value={webConfig.search.google_pse_api_key}
									/>
								</Field>

								<Field label={$i18n.t('Google PSE Engine Id')}>
									<input
										class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
										type="text"
										placeholder={$i18n.t('Enter Google PSE Engine Id')}
										bind:value={webConfig.search.google_pse_engine_id}
										autocomplete="off"
									/>
								</Field>
							</div>
						{:else if webConfig.search.engine === 'brave'}
							<Field label={$i18n.t('Brave Search API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Brave Search API Key')}
									bind:value={webConfig.search.brave_search_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'kagi'}
							<Field label={$i18n.t('Kagi Search API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Kagi Search API Key')}
									bind:value={webConfig.search.kagi_search_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'mojeek'}
							<Field label={$i18n.t('Mojeek Search API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Mojeek Search API Key')}
									bind:value={webConfig.search.mojeek_search_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'bocha'}
							<Field label={$i18n.t('Bocha Search API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Bocha Search API Key')}
									bind:value={webConfig.search.bocha_search_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'serpstack'}
							<Field label={$i18n.t('Serpstack API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Serpstack API Key')}
									bind:value={webConfig.search.serpstack_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'serper'}
							<Field label={$i18n.t('Serper API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Serper API Key')}
									bind:value={webConfig.search.serper_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'serply'}
							<Field label={$i18n.t('Serply API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Serply API Key')}
									bind:value={webConfig.search.serply_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'searchapi'}
							<div class="flex flex-col gap-2.5">
								<Field label={$i18n.t('SearchApi API Key')}>
									<SensitiveInput
										mono
										placeholder={$i18n.t('Enter SearchApi API Key')}
										bind:value={webConfig.search.searchapi_api_key}
									/>
								</Field>

								<Field label={$i18n.t('SearchApi Engine')}>
									<input
										class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
										type="text"
										placeholder={$i18n.t('Enter SearchApi Engine')}
										bind:value={webConfig.search.searchapi_engine}
										autocomplete="off"
									/>
								</Field>
							</div>
						{:else if webConfig.search.engine === 'serpapi'}
							<div class="flex flex-col gap-2.5">
								<Field label={$i18n.t('SerpApi API Key')}>
									<SensitiveInput
										mono
										placeholder={$i18n.t('Enter SerpApi API Key')}
										bind:value={webConfig.search.serpapi_api_key}
									/>
								</Field>

								<Field label={$i18n.t('SerpApi Engine')}>
									<input
										class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
										type="text"
										placeholder={$i18n.t('Enter SerpApi Engine')}
										bind:value={webConfig.search.serpapi_engine}
										autocomplete="off"
									/>
								</Field>
							</div>
						{:else if webConfig.search.engine === 'tavily'}
							<Field label={$i18n.t('Tavily API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Tavily API Key')}
									bind:value={webConfig.search.tavily_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'jina'}
							<Field label={$i18n.t('Jina API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Jina API Key')}
									bind:value={webConfig.search.jina_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'exa'}
							<Field label={$i18n.t('Exa API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Exa API Key')}
									bind:value={webConfig.search.exa_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'perplexity'}
							<Field label={$i18n.t('Perplexity API Key')}>
								<SensitiveInput
									mono
									placeholder={$i18n.t('Enter Perplexity API Key')}
									bind:value={webConfig.search.perplexity_api_key}
								/>
							</Field>
						{:else if webConfig.search.engine === 'bing'}
							<div class="flex flex-col gap-2.5">
								<Field label={$i18n.t('Bing Search V7 Endpoint')}>
									<input
										class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
										type="text"
										placeholder={$i18n.t('Enter Bing Search V7 Endpoint')}
										bind:value={webConfig.search.bing_search_v7_endpoint}
										autocomplete="off"
									/>
								</Field>

								<Field label={$i18n.t('Bing Search V7 Subscription Key')}>
									<SensitiveInput
										mono
										placeholder={$i18n.t('Enter Bing Search V7 Subscription Key')}
										bind:value={webConfig.search.bing_search_v7_subscription_key}
									/>
								</Field>
							</div>
						{/if}
					{/if}
				</SettingsSection>

				<!-- Query Rewrite (collapsed; auto-opens when already enabled) -->
				<SettingsSection title={$i18n.t('Query Rewrite')} bind:open={queryRewriteOpen}>
					{#if webConfig.search.enabled}
						<div
							class="mb-2.5 flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
						>
							<div class="min-w-0 text-sm font-medium text-foreground">
								<Tooltip
									content={$i18n.t(
										'Use LLM to rewrite and expand search queries for better results'
									)}
									placement="top-start"
								>
									{$i18n.t('Query Rewrite / Expand')}
								</Tooltip>
							</div>
							<div class="flex shrink-0 items-center">
								<Switch bind:state={webConfig.search.query_rewrite_enabled} />
							</div>
						</div>

						{#if webConfig.search.query_rewrite_enabled}
							<Field class="mt-1" label={$i18n.t('Query Rewrite Model')}>
								<select
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors cursor-pointer appearance-none focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									bind:value={webConfig.search.query_rewrite_model}
								>
									<option value="">{$i18n.t('Use Task Model (Default)')}</option>
									{#each $models as model (model.id)}
										<option value={model.id}>{model.name}</option>
									{/each}
								</select>
							</Field>

							<div
								class="mt-2.5 mb-2.5 flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
							>
								<div class="min-w-0 text-sm font-medium text-foreground">
									<Tooltip
										content={$i18n.t(
											'Send multiple rewritten queries concurrently and merge results'
										)}
										placement="top-start"
									>
										{$i18n.t('Concurrent Query Search')}
									</Tooltip>
								</div>
								<div class="flex shrink-0 items-center">
									<Switch bind:state={webConfig.search.concurrent_queries} />
								</div>
							</div>
						{/if}
					{/if}
				</SettingsSection>

				<!-- Result Tuning -->
				<SettingsSection title={$i18n.t('Result Tuning')}>
					{#if webConfig.search.enabled}
						<div class="flex gap-2">
							<Field class="w-full" label={$i18n.t('Search Result Count')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									placeholder={$i18n.t('Search Result Count')}
									bind:value={webConfig.search.result_count}
									required
								/>
							</Field>

							<Field class="w-full" label={$i18n.t('Concurrent Requests')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									placeholder={$i18n.t('Concurrent Requests')}
									bind:value={webConfig.search.concurrent_requests}
									required
								/>
							</Field>
						</div>

						<Field class="mt-2.5" label={$i18n.t('Domain Filter List')}>
							<input
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								placeholder={$i18n.t(
									'Enter domains separated by commas (e.g., example.com,site.org)'
								)}
								bind:value={webConfig.search.domain_filter_list}
							/>
						</Field>
					{/if}
				</SettingsSection>

				<!-- Advanced (collapsed) -->
				<SettingsSection title={$i18n.t('Advanced')} open={false}>
					<div
						class="mb-2.5 flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
					>
						<div class="min-w-0 text-sm font-medium text-foreground">
							<Tooltip content={$i18n.t('Full Context Mode')} placement="top-start">
								{$i18n.t('Bypass Embedding and Retrieval')}
							</Tooltip>
						</div>
						<div class="flex shrink-0 items-center">
							<Tooltip
								content={webConfig.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL
									? $i18n.t(
											'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
										)
									: $i18n.t(
											'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
										)}
							>
								<Switch bind:state={webConfig.BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL} />
							</Tooltip>
						</div>
					</div>

					<div
						class="mb-2.5 flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
					>
						<div class="min-w-0 text-sm font-medium text-foreground">
							{$i18n.t('Trust Proxy Environment')}
						</div>
						<div class="flex shrink-0 items-center">
							<Tooltip
								content={webConfig.search.trust_env
									? $i18n.t(
											'Use proxy designated by http_proxy and https_proxy environment variables to fetch page contents'
										)
									: $i18n.t('Use no proxy to fetch page contents.')}
							>
								<Switch bind:state={webConfig.search.trust_env} />
							</Tooltip>
						</div>
					</div>

					<div
						class="mb-2.5 flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
					>
						<div class="min-w-0 text-sm font-medium text-foreground">
							{$i18n.t('Bypass SSL verification for Websites')}
						</div>
						<div class="flex shrink-0 items-center">
							<Switch bind:state={webConfig.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION} />
						</div>
					</div>
				</SettingsSection>

				<!-- YouTube Loader (collapsed) -->
				<SettingsSection title={$i18n.t('YouTube Loader')} open={false}>
					<Field inline separator label={$i18n.t('Youtube Language')}>
						<Input
							class="w-64"
							type="text"
							placeholder={$i18n.t('Enter language codes')}
							bind:value={youtubeLanguage}
							autocomplete="off"
						/>
					</Field>

					<Field class="mt-2.5" label={$i18n.t('Youtube Proxy URL')}>
						<Input
							type="text"
							placeholder={$i18n.t('Enter proxy URL (e.g. https://user:password@host:port)')}
							bind:value={youtubeProxyUrl}
							autocomplete="off"
						/>
					</Field>
				</SettingsSection>
			</div>
		{/if}
	</div>
	<div class="flex justify-end pt-3">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
