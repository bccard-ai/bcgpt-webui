<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Dropdown — wrapper around bits-ui DropdownMenu with trigger + content slots.
	 *
	 * @example
	 * ```svelte
	 * <Dropdown bind:show side="bottom" align="start">
	 *   {#snippet children()}
	 *     <button>Open</button>
	 *   {/snippet}
	 *   {#snippet content()}
	 *     <DropdownMenu.Item>Item 1</DropdownMenu.Item>
	 *   {/snippet}
	 * </Dropdown>
	 * ```
	 *
	 * @props show - Bindable open state
	 * @props side - Popup side: 'top' | 'bottom' | 'left' | 'right'
	 * @props align - Popup alignment: 'start' | 'center' | 'end'
	 */
	interface Props {
		/** Bindable open state. */
		show?: boolean;
		/** Side the dropdown appears on. Defaults to `'bottom'`. */
		side?: string;
		/** Alignment of the dropdown. Defaults to `'start'`. */
		align?: string;
		/** Trigger element snippet. */
		children?: import('svelte').Snippet;
		/** Dropdown content snippet. Falls back to a placeholder menu. */
		content?: import('svelte').Snippet;
		/** Called when the dropdown open state changes. */
		onchange?: (state: boolean) => void;
	}

	let {
		show = $bindable(false),
		side = 'bottom',
		align = 'start',
		children,
		content,
		onchange = () => {}
	}: Props = $props();
</script>

<DropdownMenu.Root
	bind:open={show}
	closeFocus={false}
	onOpenChange={(state) => {
		onchange?.(state);
	}}
	typeahead={false}
>
	<DropdownMenu.Trigger>
		{@render children?.()}
	</DropdownMenu.Trigger>

	{#if content}{@render content()}{:else}
		<DropdownMenu.Portal>
			<DropdownMenu.Content
				class="w-full max-w-[130px] rounded-lg px-1 py-1.5 border border-gray-900 z-50 bg-gray-850 text-white"
				sideOffset={8}
				{side}
				{align}
			>
				<DropdownMenu.Item class="flex items-center px-3 py-2 text-sm  font-medium">
					<div class="flex items-center">{$i18n.t('Profile')}</div>
				</DropdownMenu.Item>

				<DropdownMenu.Item class="flex items-center px-3 py-2 text-sm  font-medium">
					<div class="flex items-center">{$i18n.t('Profile')}</div>
				</DropdownMenu.Item>

				<DropdownMenu.Item class="flex items-center px-3 py-2 text-sm  font-medium">
					<div class="flex items-center">{$i18n.t('Profile')}</div>
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Portal>
	{/if}
</DropdownMenu.Root>
