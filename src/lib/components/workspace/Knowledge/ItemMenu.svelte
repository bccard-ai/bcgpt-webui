<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Callback when the dropdown closes */
		onClose?: () => void;
		/** Callback when the user clicks "Delete" */
		onDelete?: () => void;
		/** Optional custom trigger element */
		children?: import('svelte').Snippet;
	}

	let { onClose = () => {}, onDelete, children }: Props = $props();

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
	<Tooltip content={$i18n.t('More')}>
		{#if children}{@render children()}{:else}<button
				class="self-center w-fit text-sm p-1.5 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
				type="button"
				onclick={(e: MouseEvent) => {
					e.stopPropagation();
					show = true;
				}}
			>
				<EllipsisHorizontal className="size-5" />
			</button>
		{/if}
	</Tooltip>

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-[160px] rounded-xl px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-sm"
					sideOffset={-2}
					side="bottom"
					align="end"
				>
					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
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
