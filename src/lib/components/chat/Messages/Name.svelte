<script lang="ts">
	import type { Snippet } from 'svelte';

	/** Props for the Name component - displays the sender's name badge */
	interface Props {
		children?: Snippet;
	}

	let { children }: Props = $props();
</script>

<div class="self-center font-semibold line-clamp-1 flex gap-1 items-center">
	{@render children?.()}
</div>
