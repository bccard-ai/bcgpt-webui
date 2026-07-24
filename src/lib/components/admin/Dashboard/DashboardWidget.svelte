<!--
  Dashboard widget shell. To avoid layout shift on range changes:
  - `loading`  → first load only (no data yet): full skeleton.
  - `refreshing` → refetch with data already present: keep content visible
                  (dimmed) + a header spinner. Height stays stable.
  - `empty`    → loaded but no rows.
  - `error`    → failure with retry.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { resolve } from '$app/paths';

	interface Props {
		title: string;
		icon?: Snippet;
		href?: string;
		hrefLabel?: string;
		loading?: boolean;
		refreshing?: boolean;
		error?: string | null;
		empty?: boolean;
		emptyLabel?: string;
		onRetry?: () => void;
		class?: string;
		bodyClass?: string;
		children: Snippet;
	}

	let {
		title,
		icon,
		href,
		hrefLabel = 'View all',
		loading = false,
		refreshing = false,
		error = null,
		empty = false,
		emptyLabel = 'No data',
		onRetry,
		class: cls = '',
		bodyClass = '',
		children
	}: Props = $props();
</script>

<section
	class="flex flex-col overflow-hidden rounded-xl border border-border bg-card text-card-foreground {cls}"
>
	<header class="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
		<div class="flex min-w-0 items-center gap-2">
			{#if icon}
				<span class="text-muted-foreground">{@render icon()}</span>
			{/if}
			<h3 class="truncate text-sm font-semibold">{title}</h3>
			{#if refreshing}
				<span class="size-3.5 animate-spin rounded-full border-2 border-muted border-t-primary"
				></span>
			{/if}
		</div>
		{#if href}
			<a
				href={resolve(href as unknown as '/')}
				class="shrink-0 text-xs text-muted-foreground transition hover:text-primary"
			>
				{hrefLabel} →
			</a>
		{/if}
	</header>

	<div class="flex-1 p-4 {bodyClass}">
		{#if error}
			<div class="flex flex-col items-center justify-center gap-2 py-8 text-center">
				<p class="text-xs text-destructive">{error}</p>
				{#if onRetry}
					<button class="text-xs text-primary hover:underline" onclick={onRetry}>Retry</button>
				{/if}
			</div>
		{:else if loading}
			<div class="flex h-48 items-center justify-center">
				<div class="size-5 animate-spin rounded-full border-2 border-muted border-t-primary"></div>
			</div>
		{:else if empty}
			<div class="flex items-center justify-center py-10 text-xs text-muted-foreground">
				{emptyLabel}
			</div>
		{:else}
			<div class="transition-opacity duration-150 {refreshing ? 'opacity-50' : 'opacity-100'}">
				{@render children()}
			</div>
		{/if}
	</div>
</section>
