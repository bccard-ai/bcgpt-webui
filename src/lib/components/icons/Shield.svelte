<script lang="ts">
	/**
	 * @param { string } [className] - CSS class for the SVG element.
	 * @param { string } [strokeWidth] - Stroke width for the SVG paths.
	 */
	interface Props {
		className?: string;
		strokeWidth?: string;
	}

	let { className = 'size-4', strokeWidth = '1.5' }: Props = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	fill="none"
	viewBox="0 0 24 24"
	stroke-width={strokeWidth}
	stroke="currentColor"
	class={className}
>
	<path
		stroke-linecap="round"
		stroke-linejoin="round"
		d="M12 2.25 4.5 5.25v6c0 4.97 3.2 8.97 7.5 10.5 4.3-1.53 7.5-5.53 7.5-10.5v-6L12 2.25Z"
	/>
</svg>
