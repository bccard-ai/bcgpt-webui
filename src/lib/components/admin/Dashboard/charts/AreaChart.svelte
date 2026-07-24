<!--
  Lightweight responsive area chart (hand-rolled, zero deps).
  Resizes via ResizeObserver; hover crosshair shows nearest point.
-->
<script lang="ts">
	import { formatCompact, formatFull, formatDate } from './format';

	interface Point {
		x: number; // ms timestamp or ordinal
		y: number;
	}

	interface Props {
		data: Point[];
		color?: string;
		height?: number;
		yFormatter?: (n: number) => string;
		xFormatter?: (n: number, i: number) => string;
		emptyLabel?: string;
	}

	let {
		data,
		color = 'var(--chart-1)',
		height = 220,
		yFormatter = formatCompact,
		xFormatter = (ms: number) => formatDate(ms),
		emptyLabel = 'No data'
	}: Props = $props();

	let wrapEl = $state<HTMLDivElement | null>(null);
	let width = $state(640);
	let hoverI = $state<number | null>(null);

	const pad = { l: 44, r: 14, t: 12, b: 26 };

	$effect(() => {
		if (!wrapEl) return;
		const ro = new ResizeObserver((entries) => {
			for (const e of entries) width = Math.max(240, Math.floor(e.contentRect.width));
		});
		ro.observe(wrapEl);
		return () => ro.disconnect();
	});

	const plotW = $derived(Math.max(10, width - pad.l - pad.r));
	const plotH = $derived(Math.max(10, height - pad.t - pad.b));
	const maxY = $derived(Math.max(1, ...data.map((d) => d.y)));
	const n = $derived(data.length);

	const xAt = (i: number) => pad.l + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
	const yAt = (v: number) => pad.t + plotH - (v / maxY) * plotH;

	const linePath = $derived(
		data.length === 0
			? ''
			: data
					.map((d, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i).toFixed(1)} ${yAt(d.y).toFixed(1)}`)
					.join(' ')
	);
	const areaPath = $derived(
		data.length === 0
			? ''
			: `${linePath} L ${xAt(n - 1).toFixed(1)} ${(pad.t + plotH).toFixed(1)} L ${xAt(0).toFixed(1)} ${(
					pad.t + plotH
				).toFixed(1)} Z`
	);

	const ticks = $derived([0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(maxY * f)));

	function onMove(e: MouseEvent) {
		if (n === 0 || !wrapEl) return;
		const rect = wrapEl.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const i = Math.round(((mx - pad.l) / (plotW || 1)) * (n - 1));
		hoverI = Math.max(0, Math.min(n - 1, i));
	}
</script>

<div class="relative w-full" bind:this={wrapEl} style="height:{height}px">
	{#if n === 0}
		<div class="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
			{emptyLabel}
		</div>
	{:else}
		<svg {width} {height} class="block" role="img" aria-label="trend chart">
			<defs>
				<linearGradient id="dash-area-grad" x1="0" y1="0" x2="0" y2="1">
					<stop offset="0%" stop-color={color} stop-opacity="0.3" />
					<stop offset="100%" stop-color={color} stop-opacity="0.02" />
				</linearGradient>
			</defs>

			{#each ticks as t, i (i)}
				<line
					x1={pad.l}
					x2={width - pad.r}
					y1={yAt(t)}
					y2={yAt(t)}
					stroke="var(--border)"
					stroke-width="1"
				/>
				<text
					x={pad.l - 6}
					y={yAt(t) + 3}
					text-anchor="end"
					font-size="10"
					fill="var(--muted-foreground)">{yFormatter(t)}</text
				>
			{/each}

			<path d={areaPath} fill="url(#dash-area-grad)" />
			<path
				d={linePath}
				fill="none"
				stroke={color}
				stroke-width="2"
				stroke-linejoin="round"
				stroke-linecap="round"
			/>

			{#if n >= 1}
				<text
					x={xAt(0)}
					y={height - 6}
					text-anchor="start"
					font-size="10"
					fill="var(--muted-foreground)">{xFormatter(data[0].x, 0)}</text
				>
			{/if}
			{#if n > 2}
				{@const mi = Math.floor((n - 1) / 2)}
				<text
					x={xAt(mi)}
					y={height - 6}
					text-anchor="middle"
					font-size="10"
					fill="var(--muted-foreground)">{xFormatter(data[mi].x, mi)}</text
				>
			{/if}
			{#if n >= 2}
				{@const li = n - 1}
				<text
					x={xAt(li)}
					y={height - 6}
					text-anchor="end"
					font-size="10"
					fill="var(--muted-foreground)">{xFormatter(data[li].x, li)}</text
				>
			{/if}

			{#if hoverI !== null && data[hoverI]}
				<line
					x1={xAt(hoverI)}
					x2={xAt(hoverI)}
					y1={pad.t}
					y2={pad.t + plotH}
					stroke={color}
					stroke-opacity="0.45"
					stroke-width="1"
					stroke-dasharray="3 3"
				/>
				<circle
					cx={xAt(hoverI)}
					cy={yAt(data[hoverI].y)}
					r="3.5"
					fill={color}
					stroke="var(--background)"
					stroke-width="1.5"
				/>
			{/if}

			<rect
				x={pad.l}
				y={pad.t}
				width={plotW}
				height={plotH}
				fill="transparent"
				onmousemove={onMove}
				onmouseleave={() => (hoverI = null)}
				role="presentation"
			/>
		</svg>

		{#if hoverI !== null && data[hoverI]}
			<div
				class="pointer-events-none absolute top-1 z-10 whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-[11px] text-popover-foreground shadow-md"
				style="left:{Math.min(width - 130, Math.max(0, xAt(hoverI) - 60))}px"
			>
				<div class="font-medium">{xFormatter(data[hoverI].x, hoverI)}</div>
				<div class="tabular-nums text-muted-foreground">{formatFull(data[hoverI].y)}</div>
			</div>
		{/if}
	{/if}
</div>
