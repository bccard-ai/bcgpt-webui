<!--
  Horizontal bar chart (CSS-based, zero deps).
  Bars scale to the max value; labels truncate with a tooltip title.
-->
<script lang="ts">
	import { formatCompact } from './format';

	interface Item {
		label: string;
		value: number;
	}

	interface Props {
		data: Item[];
		color?: string;
		valueFormatter?: (n: number) => string;
		emptyLabel?: string;
	}

	let {
		data,
		color = 'var(--chart-1)',
		valueFormatter = formatCompact,
		emptyLabel = 'No data'
	}: Props = $props();

	const max = $derived(Math.max(1, ...data.map((d) => d.value)));
</script>

<div class="flex flex-col gap-2.5">
	{#each data as d (d.label)}
		<div class="flex items-center gap-3">
			<div class="w-32 shrink-0 truncate text-xs text-muted-foreground" title={d.label}>
				{d.label}
			</div>
			<div class="relative h-5 flex-1 overflow-hidden rounded bg-muted/60">
				<div
					class="absolute inset-y-0 left-0 rounded transition-[width] duration-500"
					style="width:{Math.max(2, (d.value / max) * 100)}%;background:{color}"
				></div>
			</div>
			<div class="w-16 shrink-0 text-right text-xs font-medium tabular-nums">
				{valueFormatter(d.value)}
			</div>
		</div>
	{/each}

	{#if data.length === 0}
		<div class="py-6 text-center text-xs text-muted-foreground">{emptyLabel}</div>
	{/if}
</div>
