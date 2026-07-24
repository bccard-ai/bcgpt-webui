<script lang="ts">
	// shadcn-svelte-style Select. Token-driven single-select built on bits-ui,
	// matching Input/Button density (`size="sm"` = h-8 + text-sm, the Settings
	// standard). Portal-rendered so the popover escapes the scrolling settings
	// panel. Use this for simple enum dropdowns; keep common/Selector.svelte for
	// searchable / rich model-picker dropdowns.
	import { Select } from 'bits-ui';
	import { cn } from '$lib/utils/cn';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import type { Snippet } from 'svelte';

	type Option = { value: string; label: string };

	type Props = {
		class?: string;
		/** Bindable selected value. */
		value?: string;
		/** Options for the default list mode. Ignored when `children` is set. */
		items?: Option[];
		/** Trigger placeholder. */
		placeholder?: string;
		/** Control height. `sm` = h-8 (Settings standard); `default` = h-9. */
		size?: 'sm' | 'default';
		/** Disable the trigger. */
		disabled?: boolean;
		/** Called with the new value on change. */
		onValueChange?: (value: string) => void;
		/** Custom Trigger + Content (advanced). When set, `items` is ignored. */
		children?: Snippet;
	};

	let {
		class: className,
		value = $bindable(''),
		items = [],
		placeholder = '',
		size = 'sm',
		disabled = false,
		onValueChange,
		children
	}: Props = $props();

	const handleChange = (v: string) => {
		value = v;
		onValueChange?.(v);
	};
</script>

<Select.Root type="single" {items} {value} {disabled} onValueChange={handleChange}>
	{#if children}
		{@render children()}
	{:else}
		<Select.Trigger class={cn('relative w-full', className)} aria-label={placeholder}>
			<Select.Value
				class={cn(
					'inline-flex w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring',
					size === 'sm' ? 'h-8' : 'h-9'
				)}
				{placeholder}
			/>
			<ChevronDown
				className="pointer-events-none absolute end-2.5 top-1/2 size-3.5 -translate-y-1/2 opacity-60"
				strokeWidth="2.5"
			/>
		</Select.Trigger>
		<Select.Portal>
			<Select.Content
				class="z-50 max-h-72 min-w-[var(--bits-anchor-width)] overflow-y-auto rounded-md border border-input bg-popover p-1 text-popover-foreground shadow-lg outline-none"
				sideOffset={4}
			>
				{#each items as item (item.value)}
					<Select.Item
						class="flex w-full cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground data-highlighted:bg-accent data-highlighted:text-accent-foreground"
						value={item.value}
						label={item.label}
					>
						{item.label}
					</Select.Item>
				{/each}
			</Select.Content>
		</Select.Portal>
	{/if}
</Select.Root>
