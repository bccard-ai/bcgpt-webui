<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	import { mobile } from '$lib/stores';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import DocumentArrowUpSolid from '$lib/components/icons/DocumentArrowUpSolid.svelte';
	import CameraSolid from '$lib/components/icons/CameraSolid.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Dropdown menu for the message input, providing options for
	 * screen capture and file uploads.
	 *
	 * @example
	 * ```svelte
	 * <InputMenu
	 *   screenCaptureHandler={captureScreen}
	 *   uploadFilesHandler={openFileDialog}
	 *   onClose={() => {}}
	 * >
	 *   <button>+</button>
	 * </InputMenu>
	 * ```
	 *
	 * @param screenCaptureHandler - Callback to initiate a screen capture.
	 * @param uploadFilesHandler - Callback to open the file upload dialog.
	 * @param onClose - Callback when the dropdown is closed.
	 * @param children - Snippet for the trigger element.
	 */
	interface Props {
		screenCaptureHandler: () => void;
		uploadFilesHandler: () => void;
		onClose?: () => void;
		children?: import('svelte').Snippet;
	}

	let { screenCaptureHandler, uploadFilesHandler, onClose = () => {}, children }: Props = $props();

	let show = $state(false);

	$effect(() => {
		if (show) {
			// Initialize menu state if needed
		}
	});
</script>

<Dropdown
	bind:show
	onchange={(state: boolean) => {
		if (state === false) {
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('More')}>
		{@render children?.()}
	</Tooltip>

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-[200px] rounded-xl px-1 py-1  border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-sm"
					sideOffset={15}
					alignOffset={-8}
					side="top"
					align="start"
				>
					{#if !$mobile}
						<DropdownMenu.Item
							class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800  rounded-xl"
							onclick={() => {
								screenCaptureHandler();
							}}
						>
							<CameraSolid />
							<div class=" line-clamp-1">{$i18n.t('Capture')}</div>
						</DropdownMenu.Item>
					{/if}

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl"
						onclick={() => {
							uploadFilesHandler();
						}}
					>
						<DocumentArrowUpSolid />
						<div class="line-clamp-1">{$i18n.t('Upload Files')}</div>
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
