<script lang="ts">
	import type { Snippet } from 'svelte';

	/**
	 * InfoCallout — small info/warning callout box with icon.
	 *
	 * @example
	 * ```svelte
	 * <InfoCallout variant="warning">
	 *   This action cannot be undone.
	 * </InfoCallout>
	 * ```
	 *
	 * @props variant - Style variant: 'info' | 'warning'
	 */
	interface Props {
		/** Style variant. Defaults to `'info'`. */
		variant?: 'info' | 'warning';
		/** Callout content. */
		children: Snippet;
	}

	let { variant = 'info', children }: Props = $props();
</script>

<div
	class="flex items-start gap-2.5 p-3 mb-4 rounded-lg text-xs leading-relaxed border {variant ===
	'warning'
		? 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-900/40 text-amber-900 dark:text-amber-200'
		: 'bg-blue-50 dark:bg-blue-900/10 border-blue-100 dark:border-blue-900/30 text-gray-600 dark:text-gray-300'}"
	role="note"
>
	<svg
		xmlns="http://www.w3.org/2000/svg"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.5"
		class="size-4 shrink-0 mt-0.5 {variant === 'warning' ? 'text-amber-500' : 'text-blue-500'}"
		aria-hidden="true"
	>
		<path
			stroke-linecap="round"
			stroke-linejoin="round"
			d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
		/>
	</svg>
	<div>{@render children()}</div>
</div>
