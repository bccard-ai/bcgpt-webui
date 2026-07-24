<script lang="ts">
	// shadcn-svelte-style Button. Phase 1 spike: validates tailwind-variants +
	// cn + the new OKLCH token utilities compiling under Svelte 5 + Tailwind v4.
	import { cn } from '$lib/utils/cn';
	import { buttonVariants, type ButtonVariant } from './variants';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { Snippet } from 'svelte';

	type Props = HTMLButtonAttributes & {
		variant?: ButtonVariant['variant'];
		size?: ButtonVariant['size'];
		/** Optional extra classes; merged via cn() after the variant classes. */
		class?: string;
		children?: Snippet;
	};

	let {
		class: className,
		variant = 'default',
		size = 'default',
		children,
		...restProps
	}: Props = $props();
</script>

<button class={cn(buttonVariants({ variant, size }), className)} {...restProps}>
	{@render children?.()}
</button>
