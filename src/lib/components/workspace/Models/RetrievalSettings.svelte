<script lang="ts">
	import { getContext } from 'svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface RAGSettings {
		k?: number;
		r?: number;
		hybrid?: boolean;
		k_reranker?: number;
		query_rewrite?: boolean;
		hyde?: boolean;
		query_expansion?: boolean;
		query_expansion_max?: number;
		step_back?: boolean;
		rrf_k?: number;
		rule_based_reranking?: boolean;
		llm_reranking?: boolean;
		crag?: boolean;
		doc_grading?: boolean;
		evidence_reconciliation?: boolean;
		multi_hop?: boolean;
		multi_hop_max?: number;
		rag_template?: string;
	}

	interface Props {
		/** Agent-level RAG settings override; null means use global defaults */
		ragSettings: RAGSettings | null;
	}

	let { ragSettings = $bindable(null) }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let expanded = $state(true);

	$effect(() => {
		if (expanded && ragSettings === null) {
			enableCustom();
		}
	});

	const enableCustom = () => {
		ragSettings = {
			k: 4,
			r: 0.0,
			hybrid: false,
			k_reranker: 4,
			query_rewrite: false,
			hyde: false,
			query_expansion: false,
			query_expansion_max: 3,
			step_back: false,
			rrf_k: 60,
			rule_based_reranking: false,
			llm_reranking: false,
			crag: false,
			doc_grading: false,
			evidence_reconciliation: false,
			multi_hop: false,
			multi_hop_max: 3,
			rag_template: ''
		};
	};

	let summary = $derived.by(() => {
		if (ragSettings === null) return $i18n.t('Default settings');
		const parts: string[] = [];
		parts.push(`Top K: ${ragSettings.k ?? 4}`);
		parts.push(`Hybrid: ${ragSettings.hybrid ? 'On' : 'Off'}`);
		let activeCount = 0;
		if (ragSettings.query_rewrite) activeCount++;
		if (ragSettings.hyde) activeCount++;
		if (ragSettings.query_expansion) activeCount++;
		if (ragSettings.step_back) activeCount++;
		if (ragSettings.rule_based_reranking) activeCount++;
		if (ragSettings.llm_reranking) activeCount++;
		if (ragSettings.crag) activeCount++;
		if (ragSettings.doc_grading) activeCount++;
		if (ragSettings.evidence_reconciliation) activeCount++;
		if (ragSettings.multi_hop) activeCount++;
		if (activeCount > 0) {
			parts.push(`${activeCount} ${activeCount === 1 ? 'feature' : 'features'} on`);
		}
		return parts.join(', ');
	});
</script>

<div class="my-2">
	<button
		class="flex w-full items-center justify-between py-2 text-left group"
		type="button"
		onclick={() => {
			if (!expanded && ragSettings === null) {
				enableCustom();
			}
			expanded = !expanded;
		}}
	>
		<span class="text-sm font-semibold">{$i18n.t('Quality Enhance')}</span>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 20 20"
			fill="currentColor"
			class="w-4 h-4 text-gray-400 dark:text-gray-500 transition-transform duration-200 {expanded
				? 'rotate-180'
				: ''}"
		>
			<path
				fill-rule="evenodd"
				d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z"
				clip-rule="evenodd"
			/>
		</svg>
	</button>

	{#if !expanded}
		<div class="text-xs text-gray-400 dark:text-gray-500 -mt-1">
			{summary}
		</div>
	{/if}

	{#if expanded && ragSettings !== null}
		<div class="my-2 flex flex-col gap-3 overflow-hidden">
			<!-- Section: Basic -->
			<div class="text-xs uppercase tracking-wider text-gray-400 dark:text-gray-500 font-semibold">
				{$i18n.t('Basic')}
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="text-xs font-medium self-center">{$i18n.t('Top K')}</div>
				<div class="flex items-center">
					<input
						class="w-20 rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="number"
						min="0"
						bind:value={ragSettings.k}
						autocomplete="off"
					/>
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="text-xs font-medium self-center">{$i18n.t('Hybrid Search')}</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.hybrid} />
				</div>
			</div>

			{#if ragSettings.hybrid === true}
				<div class="flex w-full justify-between items-center">
					<div class="text-xs font-medium self-center">{$i18n.t('Top K Reranker')}</div>
					<div class="flex items-center">
						<input
							class="w-20 rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							type="number"
							min="0"
							bind:value={ragSettings.k_reranker}
							autocomplete="off"
						/>
					</div>
				</div>

				<div class="flex w-full justify-between items-center">
					<div class="text-xs font-medium self-center">{$i18n.t('Minimum Score')}</div>
					<div class="flex items-center">
						<input
							class="w-20 rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							type="number"
							step="0.01"
							min="0.0"
							bind:value={ragSettings.r}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}

			<!-- Section: Smart Query -->
			<div class="border-b-1 border-gray-100 dark:border-gray-700 border-dashed"></div>
			<div class="text-xs uppercase tracking-wider text-gray-400 dark:text-gray-500 font-semibold">
				{$i18n.t('Smart Query')}
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t('Use LLM to rewrite and expand the user query for better retrieval')}
					>
						<span class="text-xs font-medium">{$i18n.t('Query Rewrite')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.query_rewrite} />
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t('Generate hypothetical answers to improve semantic search quality')}
					>
						<span class="text-xs font-medium">{$i18n.t('HyDE')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.hyde} />
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Generate multiple alternative phrasings of the query to improve recall'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('Query Expansion')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.query_expansion} />
				</div>
			</div>

			{#if ragSettings.query_expansion === true}
				<div class="flex w-full justify-between items-center">
					<div class="text-xs font-medium self-center pl-3">{$i18n.t('Max Expanded Queries')}</div>
					<div class="flex items-center">
						<input
							class="w-20 rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							type="number"
							min="1"
							max="10"
							bind:value={ragSettings.query_expansion_max}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Generate a broader, more abstract version of the query to improve conceptual recall'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('Step-Back Prompting')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.step_back} />
				</div>
			</div>

			<!-- Section: Retrieval Quality -->
			<div class="border-b-1 border-gray-100 dark:border-gray-700 border-dashed"></div>
			<div class="text-xs uppercase tracking-wider text-gray-400 dark:text-gray-500 font-semibold">
				{$i18n.t('Retrieval Quality')}
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Reciprocal Rank Fusion constant — controls how rank positions are weighted when merging results'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('RRF Fusion K')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<input
						class="w-20 rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="number"
						min="1"
						bind:value={ragSettings.rrf_k}
						autocomplete="off"
					/>
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Score documents using heuristics: exact match, title hit, TF similarity, position, and coverage'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('Rule-Based Reranking')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.rule_based_reranking} />
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							"Use an LLM to score each document's relevance on a 1-10 scale for precise reranking"
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('LLM Reranking')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.llm_reranking} />
				</div>
			</div>

			<!-- Section: Post-Retrieval -->
			<div class="border-b-1 border-gray-100 dark:border-gray-700 border-dashed"></div>
			<div class="text-xs uppercase tracking-wider text-gray-400 dark:text-gray-500 font-semibold">
				{$i18n.t('Post-Retrieval')}
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Assess retrieval quality with a composite score (similarity, keyword overlap, coverage, diversity) and filter insufficient results'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('CRAG Quality Assessment')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.crag} />
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							"Grade each document's relevance and filter out incorrect or irrelevant sources"
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('Document Grading')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.doc_grading} />
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Detect redundant and conflicting evidence across documents, group by topic, and reconcile contradictions'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('Evidence Reconciliation')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.evidence_reconciliation} />
				</div>
			</div>

			<div class="flex w-full justify-between items-center">
				<div class="self-center">
					<Tooltip
						content={$i18n.t(
							'Decompose complex multi-part questions into sub-queries, retrieve for each, and merge results'
						)}
					>
						<span class="text-xs font-medium">{$i18n.t('Multi-Hop Retrieval')}</span>
					</Tooltip>
				</div>
				<div class="flex items-center">
					<Switch bind:state={ragSettings.multi_hop} />
				</div>
			</div>

			{#if ragSettings.multi_hop === true}
				<div class="flex w-full justify-between items-center">
					<div class="text-xs font-medium self-center pl-3">{$i18n.t('Max Hops')}</div>
					<div class="flex items-center">
						<input
							class="w-20 rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							type="number"
							min="1"
							max="10"
							bind:value={ragSettings.multi_hop_max}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}

			<!-- Section: RAG Template -->
			<div class="border-b-1 border-gray-100 dark:border-gray-700 border-dashed"></div>
			<div class="flex flex-col w-full">
				<div class="mb-1 text-xs font-medium">{$i18n.t('RAG Template')}</div>
				<Textarea
					bind:value={ragSettings.rag_template}
					placeholder={$i18n.t('Leave empty to use the default prompt')}
				/>
			</div>
		</div>
	{/if}
</div>
