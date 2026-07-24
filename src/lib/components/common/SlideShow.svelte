<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	/**
	 * SlideShow — cross-fade image slideshow with configurable duration.
	 *
	 * @example
	 * ```svelte
	 * <SlideShow imageUrls={['/img1.jpg', '/img2.jpg']} duration={3000} />
	 * ```
	 *
	 * @props imageUrls - Array of image URLs to cycle through
	 * @props duration - Time in ms between slides
	 */
	interface Props {
		/** Array of image URLs. */
		imageUrls?: string[];
		/** Time in milliseconds between slides. Defaults to `5000`. */
		duration?: number;
	}

	let {
		imageUrls = [
			'/assets/images/shaun-jones.jpg',
			'/assets/images/galaxy.jpg',
			'/assets/images/nick-nice.jpg',
			'/assets/images/matthew-smith.jpg',
			'/assets/images/markus-spiske.jpg',
			'/assets/images/315M82HdrH4.jpg'
		],
		duration = 5000
	}: Props = $props();

	let selectedImageIdx = $state(0);
	let intervalId: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		intervalId = setInterval(() => {
			selectedImageIdx = (selectedImageIdx + 1) % (imageUrls.length - 1);
		}, duration);
	});

	onDestroy(() => {
		if (intervalId) clearInterval(intervalId);
	});
</script>

{#each imageUrls as imageUrl, idx (idx)}
	<div
		class="image w-full h-full absolute top-0 left-0 bg-cover bg-center transition-opacity duration-1000"
		style="opacity: {selectedImageIdx === idx ? 1 : 0}; background-image: url('{imageUrl}')"
	></div>
{/each}

<style>
	.image {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		background-size: cover;
		background-position: center;
		transition: opacity 1s ease-in-out;
		opacity: 0.7;
	}
</style>
