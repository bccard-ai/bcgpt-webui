<script lang="ts">
	/**
	 * Badge — small coloured label for status indicators.
	 *
	 * @example
	 * ```svelte
	 * <Badge type="success" content="Active" />
	 * ```
	 *
	 * @props type - Badge colour variant: 'info' | 'success' | 'warning' | 'error' | 'muted'
	 * @props content - Badge text
	 */
	interface Props {
		/** Badge colour variant. Defaults to `'info'`. */
		type?: string;
		/** Badge text. */
		content?: string;
	}

	let { type = 'info', content = '' }: Props = $props();

	const CLASS_MAP: Record<string, string> = {
		info: 'bg-blue-500/20 text-blue-700 dark:text-blue-200 ',
		success: 'bg-green-500/20 text-green-700 dark:text-green-200',
		warning: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-200',
		error: 'bg-red-500/20 text-red-700 dark:text-red-200',
		muted: 'bg-gray-500/20 text-gray-700 dark:text-gray-200'
	};
</script>

<div
	class=" text-xs font-bold {CLASS_MAP[type] ??
		CLASS_MAP['info']}  w-fit px-2 rounded-sm uppercase line-clamp-1 mr-0.5"
>
	{content}
</div>
