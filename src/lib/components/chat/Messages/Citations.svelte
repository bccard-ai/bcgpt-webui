<script lang="ts">
	import { getContext, tick } from 'svelte';
	import CitationsModal from './CitationsModal.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface CitationMetadata {
		source?: string;
		name?: string;
		[key: string]: unknown;
	}

	interface CitationSourceRef {
		id?: string;
		name?: string;
		url?: string;
		[key: string]: unknown;
	}

	interface RawSource {
		document: string[];
		metadata?: Array<CitationMetadata | undefined>;
		distances?: number[];
		source?: CitationSourceRef;
		[key: string]: unknown;
	}

	interface CitationItemSource {
		id?: string;
		name: string;
		url?: string;
		[key: string]: unknown;
	}

	interface CitationItem {
		id: string;
		source: CitationItemSource;
		document: string[];
		metadata: Array<CitationMetadata | undefined>;
		distances?: number[];
	}

	interface Props {
		id?: string;
		sources?: RawSource[];
	}

	let { id = '', sources = [] }: Props = $props();

	let citations = $derived<CitationItem[]>(buildCitationItems(sources));
	let showPercentage = $derived<boolean>(shouldShowPercentage(citations));
	let showRelevance = $derived<boolean>(calculateShowRelevance(citations));
	let citationModalId = $derived(`citation-modal-${id || 'response'}`);
	let citationListId = $derived(`citation-list-${id || 'response'}`);

	let showCitationModal = $state(false);
	let selectedCitation: CitationItem | null = $state(null);
	let isCollapsibleOpen = $state(false);
	let lastCitationTrigger: HTMLButtonElement | null = null;
	let wasCitationModalOpen = false;

	function calculateShowRelevance(items: CitationItem[]): boolean {
		const distances = items.flatMap((citation) => citation.distances ?? []);
		const inRange = distances.filter((distance) => distance >= -1 && distance <= 1).length;
		const outOfRange = distances.filter((distance) => distance < -1 || distance > 1).length;

		if (distances.length === 0) return false;
		return !(
			(inRange === distances.length - 1 && outOfRange === 1) ||
			(outOfRange === distances.length - 1 && inRange === 1)
		);
	}

	function shouldShowPercentage(items: CitationItem[]): boolean {
		const distances = items.flatMap((citation) => citation.distances ?? []);
		return distances.every((distance) => distance >= -1 && distance <= 1);
	}

	function buildCitationItems(rawSources: RawSource[]): CitationItem[] {
		return rawSources.reduce<CitationItem[]>((acc, source) => {
			if (!source || Object.keys(source).length === 0 || !Array.isArray(source.document))
				return acc;

			source.document.forEach((document, index) => {
				const metadata = source.metadata?.[index];
				const distance = source.distances?.[index];
				const citationId = metadata?.source ?? source.source?.id ?? 'N/A';
				let citationSource = source.source;

				if (metadata?.name) citationSource = { ...citationSource, name: metadata.name };
				if (citationId.startsWith('http://') || citationId.startsWith('https://')) {
					citationSource = { ...citationSource, name: citationId, url: citationId };
				}

				const existing = acc.find((item) => item.id === citationId);
				if (existing) {
					existing.document.push(document);
					existing.metadata.push(metadata);
					if (existing.distances && distance !== undefined) {
						existing.distances.push(distance);
					} else if (existing.distances || distance !== undefined) {
						// Mixed availability cannot be represented positionally without
						// inventing a relevance value, so hide relevance for this source.
						existing.distances = undefined;
					}
					return;
				}

				acc.push({
					id: citationId,
					source: {
						...(citationSource ?? {}),
						name: citationSource?.name ?? citationId
					},
					document: [document],
					metadata: [metadata],
					distances: distance !== undefined ? [distance] : undefined
				});
			});
			return acc;
		}, []);
	}

	function citationName(citation: CitationItem): string {
		try {
			return decodeURIComponent(citation.source.name);
		} catch {
			return citation.source.name;
		}
	}

	function openCitationModal(citation: CitationItem, trigger: HTMLButtonElement): void {
		lastCitationTrigger = trigger;
		selectedCitation = citation;
		showCitationModal = true;
	}

	$effect(() => {
		if (wasCitationModalOpen && !showCitationModal && lastCitationTrigger) {
			const trigger = lastCitationTrigger;
			void tick().then(() => {
				if (trigger.isConnected) trigger.focus();
			});
		}
		wasCitationModalOpen = showCitationModal;
	});
</script>

<CitationsModal
	bind:show={showCitationModal}
	citation={selectedCitation ?? {}}
	{showPercentage}
	{showRelevance}
	modalId={citationModalId}
/>

{#snippet CitationButton(citation: CitationItem, idx: number, surface: string)}
	<button
		type="button"
		id="source-{id}-{surface}-{idx + 1}"
		class="no-toggle flex max-w-96 rounded-xl bg-gray-50 p-1 text-xs font-medium text-black/60 outline-hidden transition hover:bg-gray-100 hover:text-black focus-visible:outline-2 focus-visible:outline-offset-2 dark:bg-gray-900 dark:text-white/60 dark:hover:bg-gray-850 dark:hover:text-white"
		aria-label={citationName(citation)}
		aria-haspopup="dialog"
		aria-controls={citationModalId}
		onclick={(event) => openCitationModal(citation, event.currentTarget)}
	>
		{#if citations.every((item) => item.distances !== undefined)}
			<span class="size-4 rounded-full bg-gray-100 dark:bg-gray-800">{idx + 1}</span>
		{/if}
		<span class="mx-1 flex-1 truncate">{citationName(citation)}</span>
	</button>
{/snippet}

{#if citations.length > 0}
	<div class="flex w-full flex-wrap items-center gap-1 py-0.5 -mx-0.5">
		{#if citations.length <= 3}
			<div class="flex flex-wrap gap-1">
				{#each citations as citation, idx (citation.id ?? idx)}
					{@render CitationButton(citation, idx, 'summary')}
				{/each}
			</div>
		{:else}
			<div class="w-full max-w-full">
				<div class="flex w-full items-center gap-2 overflow-auto text-gray-500 dark:text-gray-400">
					<span class="hidden shrink-0 whitespace-nowrap sm:inline"
						>{$i18n.t('References from')}</span
					>
					<div class="flex min-w-0 flex-1 items-center gap-1 overflow-auto scrollbar-none">
						{#each citations.slice(0, 2) as citation, idx (citation.id ?? idx)}
							{@render CitationButton(citation, idx, 'preview')}
						{/each}
					</div>
					<button
						type="button"
						class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-1 hover:text-gray-600 focus-visible:outline-2 focus-visible:outline-offset-2 dark:hover:text-gray-300"
						aria-expanded={isCollapsibleOpen}
						aria-controls={citationListId}
						onclick={() => (isCollapsibleOpen = !isCollapsibleOpen)}
					>
						<span class="hidden sm:inline">{$i18n.t('and')}</span>
						{citations.length - 2}
						<span>{$i18n.t('more')}</span>
						{#if isCollapsibleOpen}
							<ChevronUp strokeWidth="3.5" className="size-3.5" />
						{:else}
							<ChevronDown strokeWidth="3.5" className="size-3.5" />
						{/if}
					</button>
				</div>

				{#if isCollapsibleOpen}
					<div
						id={citationListId}
						role="region"
						aria-label={$i18n.t('References')}
						class="mt-1 flex flex-wrap gap-1"
					>
						{#each citations as citation, idx (citation.id ?? idx)}
							{@render CitationButton(citation, idx, 'expanded')}
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}
