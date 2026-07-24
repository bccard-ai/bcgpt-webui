<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	/**
	 * Loader — intersection-observer wrapper that calls onVisible while in viewport.
	 *
	 * Useful for infinite-scroll: the callback fires on an interval while the
	 * element is visible, and stops when scrolled out of view.
	 *
	 * @example
	 * ```svelte
	 * <Loader onVisible={loadMore}>
	 *   <Spinner />
	 * </Loader>
	 * ```
	 *
	 * @props onVisible - Called repeatedly while the element is in the viewport
	 */
	interface Props {
		/** Content rendered inside the loader wrapper. */
		children?: import('svelte').Snippet;
		/** Callback invoked on an interval (~100ms) while the element is visible. */
		onVisible?: () => void;
	}

	let { children, onVisible = () => {} }: Props = $props();
	let loaderElement: HTMLElement = $state();

	let observer: IntersectionObserver | null = null;
	let intervalId: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						intervalId = setInterval(() => {
							onVisible?.();
						}, 100);
					} else {
						if (intervalId) {
							clearInterval(intervalId);
							intervalId = null;
						}
					}
				});
			},
			{
				root: null,
				rootMargin: '0px',
				threshold: 0.1
			}
		);

		if (loaderElement) {
			observer.observe(loaderElement);
		}
	});

	onDestroy(() => {
		observer?.disconnect();
		if (intervalId) {
			clearInterval(intervalId);
		}
	});
</script>

<div bind:this={loaderElement}>
	{@render children?.()}
</div>
