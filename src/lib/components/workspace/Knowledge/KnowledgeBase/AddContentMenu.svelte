<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArrowUpCircle from '$lib/components/icons/ArrowUpCircle.svelte';
	import BarsArrowUp from '$lib/components/icons/BarsArrowUp.svelte';
	import FolderOpen from '$lib/components/icons/FolderOpen.svelte';
	import ArrowPath from '$lib/components/icons/ArrowPath.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Callback when the dropdown closes */
		onClose?: () => void;
		/** Callback when an upload action is selected; receives { type: 'files' | 'directory' | 'text' } */
		onUpload?: (...args: unknown[]) => void;
		/** Callback when the sync directory action is selected */
		onSync?: (...args: unknown[]) => void;
	}

	let { onClose = () => {}, onUpload = () => {}, onSync = () => {} }: Props = $props();

	let show = $state(false);
</script>

<Dropdown
	bind:show
	onchange={(state: boolean) => {
		if ((state as unknown as CustomEvent).detail === false) {
			onClose();
		}
	}}
	align="end"
>
	<Tooltip content={$i18n.t('Add Content')}>
		<button
			class=" p-1.5 rounded-xl hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition font-medium text-sm flex items-center space-x-1"
			aria-label={$i18n.t('Add Content')}
			onclick={(e: MouseEvent) => {
				e.stopPropagation();
				show = true;
			}}
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 16 16"
				fill="currentColor"
				class="w-4 h-4"
			>
				<path
					d="M8.75 3.75a.75.75 0 0 0-1.5 0v3.5h-3.5a.75.75 0 0 0 0 1.5h3.5v3.5a.75.75 0 0 0 1.5 0v-3.5h3.5a.75.75 0 0 0 0-1.5h-3.5v-3.5Z"
				/>
			</svg>
		</button>
	</Tooltip>

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-44 rounded-xl p-1 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-sm"
					sideOffset={4}
					side="bottom"
					align="end"
				>
					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onUpload?.({ type: 'files' });
						}}
					>
						<ArrowUpCircle strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Upload files')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onUpload?.({ type: 'directory' });
						}}
					>
						<FolderOpen strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Upload directory')}</div>
					</DropdownMenu.Item>

					<Tooltip
						content={$i18n.t(
							'This option will delete all existing files in the collection and replace them with newly uploaded files.'
						)}
						className="w-full"
					>
						<DropdownMenu.Item
							class="flex  gap-2  items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
							onclick={() => {
								onSync?.({ type: 'directory' });
							}}
						>
							<ArrowPath strokeWidth="2" />
							<div class="flex items-center">{$i18n.t('Sync directory')}</div>
						</DropdownMenu.Item>
					</Tooltip>

					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onUpload?.({ type: 'text' });
						}}
					>
						<BarsArrowUp strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Add text content')}</div>
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
