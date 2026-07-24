<script lang="ts">
	/**
	 * Feedback Dropdown Menu
	 *
	 * Single-action context menu for a feedback entry (delete only).
	 */
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	interface Props {
		children?: import('svelte').Snippet;

		onDelete?: (...args: unknown[]) => void;
	}

	let { children, onDelete = () => {} }: Props = $props();

	let show = $state(false);
</script>

<Dropdown bind:show onchange={(_state: boolean) => {}}>
	<Tooltip content={$i18n.t('More')}>
		{@render children?.()}
	</Tooltip>

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-[150px] rounded-xl px-1 py-1.5 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					sideOffset={-2}
					side="bottom"
					align="start"
				>
					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							onDelete?.();
							show = false;
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
