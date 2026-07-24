<script lang="ts">
	/**
	 * Admin RAG Settings
	 *
	 * Configures Retrieval-Augmented Generation settings: vector DB connection
	 * (Qdrant), text chunking strategy, document cleansing, summarization,
	 * and embedding model selection.
	 */
	import { preventDefault } from 'svelte/legacy';

	import { toast } from 'svelte-sonner';

	import { onMount, getContext } from 'svelte';

	import { getRAGConfig, updateRAGConfig } from '$lib/apis/retrieval';

	import { models } from '$lib/stores';

	import Switch from '$lib/components/common/Switch.svelte';
	import Selector from '$lib/components/common/Selector.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import SettingsSection from './SettingsSection.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Callback invoked after config is saved */
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	// --- Vector DB ---
	let qdrantUrl = $state('');
	let qdrantApiKey = $state('');

	// --- Chunking ---
	let textSplitter = $state('');
	let chunkSize = $state(1000);
	let chunkOverlap = $state(100);

	// --- Cleansing ---
	let cleansingEnabled = $state(false);
	let cleansingModel = $state('');

	// --- Summary ---
	let summaryEnabled = $state(false);
	let summaryModel = $state('');

	// --- Embedding ---
	let embeddingModel = $state('');

	/** LLM model items for searchable dropdowns */
	let modelItems = $derived($models.map((m) => ({ value: m.id, label: m.name })));

	/** Document Processing starts collapsed unless cleansing/summary already enabled (set on load). */
	let docProcessingOpen = $state(false);

	/**
	 * Persist RAG config (chunking, vector DB, embedding, cleansing, summary) to the backend.
	 */
	const submitHandler = async () => {
		try {
			// Update RAG config (chunking + vector DB + embedding + cleansing + summary)
			await updateRAGConfig('', {
				chunk: {
					text_splitter: textSplitter,
					chunk_size: chunkSize,
					chunk_overlap: chunkOverlap
				},
				qdrant_url: qdrantUrl,
				qdrant_api_key: qdrantApiKey,
				embedding_model: embeddingModel,
				cleansing_enabled: cleansingEnabled,
				cleansing_model: cleansingModel,
				summary_enabled: summaryEnabled,
				summary_model: summaryModel
			});

			onSave?.();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	onMount(async () => {
		// Fetch RAG config
		try {
			const ragConfig = await getRAGConfig('');
			if (ragConfig) {
				textSplitter = ragConfig.chunk?.text_splitter ?? '';
				chunkSize = ragConfig.chunk?.chunk_size ?? 1000;
				chunkOverlap = ragConfig.chunk?.chunk_overlap ?? 100;

				qdrantUrl = ragConfig.qdrant_url ?? '';
				qdrantApiKey = ragConfig.qdrant_api_key ?? '';

				embeddingModel = ragConfig.embedding_model ?? '';

				cleansingEnabled = ragConfig.cleansing_enabled ?? false;
				cleansingModel = ragConfig.cleansing_model ?? '';

				summaryEnabled = ragConfig.summary_enabled ?? false;
				summaryModel = ragConfig.summary_model ?? '';

				docProcessingOpen = cleansingEnabled || summaryEnabled;
			}
		} catch (e) {
			console.warn('Failed to load RAG config:', e);
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(() => {
		submitHandler();
	})}
>
	<div class=" space-y-2.5 overflow-y-scroll scrollbar-hidden h-full pr-1.5">
		<div class="">
			<div class="mb-2.5">
				<InfoCallout
					>{$i18n.t(
						'Configure retrieval settings such as the vector DB connection, chunking, embedding model, and reranking used to fetch relevant context.'
					)}</InfoCallout
				>
			</div>

			<!-- Connection (Vector DB) -->
			<SettingsSection title={$i18n.t('Connection (Vector DB)')}>
				<Field class="mb-2.5" label={$i18n.t('Qdrant URL')}>
					<Input
						size="sm"
						type="text"
						placeholder={$i18n.t('Enter Qdrant URL (e.g. http://localhost:6333)')}
						bind:value={qdrantUrl}
					/>
				</Field>

				<Field class="mb-2.5" label={`${$i18n.t('Qdrant API Key')} (${$i18n.t('Optional')})`}>
					<SensitiveInput
						placeholder={$i18n.t('Enter Qdrant API Key')}
						bind:value={qdrantApiKey}
						required={false}
					/>
				</Field>
			</SettingsSection>

			<!-- Embedding -->
			<SettingsSection title={$i18n.t('Embedding')}>
				<Field
					class="mb-2.5"
					label={$i18n.t('Embedding Model')}
					helper={$i18n.t('When specified, a knowledge collection will be auto-created.')}
				>
					<Selector
						size="sm"
						bind:value={embeddingModel}
						placeholder={$i18n.t('Select an Embedding Model')}
						searchPlaceholder={$i18n.t('Search an Embedding Model')}
						items={$models.map((m) => ({ value: m.id, label: m.name ?? m.id }))}
					/>
				</Field>
			</SettingsSection>

			<!-- Chunking (advanced) -->
			<SettingsSection title={$i18n.t('Chunking')} open={false}>
				<Field inline separator class="mb-2.5" label={$i18n.t('Text Splitter')}>
					<Select
						class="w-fit"
						bind:value={textSplitter}
						items={[
							{ value: '', label: `${$i18n.t('Default')} (${$i18n.t('Character')})` },
							{ value: 'token', label: `${$i18n.t('Token')} (${$i18n.t('Tiktoken')})` }
						]}
					/>
				</Field>

				<div class="mb-2.5 border-b border-dashed border-border pb-2">
					<div class="flex gap-1.5 w-full">
						<Field class="w-full" label={$i18n.t('Chunk Size')}>
							<input
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								type="number"
								placeholder={$i18n.t('Enter Chunk Size')}
								bind:value={chunkSize}
								autocomplete="off"
								min="0"
							/>
						</Field>
						<Field class="w-full" label={$i18n.t('Chunk Overlap')}>
							<input
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								type="number"
								placeholder={$i18n.t('Enter Chunk Overlap')}
								bind:value={chunkOverlap}
								autocomplete="off"
								min="0"
							/>
						</Field>
					</div>
				</div>
			</SettingsSection>

			<!-- Document Processing (advanced; auto-opens when cleansing/summary enabled) -->
			<SettingsSection title={$i18n.t('Document Processing')} bind:open={docProcessingOpen}>
				<Field inline separator class="mb-2.5" label={$i18n.t('Enable Cleansing')}>
					<Switch bind:state={cleansingEnabled} />
				</Field>

				{#if cleansingEnabled}
					<Field class="mb-2.5" label={$i18n.t('Cleansing Model')}>
						<Selector
							size="sm"
							bind:value={cleansingModel}
							placeholder={$i18n.t('Select a Cleansing Model')}
							searchPlaceholder={$i18n.t('Search a Cleansing Model')}
							items={modelItems}
						/>
					</Field>
				{/if}

				<Field inline separator class="mb-2.5" label={$i18n.t('Enable Summary')}>
					<Switch bind:state={summaryEnabled} />
				</Field>

				{#if summaryEnabled}
					<Field class="mb-2.5" label={$i18n.t('Summary Model')}>
						<Selector
							size="sm"
							bind:value={summaryModel}
							placeholder={$i18n.t('Select a Summary Model')}
							searchPlaceholder={$i18n.t('Search a Summary Model')}
							items={modelItems}
						/>
					</Field>
				{/if}
			</SettingsSection>
		</div>
	</div>
	<div class="flex justify-end pt-3 text-sm font-medium">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
