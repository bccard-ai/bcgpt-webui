<script lang="ts">
	import { getContext } from 'svelte';
	import { formatFileSize } from '$lib/utils';

	import FileItemModal from './FileItemModal.svelte';
	import Spinner from './Spinner.svelte';
	import Tooltip from './Tooltip.svelte';

	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * FileItem — displays a file/document/knowledge card with preview, dismiss, and loading states.
	 *
	 * @example
	 * ```svelte
	 * <FileItem name="report.pdf" type="file" size={1024} dismissible onDismiss={handleRemove} />
	 * ```
	 *
	 * @props name - File name
	 * @props type - Item type: 'file' | 'doc' | 'collection' | 'knowledge'
	 * @props size - File size in bytes
	 * @props url - Click-through URL
	 * @props dismissible - Show dismiss button on hover
	 * @props loading - Show loading spinner
	 * @props item - Full item object for modal preview
	 * @props edit - Enable edit mode in preview modal
	 * @props small - Compact display mode
	 */
	interface Props {
		/** CSS classes on the card wrapper. */
		className?: string;
		/** CSS classes for the card color scheme. */
		colorClassName?: string;
		/** Click-through URL. */
		url?: string | null;
		/** Show dismiss button on hover. */
		dismissible?: boolean;
		/** Show loading spinner. */
		loading?: boolean;
		/** Full item object (enables modal preview). */
		item?: { file?: { data?: { content?: string } } } | null;
		/** Enable edit mode in the preview modal. */
		edit?: boolean;
		/** Compact display mode. */
		small?: boolean;
		/** File name. */
		name: string;
		/** Item type label. */
		type: string;
		/** File size in bytes. */
		size: number;
		/** Called when the card is clicked. */
		onClick?: (...args: unknown[]) => void;
		/** Called when the dismiss button is clicked. */
		onDismiss?: (...args: unknown[]) => void;
	}

	let {
		className = 'w-60',
		colorClassName = 'bg-white dark:bg-gray-850 border border-gray-50 dark:border-white/5',
		url = null,
		dismissible = false,
		loading = false,
		item = null,
		edit = false,
		small = false,
		name,
		type,
		size,
		onClick = () => {},
		onDismiss = () => {}
	}: Props = $props();

	let showModal = $state(false);

	const handleOpen = () => {
		if (item?.file?.data?.content) {
			showModal = !showModal;
		} else if (url) {
			window.open(type === 'file' ? `${url}/content` : url, '_blank')?.focus();
		}
		onClick?.();
	};
</script>

{#if item}
	<FileItemModal bind:show={showModal} {item} {edit} />
{/if}

<div
	class="relative group p-1.5 {className} flex items-center gap-1 {colorClassName} {small
		? 'rounded-xl'
		: 'rounded-2xl'} text-left cursor-pointer"
	role="button"
	tabindex="0"
	onclick={handleOpen}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			handleOpen();
		}
	}}
>
	{#if !small}
		<div class="p-3 bg-black/20 dark:bg-white/10 text-white rounded-xl">
			{#if !loading}
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="currentColor"
					class=" size-5"
				>
					<path
						fill-rule="evenodd"
						d="M5.625 1.5c-1.036 0-1.875.84-1.875 1.875v17.25c0 1.035.84 1.875 1.875 1.875h12.75c1.035 0 1.875-.84 1.875-1.875V12.75A3.75 3.75 0 0 0 16.5 9h-1.875a1.875 1.875 0 0 1-1.875-1.875V5.25A3.75 3.75 0 0 0 9 1.5H5.625ZM7.5 15a.75.75 0 0 1 .75-.75h7.5a.75.75 0 0 1 0 1.5h-7.5A.75.75 0 0 1 7.5 15Zm.75 2.25a.75.75 0 0 0 0 1.5H12a.75.75 0 0 0 0-1.5H8.25Z"
						clip-rule="evenodd"
					/>
					<path
						d="M12.971 1.816A5.23 5.23 0 0 1 14.25 5.25v1.875c0 .207.168.375.375.375H16.5a5.23 5.23 0 0 1 3.434 1.279 9.768 9.768 0 0 0-6.963-6.963Z"
					/>
				</svg>
			{:else}
				<Spinner />
			{/if}
		</div>
	{/if}

	{#if !small}
		<div class="flex flex-col justify-center -space-y-0.5 px-2.5 w-full">
			<div class=" dark:text-gray-100 text-sm font-medium line-clamp-1 mb-1">
				{decodeURIComponent(name)}
			</div>

			<div class=" flex justify-between text-gray-500 text-xs line-clamp-1">
				{#if type === 'file'}
					{$i18n.t('File')}
				{:else if type === 'doc'}
					{$i18n.t('Document')}
				{:else if type === 'collection'}
					{$i18n.t('Collection')}
				{:else if type === 'knowledge'}
					{$i18n.t('Knowledge')}
				{:else}
					<span class=" capitalize line-clamp-1">{type}</span>
				{/if}
				{#if size}
					<span class="capitalize">{formatFileSize(size)}</span>
				{/if}
			</div>
		</div>
	{:else}
		<Tooltip
			content={decodeURIComponent(name)}
			className="flex flex-col w-full"
			placement="top-start"
		>
			<div class="flex flex-col justify-center -space-y-0.5 px-2.5 w-full">
				<div class=" dark:text-gray-100 text-sm flex justify-between items-center">
					{#if loading}
						<div class=" shrink-0 mr-2">
							<Spinner className="size-4" />
						</div>
					{/if}
					<div class="font-medium line-clamp-1 flex-1">{decodeURIComponent(name)}</div>
					<div class="text-gray-500 text-xs capitalize shrink-0">{formatFileSize(size)}</div>
				</div>
			</div>
		</Tooltip>
	{/if}

	{#if dismissible}
		<div class=" absolute -top-1 -right-1">
			<button
				class=" bg-white text-black border border-white rounded-full group-hover:visible invisible transition"
				type="button"
				aria-label={$i18n.t('Remove')}
				onclick={(e: MouseEvent) => {
					e.stopPropagation();
					onDismiss?.();
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-4 h-4"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>
	{/if}
</div>
