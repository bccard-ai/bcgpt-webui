<script lang="ts">
	// Field — the single layout wrapper for settings form rows. Replaces the
	// ad-hoc `<div class="mb-1 text-xs font-medium">Label</div>` + control +
	// helper stacks (and the inline label + Switch rows) with one consistent
	// shape: a text-sm label, an optional text-xs description, the control slot,
	// and an optional text-xs helper note.
	//
	// - Stacked (default): label above the control — use for Input/Select/Textarea.
	// - inline:            label left, control right — use for Switch rows.
	// - separator:         adds the classic dashed bottom border between rows.
	import { cn } from '$lib/utils/cn';
	import type { Snippet } from 'svelte';

	type Props = {
		class?: string;
		/** Label text. */
		label?: string;
		/** Optional description shown beneath the label. */
		description?: string;
		/** Optional helper / error note shown beneath the control (stacked only). */
		helper?: string;
		/** Place the label to the left of the control instead of above it. */
		inline?: boolean;
		/** Render a dashed bottom separator (the classic settings-row look). */
		separator?: boolean;
		/** Control slot. */
		children?: Snippet;
	};

	let {
		class: className,
		label = '',
		description = '',
		helper = '',
		inline = false,
		separator = false,
		children
	}: Props = $props();
</script>

<div
	class={cn(
		'flex w-full',
		inline ? 'items-center justify-between gap-3' : 'flex-col gap-1',
		separator && 'mb-2.5 border-b border-dashed border-border pb-2',
		className
	)}
>
	{#if label || description}
		<div class={inline ? 'min-w-0' : ''}>
			{#if label}
				<div class="text-sm font-medium text-foreground">{label}</div>
			{/if}
			{#if description}
				<div class="text-xs text-muted-foreground">{description}</div>
			{/if}
		</div>
	{/if}
	<div class={inline ? 'flex shrink-0 items-center' : 'min-w-0'}>
		{@render children?.()}
		{#if helper && !inline}
			<div class="mt-1 text-xs text-muted-foreground">{helper}</div>
		{/if}
	</div>
</div>
