<script lang="ts">
	import { preventDefault } from 'svelte/legacy';

	import { toast } from 'svelte-sonner';

	import { onMount, getContext } from 'svelte';

	import { getAdvancedRAGConfig, updateAdvancedRAGConfig } from '$lib/apis/retrieval/advanced';

	import { models } from '$lib/stores';

	import Switch from '$lib/components/common/Switch.svelte';
	import Selector from '$lib/components/common/Selector.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let crEnabled = $state(false);
	let crModel = $state('');
	let crMaxContextTokens = $state(256);
	let crBatchSize = $state(32);

	let ceEnabled = $state(false);
	let ceModel = $state('BAAI/bge-reranker-v2-m3');
	let ceMaxLength = $state(512);
	let ceTopK = $state(10);

	let graphEnabled = $state(false);
	let graphEntityExtractionModel = $state('');
	let graphMaxEntities = $state(100);
	let graphMaxRelations = $state(100);
	let graphCommunityDetectionEnabled = $state(false);
	let graphMaxHops = $state(2);

	let evalEnabled = $state(false);
	let evalModel = $state('');
	let evalMetrics = $state('faithfulness,relevancy,context_relevancy');
	let evalLogResults = $state(false);

	let modelItems = $derived($models.map((m) => ({ value: m.id, label: m.name })));

	/** Collapsed advanced groups auto-open when their feature is already enabled on load. */
	let crOpen = $state(false);
	let graphOpen = $state(false);
	let evalOpen = $state(false);

	const submitHandler = async () => {
		try {
			await updateAdvancedRAGConfig('', {
				contextual_retrieval: {
					enabled: crEnabled,
					model: crModel,
					max_context_tokens: crMaxContextTokens,
					batch_size: crBatchSize
				},
				cross_encoder: {
					enabled: ceEnabled,
					model: ceModel,
					max_length: ceMaxLength,
					top_k: ceTopK
				},
				graph: {
					enabled: graphEnabled,
					entity_extraction_model: graphEntityExtractionModel,
					max_entities: graphMaxEntities,
					max_relations: graphMaxRelations,
					community_detection_enabled: graphCommunityDetectionEnabled,
					max_hops: graphMaxHops
				},
				evaluation: {
					enabled: evalEnabled,
					model: evalModel,
					metrics: evalMetrics,
					log_results: evalLogResults
				}
			});

			onSave?.();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	onMount(async () => {
		try {
			const config = await getAdvancedRAGConfig('');
			if (config) {
				crEnabled = config.contextual_retrieval?.enabled ?? false;
				crModel = config.contextual_retrieval?.model ?? '';
				crMaxContextTokens = config.contextual_retrieval?.max_context_tokens ?? 256;
				crBatchSize = config.contextual_retrieval?.batch_size ?? 32;

				ceEnabled = config.cross_encoder?.enabled ?? false;
				ceModel = config.cross_encoder?.model ?? 'BAAI/bge-reranker-v2-m3';
				ceMaxLength = config.cross_encoder?.max_length ?? 512;
				ceTopK = config.cross_encoder?.top_k ?? 10;

				graphEnabled = config.graph?.enabled ?? false;
				graphEntityExtractionModel = config.graph?.entity_extraction_model ?? '';
				graphMaxEntities = config.graph?.max_entities ?? 100;
				graphMaxRelations = config.graph?.max_relations ?? 100;
				graphCommunityDetectionEnabled = config.graph?.community_detection_enabled ?? false;
				graphMaxHops = config.graph?.max_hops ?? 2;

				evalEnabled = config.evaluation?.enabled ?? false;
				evalModel = config.evaluation?.model ?? '';
				evalMetrics = config.evaluation?.metrics ?? 'faithfulness,relevancy,context_relevancy';
				evalLogResults = config.evaluation?.log_results ?? false;

				crOpen = crEnabled;
				graphOpen = graphEnabled;
				evalOpen = evalEnabled;
			}
		} catch (e) {
			console.warn('Failed to load Advanced RAG config:', e);
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
						'Configure advanced RAG features including contextual retrieval, cross-encoder reranking, GraphRAG, and RAG evaluation.'
					)}</InfoCallout
				>
			</div>

			<SettingsSection title={$i18n.t('Contextual Retrieval')} bind:open={crOpen}>
				<Field inline separator label={$i18n.t('Enable Contextual Retrieval')}>
					<Switch bind:state={crEnabled} />
				</Field>

				{#if crEnabled}
					<Field class="mb-2.5" label={$i18n.t('Model')}>
						<Selector
							size="sm"
							bind:value={crModel}
							placeholder={$i18n.t('Select a Model')}
							searchPlaceholder={$i18n.t('Search a Model')}
							items={modelItems}
						/>
					</Field>

					<div class="mb-2.5 border-b border-dashed border-border pb-2">
						<div class="flex gap-1.5 w-full">
							<Field class="w-full" label={$i18n.t('Max Context Tokens')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="number"
									placeholder={$i18n.t('Enter Max Context Tokens')}
									bind:value={crMaxContextTokens}
									autocomplete="off"
									min="1"
								/>
							</Field>
							<Field class="w-full" label={$i18n.t('Batch Size')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="number"
									placeholder={$i18n.t('Enter Batch Size')}
									bind:value={crBatchSize}
									autocomplete="off"
									min="1"
								/>
							</Field>
						</div>
					</div>
				{/if}
			</SettingsSection>

			<SettingsSection title={$i18n.t('Cross-Encoder Reranking')}>
				<Field inline separator label={$i18n.t('Enable Cross-Encoder Reranking')}>
					<Switch bind:state={ceEnabled} />
				</Field>

				{#if ceEnabled}
					<Field class="mb-2.5" label={$i18n.t('Model')}>
						<Selector
							size="sm"
							bind:value={ceModel}
							placeholder={$i18n.t('Select a Model')}
							searchPlaceholder={$i18n.t('Search a Model')}
							items={modelItems}
						/>
					</Field>

					<div class="mb-2.5 border-b border-dashed border-border pb-2">
						<div class="flex gap-1.5 w-full">
							<Field class="w-full" label={$i18n.t('Max Length')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="number"
									placeholder={$i18n.t('Enter Max Length')}
									bind:value={ceMaxLength}
									autocomplete="off"
									min="1"
								/>
							</Field>
							<Field class="w-full" label={$i18n.t('Top K')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="number"
									placeholder={$i18n.t('Enter Top K')}
									bind:value={ceTopK}
									autocomplete="off"
									min="1"
								/>
							</Field>
						</div>
					</div>
				{/if}
			</SettingsSection>

			<SettingsSection title={$i18n.t('GraphRAG')} bind:open={graphOpen}>
				<Field inline separator label={$i18n.t('Enable GraphRAG')}>
					<Switch bind:state={graphEnabled} />
				</Field>

				{#if graphEnabled}
					<Field class="mb-2.5" label={$i18n.t('Entity Extraction Model')}>
						<Selector
							size="sm"
							bind:value={graphEntityExtractionModel}
							placeholder={$i18n.t('Select an Entity Extraction Model')}
							searchPlaceholder={$i18n.t('Search an Entity Extraction Model')}
							items={modelItems}
						/>
					</Field>

					<div class="mb-2.5 border-b border-dashed border-border pb-2">
						<div class="flex gap-1.5 w-full">
							<Field class="w-full" label={$i18n.t('Max Entities')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="number"
									placeholder={$i18n.t('Enter Max Entities')}
									bind:value={graphMaxEntities}
									autocomplete="off"
									min="1"
								/>
							</Field>
							<Field class="w-full" label={$i18n.t('Max Relations')}>
								<input
									class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									type="number"
									placeholder={$i18n.t('Enter Max Relations')}
									bind:value={graphMaxRelations}
									autocomplete="off"
									min="1"
								/>
							</Field>
						</div>
					</div>

					<Field inline separator label={$i18n.t('Community Detection')}>
						<Switch bind:state={graphCommunityDetectionEnabled} />
					</Field>

					<Field class="mb-2.5" label={$i18n.t('Max Hops')}>
						<input
							class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							type="number"
							placeholder={$i18n.t('Enter Max Hops')}
							bind:value={graphMaxHops}
							autocomplete="off"
							min="1"
						/>
					</Field>
				{/if}
			</SettingsSection>

			<SettingsSection title={$i18n.t('RAG Evaluation')} bind:open={evalOpen}>
				<Field inline separator label={$i18n.t('Enable RAG Evaluation')}>
					<Switch bind:state={evalEnabled} />
				</Field>

				{#if evalEnabled}
					<Field class="mb-2.5" label={$i18n.t('Evaluation Model')}>
						<Selector
							size="sm"
							bind:value={evalModel}
							placeholder={$i18n.t('Select an Evaluation Model')}
							searchPlaceholder={$i18n.t('Search an Evaluation Model')}
							items={modelItems}
						/>
					</Field>

					<Field
						class="mb-2.5"
						label={$i18n.t('Metrics')}
						helper={$i18n.t('Comma-separated list of evaluation metrics.')}
					>
						<Input
							size="sm"
							placeholder={$i18n.t('faithfulness,relevancy,context_relevancy')}
							bind:value={evalMetrics}
						/>
					</Field>

					<Field inline separator label={$i18n.t('Log Results')}>
						<Switch bind:state={evalLogResults} />
					</Field>
				{/if}
			</SettingsSection>
		</div>
	</div>
	<div class="flex justify-end pt-3 text-sm font-medium">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
