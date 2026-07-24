<!--
  Dashboard command bar: time-range segmented control + auto-refresh
  toggle + manual refresh. Reads/writes the shared dashboard context.
-->
<script lang="ts">
	import { useDashboard, RANGE_OPTIONS } from './context';
	import ArrowPath from '$lib/components/icons/ArrowPath.svelte';

	const d = useDashboard();
</script>

<div class="flex flex-wrap items-center justify-between gap-3">
	<div class="inline-flex rounded-lg border border-border bg-card p-0.5">
		{#each RANGE_OPTIONS as opt (opt.key)}
			<button
				class="rounded-md px-3 py-1 text-xs font-medium transition {d.range.key === opt.key
					? 'bg-primary text-primary-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				onclick={() => d.setRangeKey(opt.key)}
			>
				{opt.label}
			</button>
		{/each}
	</div>

	<div class="flex items-center gap-3">
		<label
			class="flex cursor-pointer select-none items-center gap-1.5 text-xs text-muted-foreground"
		>
			<input type="checkbox" class="sr-only" bind:checked={d.auto} />
			<span
				class="relative inline-flex h-4 w-7 items-center rounded-full transition {d.auto
					? 'bg-primary'
					: 'bg-muted'}"
			>
				<span
					class="inline-block size-3 transform rounded-full bg-background shadow transition {d.auto
						? 'translate-x-3.5'
						: 'translate-x-0.5'}"
				></span>
			</span>
			Auto
		</label>

		<button
			class="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
			onclick={() => d.refresh()}
			title="Refresh now"
		>
			<ArrowPath className="size-3.5" />
			Refresh
		</button>
	</div>
</div>
