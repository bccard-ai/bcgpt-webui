<script lang="ts">
	/**
	 * Sortable Model List
	 *
	 * Renders a drag-and-drop reorderable list of model IDs using SortableJS.
	 * Emits updated order via the two-way bindable `modelIds` prop.
	 */

	import Sortable from 'sortablejs';

	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { models } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EllipsisVertical from '$lib/components/icons/EllipsisVertical.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Ordered list of model IDs (two-way bindable) */
		modelIds?: string[];
	}

	let { modelIds = $bindable([]) }: Props = $props();

	/** SortableJS instance reference */
	let sortable: Sortable | null = null;
	/** DOM element for the sortable container */
	let modelListElement = $state(null);

	/** Read the current DOM order and update modelIds */
	const positionChangeHandler = () => {
		const modelList = Array.from(modelListElement.children).map((child) =>
			child.id.replace('model-item-', '')
		);
		modelIds = modelList;
	};

	/** Initialize or reinitialize the SortableJS drag handler */
	const initSortable = () => {
		if (sortable) {
			sortable.destroy();
		}

		if (modelListElement) {
			sortable = Sortable.create(modelListElement, {
				animation: 150,
				handle: '.item-handle',
				onUpdate: async (_event: unknown) => {
					positionChangeHandler();
				}
			});
		}
	};

	/** Reinitialize sortable when modelIds changes */
	$effect(() => {
		if (modelIds) {
			initSortable();
		}
	});
</script>

{#if modelIds.length > 0}
	<div class="flex flex-col -translate-x-1" bind:this={modelListElement}>
		{#each modelIds as modelId (modelId)}
			<div class=" flex gap-2 w-full justify-between items-center" id="model-item-{modelId}">
				<Tooltip content={modelId} placement="top-start">
					<div class="flex items-center gap-1">
						<EllipsisVertical className="size-4 cursor-move item-handle" />

						<div class=" text-sm flex-1 py-1 rounded-lg">
							{#if $models.find((model) => model.id === modelId)}
								{$models.find((model) => model.id === modelId).name}
							{:else}
								{modelId}
							{/if}
						</div>
					</div>
				</Tooltip>
			</div>
		{/each}
	</div>
{:else}
	<div class="text-gray-500 text-xs text-center py-2">
		{$i18n.t('No models found')}
	</div>
{/if}
