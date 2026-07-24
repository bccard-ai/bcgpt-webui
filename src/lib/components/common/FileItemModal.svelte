<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { formatFileSize, getLineCount } from '$lib/utils';
	import { API_BASE_URL } from '$lib/constants';

	import Modal from './Modal.svelte';
	import XMark from '../icons/XMark.svelte';
	import Info from '../icons/Info.svelte';
	import Switch from './Switch.svelte';
	import Tooltip from './Tooltip.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * FileItemModal — detail modal for viewing file content, metadata, and retrieval settings.
	 *
	 * @example
	 * ```svelte
	 * <FileItemModal bind:show item={fileObject} edit={true} />
	 * ```
	 *
	 * @props show - Bindable visibility
	 * @props item - File item object with metadata
	 * @props edit - Enable full-content vs focused-retrieval toggle
	 */
	interface FileItem {
		id?: string;
		name?: string;
		url?: string;
		type?: string;
		size?: number;
		context?: string;
		meta?: { content_type?: string };
		file?: { data?: { content?: string } };
	}

	interface Props {
		/** File item to display. */
		item: FileItem;
		/** Bindable visibility. */
		show?: boolean;
		/** Enable full-content vs focused-retrieval toggle. */
		edit?: boolean;
	}

	let { item, show = $bindable(false), edit = false }: Props = $props();

	let enableFullContent = $state(false);
	let isPDF = $derived(
		item?.meta?.content_type === 'application/pdf' ||
			(item?.name && item?.name.toLowerCase().endsWith('.pdf'))
	);

	onMount(() => {
		if (item?.context === 'full') {
			enableFullContent = true;
		}
	});
</script>

<Modal bind:show size="lg">
	<div class="font-primary px-6 py-5 w-full flex flex-col justify-center dark:text-gray-400">
		<div class=" pb-2">
			<div class="flex items-start justify-between">
				<div>
					<div class=" font-medium text-lg dark:text-gray-100">
						<button
							type="button"
							class="hover:underline line-clamp-1 text-left"
							onclick={() => {
								if (!isPDF && item.url) {
									window.open(
										item.type === 'file' ? `${item.url}/content` : `${item.url}`,
										'_blank'
									);
								}
							}}
						>
							{item?.name ?? $i18n.t('File')}
						</button>
					</div>
				</div>

				<div>
					<button
						onclick={() => {
							show = false;
						}}
					>
						<XMark />
					</button>
				</div>
			</div>

			<div>
				<div class="flex flex-col items-center md:flex-row gap-1 justify-between w-full">
					<div class=" flex flex-wrap text-sm gap-1 text-gray-500">
						{#if item.size}
							<div class="capitalize shrink-0">{formatFileSize(item.size)}</div>
							•
						{/if}

						{#if item?.file?.data?.content}
							<div class="capitalize shrink-0">
								{$i18n.t('{{count}} extracted lines', {
									count: getLineCount(item?.file?.data?.content ?? '')
								})}
							</div>

							<div class="flex items-center gap-1 shrink-0">
								<Info />

								{$i18n.t('Formatting may be inconsistent from source.')}
							</div>
						{/if}
					</div>

					{#if edit}
						<div>
							<Tooltip
								content={enableFullContent
									? $i18n.t(
											'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
										)
									: $i18n.t(
											'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
										)}
							>
								<div class="flex items-center gap-1.5 text-xs">
									{#if enableFullContent}
										{$i18n.t('Using Entire Document')}
									{:else}
										{$i18n.t('Using Focused Retrieval')}
									{/if}
									<Switch
										bind:state={enableFullContent}
										onchange={(e: CustomEvent) => {
											item.context = e.detail ? 'full' : undefined;
										}}
									/>
								</div>
							</Tooltip>
						</div>
					{/if}
				</div>
			</div>
		</div>

		<div class="max-h-[75vh] overflow-auto">
			{#if isPDF}
				<iframe
					title={item?.name}
					src={`${API_BASE_URL}/files/${item.id}/content`}
					class="w-full h-[70vh] border-0 rounded-lg mt-4"
					sandbox="allow-scripts"
				></iframe>
			{:else}
				<div class="max-h-96 overflow-scroll scrollbar-hidden text-xs whitespace-pre-wrap">
					{item?.file?.data?.content ?? $i18n.t('No content')}
				</div>
			{/if}
		</div>
	</div>
</Modal>
