<script lang="ts">
	import Spinner from './Spinner.svelte';

	/**
	 * Overlay — translucent loading overlay that covers its parent.
	 *
	 * @example
	 * ```svelte
	 * <Overlay show={loading} content="Processing...">
	 *   <div>Content beneath the overlay</div>
	 * </Overlay>
	 * ```
	 *
	 * @props show - Whether the overlay is visible
	 * @props content - Optional text shown beneath the spinner
	 * @props opacity - Overlay backdrop opacity (0-1)
	 */
	interface Props {
		/** Whether the overlay is visible. */
		show?: boolean;
		/** Optional text shown beneath the spinner. */
		content?: string;
		/** Backdrop opacity. Defaults to `1`. */
		opacity?: number;
		/** Content rendered beneath the overlay. */
		children?: import('svelte').Snippet;
	}

	let {
		show = false,
		content = '',
		opacity = 1,
		children
	}: Props = $props();
</script>

<div class="relative">
	{#if show}
		<div class="absolute w-full h-full flex">
			<div
				class="absolute rounded-sm"
				style="inset: -10px; opacity: {opacity}; backdrop-filter: blur(5px);"
			></div>

			<div class="flex w-full flex-col justify-center">
				<div class=" py-3">
					<Spinner className="ml-2" />
				</div>

				{#if content !== ''}
					<div class="text-center text-gray-100 text-xs font-medium z-50">
						{content}
					</div>
				{/if}
			</div>
		</div>
	{/if}

	{@render children?.()}
</div>
