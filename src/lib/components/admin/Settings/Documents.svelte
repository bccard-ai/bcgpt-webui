<script lang="ts">
	/**
	 * Admin Documents Settings
	 *
	 * Configures document processing: content extraction engines, chunking,
	 * embedding models, retrieval settings (hybrid search, reranking, top-K),
	 * file limits, cloud integrations, and danger zone operations.
	 */
	import { preventDefault } from 'svelte/legacy';
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import {
		getQuerySettings,
		updateQuerySettings,
		resetVectorDB,
		getRerankingConfig,
		updateRerankingConfig,
		getRAGConfig,
		updateRAGConfig
	} from '$lib/apis/retrieval';
	import { deleteAllFiles } from '$lib/apis/files';
	import { models } from '$lib/stores';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import ResetUploadDirConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import ResetVectorDBConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Selector from '$lib/components/common/Selector.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Callback invoked after settings are saved */
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Token-driven classes matching the kit <Input size="sm">, applied to the
	 * native number inputs whose `bind:value` is number/nullable and therefore
	 * cannot bind to the kit Input's string-typed value without a type error.
	 * Width is intentionally omitted so each call site can set its own.
	 */
	const nativeInputClass =
		'h-8 rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50';

	// --- Loading states ---
	let updateRerankingModelLoading = $state(false);

	// --- Dialog states ---
	let showResetConfirm = $state(false);
	let showResetUploadDirConfirm = $state(false);

	// --- Embedding configuration ---
	let embeddingModel = $state('');
	let rerankingModel = $state('');

	// --- File limits ---
	let fileMaxSize = $state<string | null>(null);
	let fileMaxCount = $state<string | null>(null);

	// --- Content extraction ---
	let contentExtractionEngine = $state('default');
	let tikaServerUrl = $state('');
	let doclingServerUrl = $state('');
	let documentIntelligenceEndpoint = $state('');
	let documentIntelligenceKey = $state('');

	// --- Chunking ---
	let textSplitter = $state('');
	let chunkSize = $state(0);
	let chunkOverlap = $state(0);
	let pdfExtractImages = $state(true);

	// --- RAG modes ---
	let RAG_FULL_CONTEXT = $state(false);
	let BYPASS_EMBEDDING_AND_RETRIEVAL = $state(false);

	// --- Cloud integrations ---
	let enableGoogleDriveIntegration = $state(false);
	let enableOneDriveIntegration = $state(false);

	// --- Query/retrieval settings ---
	let querySettings = $state({
		template: '',
		r: 0.0,
		k: 4,
		k_reranker: 4,
		hybrid: false
	});

	// --- Collapsible group open states ---
	// Advanced groups start collapsed but auto-open when their feature is already
	// configured on load (set in onMount after config loads, mirroring General.svelte's LDAP).
	let chunkingOpen = $state(false);
	let rerankingOpen = $state(false);

	/** Update the reranking model */
	const rerankingModelUpdateHandler = async () => {
		updateRerankingModelLoading = true;
		const res = await updateRerankingConfig('', {
			reranking_model: rerankingModel
		}).catch(async (error) => {
			toast.error(`${error}`);
			await setRerankingConfig();
			return null;
		});
		updateRerankingModelLoading = false;

		if (res?.status === true) {
			const msg =
				rerankingModel === ''
					? $i18n.t('Reranking model disabled', res)
					: $i18n.t('Reranking model set to "{{reranking_model}}"', res);
			toast.success(msg, { duration: 1000 * 10 });
		}
	};

	/** Validate content extraction engine config before submit */
	const validateContentExtraction = (): boolean => {
		if (contentExtractionEngine === 'tika' && tikaServerUrl === '') {
			toast.error($i18n.t('Tika Server URL required.'));
			return false;
		}
		if (contentExtractionEngine === 'docling' && doclingServerUrl === '') {
			toast.error($i18n.t('Docling Server URL required.'));
			return false;
		}
		if (
			contentExtractionEngine === 'document_intelligence' &&
			(documentIntelligenceEndpoint === '' || documentIntelligenceKey === '')
		) {
			toast.error($i18n.t('Document Intelligence endpoint and key required.'));
			return false;
		}
		return true;
	};

	/** Save all document settings */
	const submitHandler = async () => {
		if (!validateContentExtraction()) return;

		if (!BYPASS_EMBEDDING_AND_RETRIEVAL && querySettings.hybrid) {
			await rerankingModelUpdateHandler();
		}

		await updateRAGConfig('', {
			embedding_model: embeddingModel,
			pdf_extract_images: pdfExtractImages,
			enable_google_drive_integration: enableGoogleDriveIntegration,
			enable_onedrive_integration: enableOneDriveIntegration,
			file: {
				max_size: fileMaxSize === '' ? null : fileMaxSize,
				max_count: fileMaxCount === '' ? null : fileMaxCount
			},
			RAG_FULL_CONTEXT,
			BYPASS_EMBEDDING_AND_RETRIEVAL,
			chunk: { text_splitter: textSplitter, chunk_overlap: chunkOverlap, chunk_size: chunkSize },
			content_extraction: {
				engine: contentExtractionEngine,
				tika_server_url: tikaServerUrl,
				docling_server_url: doclingServerUrl,
				document_intelligence_config: {
					key: documentIntelligenceKey,
					endpoint: documentIntelligenceEndpoint
				}
			}
		});

		await updateQuerySettings('', querySettings);
		onSave?.();
	};

	/** Load reranking config from backend */
	const setRerankingConfig = async () => {
		const rerankingConfig = await getRerankingConfig('');
		if (rerankingConfig) {
			rerankingModel = rerankingConfig.reranking_model;
		}
	};

	/** Toggle hybrid search and persist immediately */
	const toggleHybridSearch = async () => {
		querySettings = await updateQuerySettings('', querySettings);
	};

	/** Reset upload directory */
	const handleResetUploadDir = async () => {
		const res = await deleteAllFiles('').catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) toast.success($i18n.t('Success'));
	};

	/** Reset vector DB */
	const handleResetVectorDB = async () => {
		const res = await resetVectorDB('').catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) toast.success($i18n.t('Success'));
	};

	onMount(async () => {
		await setRerankingConfig();
		querySettings = await getQuerySettings('');

		const res = await getRAGConfig('');
		if (res) {
			embeddingModel = res.embedding_model ?? '';
			pdfExtractImages = res.pdf_extract_images;
			textSplitter = res.chunk.text_splitter;
			chunkSize = res.chunk.chunk_size;
			chunkOverlap = res.chunk.chunk_overlap;
			RAG_FULL_CONTEXT = res.RAG_FULL_CONTEXT;
			BYPASS_EMBEDDING_AND_RETRIEVAL = res.BYPASS_EMBEDDING_AND_RETRIEVAL;
			contentExtractionEngine = res.content_extraction.engine;
			tikaServerUrl = res.content_extraction.tika_server_url;
			doclingServerUrl = res.content_extraction.docling_server_url;
			documentIntelligenceEndpoint = res.content_extraction.document_intelligence_config.endpoint;
			documentIntelligenceKey = res.content_extraction.document_intelligence_config.key;
			fileMaxSize = res?.file.max_size ?? '';
			fileMaxCount = res?.file.max_count ?? '';
			enableGoogleDriveIntegration = res.enable_google_drive_integration;
			enableOneDriveIntegration = res.enable_onedrive_integration;
		}

		// Auto-open advanced groups whose feature is already active on load.
		chunkingOpen = !BYPASS_EMBEDDING_AND_RETRIEVAL;
		rerankingOpen = querySettings.hybrid;
	});
</script>

<ResetUploadDirConfirmDialog
	bind:show={showResetUploadDirConfirm}
	onconfirm={handleResetUploadDir}
/>
<ResetVectorDBConfirmDialog bind:show={showResetConfirm} onconfirm={handleResetVectorDB} />

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(submitHandler)}
>
	<div class="space-y-2.5 overflow-y-scroll scrollbar-hidden h-full pr-1.5">
		<InfoCallout>
			{$i18n.t(
				'Configure how uploaded documents are extracted, chunked, embedded, and retrieved for use in chat.'
			)}
		</InfoCallout>

		<!-- Content Extraction -->
		<SettingsSection title={$i18n.t('Content Extraction')}>
			<Field inline separator label={$i18n.t('Content Extraction Engine')}>
				<Select
					class="w-48"
					bind:value={contentExtractionEngine}
					items={[
						{ value: '', label: $i18n.t('Default') },
						{ value: 'tika', label: $i18n.t('Tika') },
						{ value: 'docling', label: $i18n.t('Docling') },
						{ value: 'document_intelligence', label: $i18n.t('Document Intelligence') }
					]}
				/>
			</Field>

			{#if contentExtractionEngine === 'tika'}
				<div class="flex w-full">
					<Input
						size="sm"
						placeholder={$i18n.t('Enter Tika Server URL')}
						bind:value={tikaServerUrl}
					/>
				</div>
			{:else if contentExtractionEngine === 'docling'}
				<div class="flex w-full">
					<Input
						size="sm"
						placeholder={$i18n.t('Enter Docling Server URL')}
						bind:value={doclingServerUrl}
					/>
				</div>
			{:else if contentExtractionEngine === 'document_intelligence'}
				<div class="flex w-full gap-2">
					<Input
						size="sm"
						placeholder={$i18n.t('Enter Document Intelligence Endpoint')}
						bind:value={documentIntelligenceEndpoint}
					/>
					<SensitiveInput
						placeholder={$i18n.t('Enter Document Intelligence Key')}
						bind:value={documentIntelligenceKey}
					/>
				</div>
			{/if}

			{#if contentExtractionEngine === ''}
				<Field inline separator label={$i18n.t('PDF Extract Images (OCR)')}>
					<Switch bind:state={pdfExtractImages} />
				</Field>
			{/if}

			<div
				class="mb-2.5 flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
			>
				<Tooltip content={$i18n.t('Full Context Mode')} placement="top-start">
					<div class="text-sm font-medium text-foreground">
						{$i18n.t('Bypass Embedding and Retrieval')}
					</div>
				</Tooltip>
				<Tooltip
					content={BYPASS_EMBEDDING_AND_RETRIEVAL
						? $i18n.t(
								'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
							)
						: $i18n.t(
								'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
							)}
				>
					<Switch bind:state={BYPASS_EMBEDDING_AND_RETRIEVAL} />
				</Tooltip>
			</div>
		</SettingsSection>

		{#if !BYPASS_EMBEDDING_AND_RETRIEVAL}
			<!-- Chunking -->
			<SettingsSection title={$i18n.t('Chunking')} bind:open={chunkingOpen}>
				<Field inline separator label={$i18n.t('Text Splitter')}>
					<Select
						class="w-48"
						bind:value={textSplitter}
						items={[
							{ value: '', label: `${$i18n.t('Default')} (${$i18n.t('Character')})` },
							{ value: 'token', label: `${$i18n.t('Token')} (${$i18n.t('Tiktoken')})` }
						]}
					/>
				</Field>

				<div class="mb-2.5 flex w-full gap-2 border-b border-dashed border-border pb-2">
					<Field class="w-full" label={$i18n.t('Chunk Size')}>
						<input
							class={`${nativeInputClass} w-full`}
							type="number"
							placeholder={$i18n.t('Enter Chunk Size')}
							bind:value={chunkSize}
							autocomplete="off"
							min="0"
						/>
					</Field>
					<Field class="w-full" label={$i18n.t('Chunk Overlap')}>
						<input
							class={`${nativeInputClass} w-full`}
							type="number"
							placeholder={$i18n.t('Enter Chunk Overlap')}
							bind:value={chunkOverlap}
							autocomplete="off"
							min="0"
						/>
					</Field>
				</div>
			</SettingsSection>
		{/if}

		{#if !BYPASS_EMBEDDING_AND_RETRIEVAL}
			<!-- Embedding -->
			<SettingsSection title={$i18n.t('Embedding')}>
				<Field
					class="mb-2.5"
					label={$i18n.t('Embedding Model')}
					helper={$i18n.t(
						'Select a model exposed by a configured connection (Connections tab). Embeddings are routed to that connection automatically. Warning: If you change your embedding model, you will need to re-import all documents.'
					)}
				>
					<div class="w-full">
						<Selector
							size="sm"
							bind:value={embeddingModel}
							placeholder={$i18n.t('Select an Embedding Model')}
							searchPlaceholder={$i18n.t('Search an Embedding Model')}
							items={$models.map((m) => ({ value: m.id, label: m.name ?? m.id }))}
						/>
					</div>
				</Field>
			</SettingsSection>

			<!-- Retrieval -->
			<SettingsSection title={$i18n.t('Retrieval')}>
				<Field inline separator label={$i18n.t('Full Context Mode')}>
					<Tooltip
						content={RAG_FULL_CONTEXT
							? $i18n.t(
									'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
								)
							: $i18n.t(
									'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
								)}
					>
						<Switch bind:state={RAG_FULL_CONTEXT} />
					</Tooltip>
				</Field>

				{#if !RAG_FULL_CONTEXT}
					<Field inline separator label={$i18n.t('Hybrid Search')}>
						<Switch bind:state={querySettings.hybrid} onchange={toggleHybridSearch} />
					</Field>

					<Field inline separator label={$i18n.t('Top K')}>
						<input
							class={`${nativeInputClass} w-24`}
							type="number"
							placeholder={$i18n.t('Enter Top K')}
							bind:value={querySettings.k}
							autocomplete="off"
							min="0"
						/>
					</Field>
				{/if}

				<Field class="mb-2.5" label={$i18n.t('RAG Template')}>
					<Tooltip
						content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
						placement="top-start"
						className="w-full"
					>
						<Textarea
							bind:value={querySettings.template}
							placeholder={$i18n.t(
								'Leave empty to use the default prompt, or enter a custom prompt'
							)}
						/>
					</Tooltip>
				</Field>
			</SettingsSection>

			<!-- Reranking & Scoring -->
			<SettingsSection title={$i18n.t('Reranking & Scoring')} bind:open={rerankingOpen}>
				{#if !RAG_FULL_CONTEXT}
					{#if querySettings.hybrid}
						<Field class="mb-2.5" label={$i18n.t('Reranking Model')}>
							<div class="flex w-full gap-2">
								<Input
									size="sm"
									placeholder={$i18n.t('Set reranking model (e.g. {{model}})', {
										model: 'BAAI/bge-reranker-v2-m3'
									})}
									bind:value={rerankingModel}
								/>
								<Button
									variant="ghost"
									size="icon"
									class="size-8 shrink-0"
									type="button"
									onclick={rerankingModelUpdateHandler}
									disabled={updateRerankingModelLoading}
								>
									{#if updateRerankingModelLoading}
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
													to {
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
						</Field>

						<Field inline separator label={$i18n.t('Top K Reranker')}>
							<input
								class={`${nativeInputClass} w-24`}
								type="number"
								placeholder={$i18n.t('Enter Top K Reranker')}
								bind:value={querySettings.k_reranker}
								autocomplete="off"
								min="0"
							/>
						</Field>

						<div class="mb-2.5">
							<div
								class="flex w-full items-center justify-between gap-3 border-b border-dashed border-border pb-2"
							>
								<div class="text-sm font-medium text-foreground">
									{$i18n.t('Minimum Score')}
								</div>
								<input
									class={`${nativeInputClass} w-24`}
									type="number"
									step="0.01"
									placeholder={$i18n.t('Enter Score')}
									bind:value={querySettings.r}
									autocomplete="off"
									min="0.0"
									title={$i18n.t('The score should be a value between 0.0 (0%) and 1.0 (100%).')}
								/>
							</div>
							<div class="mt-1 text-xs text-muted-foreground">
								{$i18n.t(
									'Note: If you set a minimum score, the search will only return documents with a score greater than or equal to the minimum score.'
								)}
							</div>
						</div>
					{/if}
				{/if}
			</SettingsSection>
		{/if}

		<!-- Files & Limits -->
		<SettingsSection title={$i18n.t('Files & Limits')} open={false}>
			<Field inline separator label={$i18n.t('Max Upload Size')}>
				<Tooltip
					content={$i18n.t(
						'The maximum file size in MB. If the file size exceeds this limit, the file will not be uploaded.'
					)}
					placement="top-start"
				>
					<input
						class={`${nativeInputClass} w-24`}
						type="number"
						placeholder={$i18n.t('Leave empty for unlimited')}
						bind:value={fileMaxSize}
						autocomplete="off"
						min="0"
					/>
				</Tooltip>
			</Field>

			<Field inline separator label={$i18n.t('Max Upload Count')}>
				<Tooltip
					content={$i18n.t(
						'The maximum number of files that can be used at once in chat. If the number of files exceeds this limit, the files will not be uploaded.'
					)}
					placement="top-start"
				>
					<input
						class={`${nativeInputClass} w-24`}
						type="number"
						placeholder={$i18n.t('Leave empty for unlimited')}
						bind:value={fileMaxCount}
						autocomplete="off"
						min="0"
					/>
				</Tooltip>
			</Field>
		</SettingsSection>

		<!-- Cloud Integrations -->
		<SettingsSection title={$i18n.t('Cloud Integrations')} open={false}>
			<Field inline separator label={$i18n.t('Google Drive')}>
				<Switch bind:state={enableGoogleDriveIntegration} />
			</Field>
			<Field inline separator label={$i18n.t('OneDrive')}>
				<Switch bind:state={enableOneDriveIntegration} />
			</Field>
		</SettingsSection>

		<!-- Danger Zone -->
		<SettingsSection title={$i18n.t('Danger Zone')} danger open={false}>
			<Field inline separator label={$i18n.t('Reset Upload Directory')}>
				<Button
					variant="outline"
					size="sm"
					class="text-destructive hover:bg-destructive/10"
					type="button"
					onclick={() => (showResetUploadDirConfirm = true)}
				>
					{$i18n.t('Reset')}
				</Button>
			</Field>
			<Field inline separator label={$i18n.t('Reset Vector Storage/Knowledge')}>
				<Button
					variant="outline"
					size="sm"
					class="text-destructive hover:bg-destructive/10"
					type="button"
					onclick={() => (showResetConfirm = true)}
				>
					{$i18n.t('Reset')}
				</Button>
			</Field>
		</SettingsSection>
	</div>

	<div class="flex justify-end pt-3">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
