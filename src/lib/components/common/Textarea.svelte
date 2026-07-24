<script lang="ts">
	import { onMount, tick } from 'svelte';

	/**
	 * Textarea — auto-resizing textarea with bindable value.
	 *
	 * @example
	 * ```svelte
	 * <Textarea bind:value placeholder="Enter text..." />
	 * ```
	 *
	 * @props value - Bindable text value
	 * @props placeholder - Placeholder text
	 * @props rows - Initial rows (visual only, height auto-adjusts)
	 * @props required - HTML required attribute
	 * @props className - CSS classes on the textarea element
	 */
	interface Props {
		/** Bindable text content. */
		value?: string;
		/** Placeholder text. */
		placeholder?: string;
		/** Initial number of rows. Height auto-adjusts. */
		rows?: number;
		/** HTML required attribute. */
		required?: boolean;
		/** CSS classes on the textarea element. */
		className?: string;
	}

	let {
		value = $bindable(''),
		placeholder = '',
		rows = 1,
		required = false,
		className = 'w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden  h-full'
	}: Props = $props();

	let textareaElement: HTMLTextAreaElement = $state();

	const resize = () => {
		if (textareaElement) {
			textareaElement.style.height = '';
			textareaElement.style.height = `${textareaElement.scrollHeight}px`;
		}
	};

	onMount(async () => {
		await tick();
		resize();

		const interval = setInterval(() => {
			if (textareaElement) {
				clearInterval(interval);
				resize();
			}
		}, 100);
	});
</script>

<textarea
	bind:this={textareaElement}
	bind:value
	{placeholder}
	class={className}
	style="field-sizing: content;"
	{rows}
	{required}
	oninput={() => {
		resize();
	}}
	onfocus={() => {
		resize();
	}}
></textarea>
