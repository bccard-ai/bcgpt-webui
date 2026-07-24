<script lang="ts">
	/**
	 * Skeleton — animated placeholder for loading states.
	 *
	 * @example
	 * ```svelte
	 * <Skeleton variant="circle" width="48px" />
	 * <Skeleton variant="text" count={3} />
	 * ```
	 *
	 * @props width - CSS width value
	 * @props height - CSS height value
	 * @props variant - Shape: 'text' | 'circle' | 'rect'
	 * @props count - Number of skeleton elements to render
	 */
	interface Props {
		/** CSS width. Defaults to `100%`. */
		width?: string;
		/** CSS height. Defaults to `1rem`. */
		height?: string;
		/** Shape variant. `'circle'` forces width for both dimensions. */
		variant?: 'text' | 'circle' | 'rect';
		/** Number of skeleton elements to render. */
		count?: number;
	}

	let { width = '100%', height = '1rem', variant = 'text', count = 1 }: Props = $props();

	let baseClasses = $derived(
		variant === 'circle' ? 'rounded-full' : variant === 'rect' ? 'rounded-lg' : 'rounded'
	);

	let style = $derived(
		variant === 'circle'
			? `width: ${width}; height: ${width};`
			: `width: ${width}; height: ${height};`
	);
</script>

{#each Array(count) as _, i (i)}
	<div
		class="bg-gray-200 dark:bg-gray-800 animate-pulse {baseClasses}"
		{style}
		aria-hidden="true"
	></div>
{/each}
