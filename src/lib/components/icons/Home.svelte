<script lang="ts">
	/**
	 * Home icon component.
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
	stroke-width={strokeWidth}
	stroke="currentColor"
	class={className}
	aria-hidden="true"
	xmlns="http://www.w3.org/2000/svg"
	fill="none"
	width="24"
	height="24"
	viewBox="0 0 22 22"
>
	<path
		stroke="currentColor"
		stroke-linecap="round"
		stroke-linejoin="round"
		d="m4 12 8-8 8 8M6 10.5V19a1 1 0 0 0 1 1h3v-3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v3h3a1 1 0 0 0 1-1v-8.5"
	/>
</svg>
