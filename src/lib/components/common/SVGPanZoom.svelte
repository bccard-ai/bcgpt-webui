<script lang="ts">
	import fileSaver from 'file-saver';
	import { toast } from 'svelte-sonner';
	import panzoom, { type PanZoom } from 'panzoom';
	import DOMPurify from 'dompurify';
	import { getContext } from 'svelte';
	import { copyToClipboard } from '$lib/utils';

	import Tooltip from './Tooltip.svelte';
	import Clipboard from '../icons/Clipboard.svelte';
	import Reset from '../icons/Reset.svelte';
	import ArrowDownTray from '../icons/ArrowDownTray.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const { saveAs } = fileSaver;
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * SVGPanZoom — renders an SVG with pan/zoom, download, reset, and copy controls.
	 *
	 * @example
	 * ```svelte
	 * <SVGPanZoom svg={mermaidSvg} content={diagramCode} />
	 * ```
	 *
	 * @props svg - SVG string to render
	 * @props content - Plain-text source for copy-to-clipboard
	 * @props className - CSS classes on the wrapper
	 */
	interface Props {
		/** CSS classes on the wrapper div. */
		className?: string;
		/** SVG string to render (DOMPurify-sanitized). */
		svg?: string;
		/** Plain-text source for copy-to-clipboard. If empty, controls are hidden. */
		content?: string;
	}

	let { className = '', svg = '', content = '' }: Props = $props();

	let instance: PanZoom = $state();
	let sceneElement: HTMLElement = $state();

	$effect(() => {
		if (sceneElement) {
			instance = panzoom(sceneElement, {
				bounds: true,
				boundsPadding: 0.1,
				zoomSpeed: 0.065
			});
		}
	});

	const resetPanZoomViewport = () => {
		instance?.moveTo(0, 0);
		instance?.zoomAbs(0, 0, 1);
	};

	const downloadAsSVG = () => {
		const svgBlob = new Blob([svg], { type: 'image/svg+xml' });
		saveAs(svgBlob, 'diagram.svg');
	};
</script>

<div class="relative {className}">
	<div bind:this={sceneElement} class="flex h-full max-h-full justify-center items-center">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: DOMPurify-sanitized SVG (mermaid strict source) -->
		{@html DOMPurify.sanitize(svg)}
	</div>

	{#if content}
		<div class=" absolute top-1 right-1">
			<div class="flex gap-1">
				<Tooltip content={$i18n.t('Download as SVG')}>
					<button
						class="p-1.5 rounded-lg border border-gray-100 dark:border-none dark:bg-gray-850 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						onclick={downloadAsSVG}
					>
						<ArrowDownTray className=" size-4" />
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('Reset view')}>
					<button
						class="p-1.5 rounded-lg border border-gray-100 dark:border-none dark:bg-gray-850 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						onclick={resetPanZoomViewport}
					>
						<Reset className=" size-4" />
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('Copy to clipboard')}>
					<button
						class="p-1.5 rounded-lg border border-gray-100 dark:border-none dark:bg-gray-850 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						aria-label="Copy to clipboard"
						onclick={() => {
							copyToClipboard(content);
							toast.success($i18n.t('Copied to clipboard'));
						}}
					>
						<Clipboard className=" size-4" strokeWidth="1.5" />
					</button>
				</Tooltip>
			</div>
		</div>
	{/if}
</div>
