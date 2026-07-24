<script lang="ts">
	// shadcn-svelte-style Input. Token-driven (border-input / bg-background /
	// ring-ring), with a `size` variant (`sm` = h-8 compact, `default` = h-9) and
	// an optional `mono` variant for identifier-style content (URLs, API keys,
	// IDs) — the "instrument panel" feel of the research-instrument direction.
	import { cn } from '$lib/utils/cn';
	import type { HTMLInputAttributes } from 'svelte/elements';

	type Props = Omit<HTMLInputAttributes, 'value' | 'size'> & {
		class?: string;
		/** Render in monospace — for URLs, IDs, keys. */
		mono?: boolean;
		/** Control height. `sm` = h-8 (compact, the Settings standard); `default` = h-9. */
		size?: 'sm' | 'default';
		value?: string;
	};

	let {
		class: className,
		mono = false,
		size = 'default',
		value = $bindable(''),
		...restProps
	}: Props = $props();
</script>

<input
	bind:value
	class={cn(
		'flex w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
		size === 'sm' ? 'h-8' : 'h-9',
		mono && 'font-mono text-[13px]',
		className
	)}
	{...restProps}
/>
