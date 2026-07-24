<!--
  Stacked vertical bar chart (CSS fl- based, zero deps).
  Bar height scales with daily total; segments stack by severity.
-->
<script lang="ts">
	import { formatDate, formatDateTime, formatFull } from './format';

	interface Bucket {
		x: number; // ms timestamp
		segs: Record<string, number>;
	}

	interface Props {
		data: Bucket[];
		severities?: string[];
		colors?: Record<string, string>;
		height?: number;
		emptyLabel?: string;
	}

	let {
		data,
		severities = ['critical', 'high', 'medium', 'low'],
		colors = {},
		height = 180,
		emptyLabel = 'No data'
	}: Props = $props();

	const defaults: Record<string, string> = {
		critical: 'var(--destructive)',
		high: 'var(--warning)',
		medium: 'var(--chart-1)',
		low: 'var(--muted-foreground)'
	};
	const colorFor = (s: string) => colors[s] ?? defaults[s] ?? 'var(--chart-1)';

	const sum = (segs: Record<string, number>) =>
		Object.values(segs).reduce((a, b) => a + (b || 0), 0);
	const maxTotal = $derived(Math.max(1, ...data.map((d) => sum(d.segs))));
</script>

{#if data.length === 0}
	<div
		class="flex items-center justify-center text-xs text-muted-foreground"
		style="height:{height}px"
	>
		{emptyLabel}
	</div>
{:else}
	<div class="flex items-end gap-[2px]" style="height:{height}px">
		{#each data as b (b.x)}
			{@const total = sum(b.segs)}
			{@const h = (total / maxTotal) * 100}
			<div class="group relative flex min-w-0 flex-1 flex-col justify-end">
				<div
					class="flex w-full flex-col-reverse overflow-hidden rounded-sm transition-[height] duration-300"
					style="height:{h}%;min-height:{total > 0 ? 2 : 0}px"
				>
					{#each severities as s (s)}
						{@const v = b.segs[s] ?? 0}
						{#if v > 0}
							<div style="flex:{v} 0 0;background:{colorFor(s)}"></div>
						{/if}
					{/each}
				</div>

				<!-- hover breakdown -->
				<div
					class="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-[11px] text-popover-foreground shadow-md group-hover:block"
				>
					<div class="font-medium">{formatDateTime(b.x)}</div>
					<div class="mt-0.5 tabular-nums text-muted-foreground">{formatFull(total)} events</div>
				</div>
			</div>
		{/each}
	</div>

	<!-- x-axis labels: first / mid / last -->
	<div class="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
		<span>{data.length > 0 ? formatDate(data[0].x) : ''}</span>
		<span>{data.length > 2 ? formatDate(data[Math.floor((data.length - 1) / 2)].x) : ''}</span>
		<span>{data.length > 0 ? formatDate(data[data.length - 1].x) : ''}</span>
	</div>
{/if}
