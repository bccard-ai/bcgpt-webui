<script lang="ts">
	/**
	 * Hamburger menu lines icon component.
	 * @param { string } [className] - CSS class for the SVG element.
	 * @param { string } [strokeWidth] - Stroke width for the SVG paths.
	 */
	interface Props {
		className?: string;
		strokeWidth?: string;
	}

	let { className = 'size-5', strokeWidth = '2' }: Props = $props();
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
		d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12"
	/>
</svg>
