<script lang="ts">
	import { fade, slide } from 'svelte/transition';

	/**
	 * Sidebar (common) — positioned sidebar panel that slides in from left or right.
	 *
	 * This is a lightweight, position-aware sidebar for in-page panels.
	 * Not to be confused with the main layout Sidebar component.
	 *
	 * @example
	 * ```svelte
	 * <Sidebar bind:show side="right" width="300px">
	 *   <p>Panel content</p>
	 * </Sidebar>
	 * ```
	 *
	 * @props show - Bindable visibility
	 * @props side - Which side the panel slides from: 'left' | 'right'
	 * @props width - Panel width in CSS units
	 * @props duration - Transition duration in ms
	 */
	interface Props {
		/** Bindable visibility. */
		show?: boolean;
		/** Which side the panel slides from. Defaults to `'right'`. */
		side?: string;
		/** Panel width in CSS units. Defaults to `'200px'`. */
		width?: string;
		/** CSS classes on the inner content div. */
		className?: string;
		/** Transition duration in ms. Defaults to `100`. */
		duration?: number;
		/** Panel content. */
		children?: import('svelte').Snippet;
	}

	let {
		show = $bindable(false),
		side = 'right',
		width = '200px',
		className = '',
		duration = 100,
		children
	}: Props = $props();
</script>

{#if show}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="absolute z-20 top-0 right-0 left-0 bottom-0 bg-white/20 dark:bg-black/5 w-full min-h-full h-full flex justify-center overflow-hidden overscroll-contain"
		onmousedown={() => {
			show = false;
		}}
		transition:fade={{ duration: duration }}
	></div>

	<div
		class="absolute z-30 shadow-xl {side === 'right' ? 'right-0' : 'left-0'} top-0 bottom-0"
		transition:slide={{ duration: duration, axis: side === 'right' ? 'x' : 'y' }}
	>
		<div class="{className} h-full" style="width: {show ? width : '0px'}">
			{@render children?.()}
		</div>
	</div>
{/if}
