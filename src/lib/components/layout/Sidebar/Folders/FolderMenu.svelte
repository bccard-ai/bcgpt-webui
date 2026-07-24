<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Snippet for the trigger element */
		children?: import('svelte').Snippet;
		/** Callback invoked when the menu is closed */
		onClose?: (...args: unknown[]) => void;
		/** Callback invoked when rename is requested */
		onRename?: (...args: unknown[]) => void;
		/** Callback invoked when export is requested */
		onExport?: (...args: unknown[]) => void;
		/** Callback invoked when delete is requested */
		onDelete?: (...args: unknown[]) => void;
	}

	let {
		children,
		onClose = () => {},
		onRename = () => {},
		onExport = () => {},
		onDelete = () => {}
	}: Props = $props();

	let show = $state(false);
</script>

<Dropdown
	bind:show
	onchange={(state: boolean) => {
		if ((state as unknown as CustomEvent).detail === false) {
			onClose?.();
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
					class="w-full max-w-[160px] rounded-lg px-1 py-1.5  z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					sideOffset={-2}
					side="bottom"
					align="start"
				>
					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onRename?.();
						}}
					>
						<Pencil strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Rename')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onExport?.();
						}}
					>
						<Download strokeWidth="2" />

						<div class="flex items-center">{$i18n.t('Export')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onDelete?.();
						}}
					>
						<GarbageBin strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Delete')}</div>
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
