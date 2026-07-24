<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Keyboard from '$lib/components/icons/Keyboard.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Callback invoked when documentation is requested */
		showDocsHandler: () => void;
		/** Callback invoked when keyboard shortcuts are requested */
		showShortcutsHandler: () => void;
		/** Callback invoked when the menu is closed */
		onClose?: () => void;
		/** Snippet for the trigger element */
		children?: import('svelte').Snippet;
	}

	let {
		showDocsHandler: _showDocsHandler,
		showShortcutsHandler,
		onClose = () => {},
		children
	}: Props = $props();
</script>

<Dropdown
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
					class="w-full max-w-[200px] rounded-xl px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					sideOffset={4}
					side="top"
					align="end"
				>
					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						id="chat-share-button"
						onclick={() => {
							window.open('https://github.com/bccard-ai/bcgpt-webui', '_blank');
						}}
					>
						<QuestionMarkCircle className="size-5" />
						<div class="flex items-center">{$i18n.t('Documentation')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						id="chat-share-button"
						onclick={() => {
							showShortcutsHandler();
						}}
					>
						<Keyboard className="size-5" />
						<div class="flex items-center">{$i18n.t('Keyboard shortcuts')}</div>
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
