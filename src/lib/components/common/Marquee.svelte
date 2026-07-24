<script lang="ts">
	import { fly } from 'svelte/transition';
	import { onMount, onDestroy } from 'svelte';

	/**
	 * Marquee — animated word carousel with fly-in transition.
	 *
	 * @example
	 * ```svelte
	 * <Marquee words={['Hello', 'World']} duration={4000} />
	 * ```
	 *
	 * @props words - Array of words to cycle through
	 * @props duration - Time in ms between word changes
	 * @props className - CSS classes on the wrapper
	 */
	interface Props {
		/** CSS classes on the wrapper. */
		className?: string;
		/** Array of words to cycle through. */
		words?: string[];
		/** Time in milliseconds between word changes. Defaults to `4000`. */
		duration?: number;
	}

	let { className = '', words = ['lorem', 'ipsum'], duration = 4000 }: Props = $props();

	let idx = $state(0);
	let intervalId: ReturnType<typeof setInterval> | null = null;

	onMount(() => {
		intervalId = setInterval(() => {
			idx = idx === words.length - 1 ? 0 : idx + 1;
		}, duration);
	});

	onDestroy(() => {
		if (intervalId) clearInterval(intervalId);
	});
</script>

<div class={className}>
	<div>
		{#key idx}
			<div class=" marquee-item" in:fly={{ y: '30%', duration: 1000 }}>
				{words.at(idx)}
			</div>
		{/key}
	</div>
</div>
