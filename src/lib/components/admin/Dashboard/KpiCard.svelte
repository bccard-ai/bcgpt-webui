<!--
  Compact KPI stat card. Clickable (href) when a destination exists.
  `icon` and `accent` tint the icon chip; `sub` renders a context line.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { resolve } from '$app/paths';

	interface Props {
		label: string;
		value: string;
		sub?: string;
		icon?: Snippet;
		href?: string;
		loading?: boolean;
		refreshing?: boolean;
		error?: boolean;
		accent?: string;
	}

	let {
		label,
		value,
		sub,
		icon,
		href,
		loading = false,
		refreshing = false,
		error = false,
		accent = 'var(--chart-1)'
	}: Props = $props();

	const cardClass =
		'flex flex-col gap-2 rounded-xl border border-border bg-card p-4 transition hover:border-primary/50 hover:shadow-sm';
</script>

{#snippet body()}
	<div class="flex items-center justify-between">
		<span class="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
		{#if icon}
			<span
				class="flex size-7 items-center justify-center rounded-md"
				style="background:color-mix(in oklch, {accent} 14%, transparent);color:{accent}"
			>
				{@render icon()}
			</span>
		{/if}
	</div>

	{#if loading}
		<div class="h-7 w-24 animate-pulse rounded bg-muted"></div>
	{:else if error}
		<span class="text-2xl font-bold text-muted-foreground">—</span>
	{:else}
		<span
			class="text-2xl font-bold tabular-nums transition-opacity duration-150 {refreshing
				? 'opacity-50'
				: 'opacity-100'}">{value}</span
		>
	{/if}

	{#if sub}
		<span class="truncate text-xs text-muted-foreground">{sub}</span>
	{/if}
{/snippet}

{#if href}
	<a href={resolve(href as unknown as '/')} class="group {cardClass}">
		{@render body()}
	</a>
{:else}
	<div class={cardClass}>
		{@render body()}
	</div>
{/if}
