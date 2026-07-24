<script lang="ts">
	import { getContext } from 'svelte';
	import Selector from './Knowledge/Selector.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Selected knowledge items bound to the agent (two-way bindable) */
		selectedKnowledge?: unknown[];
	}

	let { selectedKnowledge = $bindable([]) }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	function getTypeMeta(item: Record<string, unknown>): {
		label: string;
		icon: 'book' | 'database' | 'layers';
		classes: string;
	} {
		if (item?.legacy) {
			return {
				label: `Legacy${item.type ? ` ${item.type}` : ''}`,
				icon: 'layers',
				classes:
					'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'
			};
		}
		if (item?.source === 'knowledge') {
			return {
				label: 'Knowledge',
				icon: 'book',
				classes:
					'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-700/50 text-emerald-700 dark:text-emerald-300'
			};
		}
		if (item?.source === 'collection') {
			return {
				label: 'Vector DB',
				icon: 'database',
				classes:
					'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-700/50 text-blue-700 dark:text-blue-300'
			};
		}
		return {
			label: 'Collection',
			icon: 'layers',
			classes:
				'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'
		};
	}
</script>

<div>
	<div class="flex w-full justify-between mb-1">
		<div class=" self-center text-sm font-semibold">{$i18n.t('Knowledge')}</div>
	</div>

	<div class=" text-xs dark:text-gray-500">
		{$i18n.t('To attach knowledge base here, add them to the "Knowledge" workspace first.')}
		{$i18n.t('You can also attach vector DB collections to use them for RAG.')}
	</div>

	<div class="flex flex-col">
		{#if selectedKnowledge?.length > 0}
			<div class="flex flex-wrap items-center gap-2 mt-2">
				{#each selectedKnowledge as item, idx (item.id ?? idx)}
					{@const meta = getTypeMeta(item)}
					<Tooltip content={meta.label} placement="top">
						<div
							class="group relative flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg border text-xs font-medium transition {meta.classes}"
						>
							{#if meta.icon === 'book'}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="size-3.5 shrink-0 opacity-70"
								>
									<path
										d="M10.75 16.82A7.462 7.462 0 0112 15.4V2.18a7.461 7.461 0 00-1.25-.16h-.5c-.284 0-.565.027-.84.08V15.5c.276.053.556.08.84.08h.5c.004 0 .004 0 0 0zM7.5 14.97V3.03a7.477 7.477 0 00-2-1.03v13.6c.17.062.338.13.504.207A8.48 8.48 0 017.5 14.97zM14 3.03v11.94a8.48 8.48 0 001.496.837c.166-.077.334-.145.504-.207V2c-.702.207-1.377.528-2 1.03z"
									/>
								</svg>
							{:else if meta.icon === 'database'}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="size-3.5 shrink-0 opacity-70"
								>
									<path
										fill-rule="evenodd"
										d="M5.625 1.5H9a.75.75 0 01.75.75v2a.75.75 0 01-.75.75H5.625a1.875 1.875 0 010-3.75zm8.25 0h-2.876a3.375 3.375 0 010 3.75h2.876a.75.75 0 00.75-.75v-2.25a.75.75 0 00-.75-.75zm-8.25 4.5H9A.75.75 0 019.75 7v2a.75.75 0 01-.75.75H5.625a1.875 1.875 0 010-3.75zm8.25 0h-2.876a3.375 3.375 0 010 3.75h2.876a.75.75 0 00.75-.75V6.75a.75.75 0 00-.75-.75zm-8.25 4.5H9a.75.75 0 01.75.75v2A.75.75 0 019 13.5H5.625a1.875 1.875 0 010-3.75z"
										clip-rule="evenodd"
									/>
								</svg>
							{:else}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="size-3.5 shrink-0 opacity-70"
								>
									<path
										d="M5.127 3.502A1.876 1.876 0 016.875 2h6.25a1.876 1.876 0 011.748 1.502c.846.17 1.586.625 2.102 1.263A3.74 3.74 0 0118.75 7.5v5a3.75 3.75 0 01-3.75 3.75H5A3.75 3.75 0 011.25 12.5v-5a3.74 3.74 0 01.825-2.355 4.37 4.37 0 012.052-1.643zM6.875 3.5a.375.375 0 00-.375.375V5.5h7V3.875a.375.375 0 00-.375-.375h-6.25z"
									/>
								</svg>
							{/if}

							<span class="line-clamp-1 max-w-[160px]">{item.name}</span>

							<button
								class="p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 transition opacity-0 group-hover:opacity-100 shrink-0"
								type="button"
								aria-label={$i18n.t('Remove')}
								onclick={() => {
									selectedKnowledge = selectedKnowledge.filter((_, i) => i !== idx);
								}}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="size-3"
								>
									<path
										d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
									/>
								</svg>
							</button>
						</div>
					</Tooltip>
				{/each}
			</div>
		{/if}

		<div class="flex flex-wrap text-sm font-medium gap-1.5 mt-2">
			<Selector
				onSelect={(item: unknown) => {
					const knowledgeItem = item as Record<string, unknown>;
					if (!selectedKnowledge.find((k) => k.id === knowledgeItem.id)) {
						selectedKnowledge = [
							...selectedKnowledge,
							{
								...knowledgeItem
							}
						];
					}
				}}
			>
				<button
					class=" px-3.5 py-1.5 font-medium hover:bg-black/5 dark:hover:bg-white/5 outline outline-1 outline-gray-100 dark:outline-gray-850 rounded-3xl"
					type="button">{$i18n.t('Select Knowledge')}</button
				>
			</Selector>
		</div>
	</div>
</div>
