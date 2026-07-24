<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	/**
	 * DragGhost — floating overlay that follows the cursor during drag operations.
	 *
	 * Portals a fixed-position element to `document.body` that tracks x/y coordinates.
	 *
	 * @example
	 * ```svelte
	 * {#if dragging}
	 *   <DragGhost x={mouseX} y={mouseY}>
	 *     <div>Dragging item</div>
	 *   </DragGhost>
	 * {/if}
	 * ```
	 *
	 * @props x - Horizontal cursor position
	 * @props y - Vertical cursor position
	 */
	let { x, y, children } = $props();

	let popupElement: HTMLDivElement | null = $state(null);

	onMount(() => {
		if (popupElement) {
			document.body.appendChild(popupElement);
			document.body.style.overflow = 'hidden';
		}
	});

	onDestroy(() => {
		if (popupElement && document.body.contains(popupElement)) {
			document.body.removeChild(popupElement);
		}
		document.body.style.overflow = '';
	});
</script>

<div
	bind:this={popupElement}
	class="fixed top-0 left-0 w-screen h-[100dvh] z-50 touch-none pointer-events-none"
>
	<div class=" absolute text-white z-99999" style="top: {y + 10}px; left: {x + 10}px;">
		{@render children?.()}
	</div>
</div>
