<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	const _i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		onClose?: () => void;
		devices: MediaDeviceInfo[];
		children?: import('svelte').Snippet;
		onchange?: (...args: unknown[]) => void;
	}

	let { onClose = () => {}, devices, children, onchange }: Props = $props();

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
	{@render children?.()}

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-[180px] rounded-lg px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-9999 bg-white dark:bg-gray-900 dark:text-white shadow-xs"
					sideOffset={6}
					side="top"
					align="start"
				>
					{#each devices as device (device.deviceId)}
						<DropdownMenu.Item
							class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
							onclick={() => {
								onchange?.(device.deviceId);
							}}
						>
							<div class="flex items-center">
								<div class=" line-clamp-1">
									{device?.label ?? 'Camera'}
								</div>
							</div>
						</DropdownMenu.Item>
					{/each}
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
