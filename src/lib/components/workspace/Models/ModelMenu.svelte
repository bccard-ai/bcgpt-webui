<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Share from '$lib/components/icons/Share.svelte';
	import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';

	import { config } from '$lib/stores';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Current user object for permission checks */
		user: unknown;
		/** The model/agent this menu operates on */
		model: unknown;
		/** Callback when the user clicks "Share" */
		shareHandler: () => void;
		/** Callback when the user clicks "Clone" */
		cloneHandler: () => void;
		/** Callback when the user clicks "Export" */
		exportHandler: () => void;
		/** Callback when the user clicks "Hide/Show" */
		hideHandler: () => void;
		/** Callback when the user clicks "Delete" */
		deleteHandler: () => void;
		/** Callback when the dropdown closes */
		onClose: () => void;
		/** Trigger element rendered inside the dropdown toggle */
		children?: import('svelte').Snippet;
	}

	let {
		user: _user,
		model: _model,
		shareHandler,
		cloneHandler,
		exportHandler,
		hideHandler: _hideHandler,
		deleteHandler,
		onClose,
		children
	}: Props = $props();

	let show = $state(false);
</script>

<Dropdown
	bind:show
	onchange={(state: boolean) => {
		if ((state as unknown as CustomEvent).detail === false) {
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
					class="w-full max-w-[160px] rounded-xl px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-sm"
					sideOffset={-2}
					side="bottom"
					align="start"
				>
					{#if $config?.features.enable_community_sharing}
						<DropdownMenu.Item
							class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800  rounded-md"
							onclick={() => {
								shareHandler();
							}}
						>
							<Share />
							<div class="flex items-center">{$i18n.t('Share')}</div>
						</DropdownMenu.Item>
					{/if}

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							cloneHandler();
						}}
					>
						<DocumentDuplicate />

						<div class="flex items-center">{$i18n.t('Clone')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							exportHandler();
						}}
					>
						<ArrowDownTray />

						<div class="flex items-center">{$i18n.t('Export')}</div>
					</DropdownMenu.Item>

					<hr class="border-gray-100 dark:border-gray-850 my-1" />

					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							deleteHandler();
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
