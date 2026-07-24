<script lang="ts">
	// shadcn-svelte-style Textarea. Token-driven (border-input / bg-background /
	// ring-ring), text-sm baseline, matching the Input/Select kit.
	import { cn } from '$lib/utils/cn';
	import type { HTMLTextareaAttributes } from 'svelte/elements';

	type Props = Omit<HTMLTextareaAttributes, 'value'> & {
		class?: string;
		value?: string;
	};

	let { class: className, value = $bindable(''), ...restProps }: Props = $props();
</script>

<textarea
	bind:value
	class={cn(
		'flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
		className
	)}
	{...restProps}
></textarea>
