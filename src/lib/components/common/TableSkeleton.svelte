<script lang="ts">
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * TableSkeleton — animated placeholder for loading table data.
	 *
	 * Renders a header row + body rows with pulsing cells.
	 *
	 * @example
	 * ```svelte
	 * <TableSkeleton rows={5} columns={4} />
	 * ```
	 *
	 * @props rows - Number of body rows
	 * @props columns - Number of columns
	 */
	interface Props {
		/** Number of body rows. Defaults to `5`. */
		rows?: number;
		/** Number of columns. Defaults to `4`. */
		columns?: number;
	}

	let { rows = 5, columns = 4 }: Props = $props();
</script>

<div class="w-full" aria-busy="true" aria-label={$i18n.t('Loading data')}>
	<div class="flex gap-3 px-3 py-1.5 mb-1">
		{#each Array(columns) as _, colIdx (colIdx)}
			<div class="h-3 bg-gray-200 dark:bg-gray-800 rounded animate-pulse flex-1"></div>
		{/each}
	</div>

	{#each Array(rows) as _, rowIdx (rowIdx)}
		<div class="flex gap-3 px-3 py-2 border-t border-gray-50 dark:border-gray-850">
			{#each Array(columns) as _, colIdx (colIdx)}
				<div class="h-4 bg-gray-100 dark:bg-gray-850 rounded animate-pulse flex-1"></div>
			{/each}
		</div>
	{/each}
</div>
