<script lang="ts">
	import DOMPurify from 'dompurify';
	import { onDestroy } from 'svelte';
	import tippy from 'tippy.js';
	import type { Instance, Props as TippyProps } from 'tippy.js';

	/**
	 * Tooltip — declarative tooltip using tippy.js with DOMPurify sanitisation.
	 *
	 * @example
	 * ```svelte
	 * <Tooltip content="Helpful tip" placement="top">
	 *   <button>Hover me</button>
	 * </Tooltip>
	 * ```
	 *
	 * @props content - Tooltip text. Empty string disables the tooltip.
	 * @props placement - Tippy placement string
	 * @props touch - Enable touch support
	 * @props theme - Tippy theme name
	 * @props offset - [skid, distance] offset
	 * @props allowHTML - Whether to render HTML content
	 * @props tippyOptions - Additional tippy.js options
	 */
	interface Props {
		/** Tippy placement string. Defaults to `'top'`. */
		placement?: 'top' | 'bottom' | 'left' | 'right' | 'auto' | 'auto-start' | 'auto-end' | 'top-start' | 'top-end' | 'bottom-start' | 'bottom-end' | 'right-start' | 'right-end' | 'left-start' | 'left-end';
		/** Tooltip text. Set to empty string to disable. */
		content?: string;
		/** Enable touch support. Defaults to `true`. */
		touch?: boolean;
		/** CSS class on the wrapper div. */
		className?: string;
		/** Tippy theme name. Defaults to `'dark'`. */
		theme?: string;
		/** [skid, distance] offset. Defaults to `[0, 4]`. */
		offset?: [number, number];
		/** Allow HTML in tooltip content. Defaults to `true`. */
		allowHTML?: boolean;
		/** Additional tippy.js options. */
		tippyOptions?: Partial<TippyProps>;
		/** Wrapped element(s). */
		children?: import('svelte').Snippet;
	}

	let {
		placement = 'top',
		content = `I'm a tooltip!`,
		touch = true,
		className = 'flex',
		theme = '',
		offset = [0, 4],
		allowHTML = true,
		tippyOptions = {},
		children
	}: Props = $props();

	let tooltipElement: HTMLElement | undefined = $state();
	// Plain (non-reactive) handle: tippy instance is not UI state.
	let tooltipInstance: Instance | null = null;

	$effect(() => {
		if (tooltipElement && content) {
			if (tooltipInstance) {
				tooltipInstance.setContent(DOMPurify.sanitize(content));
			} else {
				tooltipInstance = tippy(tooltipElement, {
					content: DOMPurify.sanitize(content),
					placement: placement,
					allowHTML: allowHTML,
					touch: touch,
					...(theme !== '' ? { theme } : { theme: 'dark' }),
					arrow: false,
					offset: offset,
					...tippyOptions
				});
			}
		} else if (tooltipInstance && content === '') {
			tooltipInstance.destroy();
			tooltipInstance = null;
		}
	});

	onDestroy(() => {
		if (tooltipInstance) {
			tooltipInstance.destroy();
			tooltipInstance = null;
		}
	});
</script>

<div bind:this={tooltipElement} aria-label={DOMPurify.sanitize(content)} class={className}>
	{@render children?.()}
</div>
