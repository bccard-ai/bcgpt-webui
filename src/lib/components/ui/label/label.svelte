<script lang="ts">
	// shadcn-svelte-style Label. text-sm font-medium on the foreground token —
	// the single label style for every settings field.
	import { cn } from '$lib/utils/cn';
	import type { HTMLLabelAttributes } from 'svelte/elements';
	import type { Snippet } from 'svelte';

	type Props = HTMLLabelAttributes & {
		class?: string;
		children?: Snippet;
	};

	let { class: className, children, ...restProps }: Props = $props();
</script>

<label class={cn('text-sm font-medium text-foreground', className)} {...restProps}>
	{@render children?.()}
</label>
