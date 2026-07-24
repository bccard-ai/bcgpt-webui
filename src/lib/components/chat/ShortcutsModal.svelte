<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '../common/Modal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Controls modal visibility */
		show?: boolean;
	}

	let { show = $bindable(false) }: Props = $props();
</script>

<Modal bind:show>
	<div class="text-gray-700 dark:text-gray-100">
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4">
			<div class=" text-lg font-medium self-center">{$i18n.t('Keyboard shortcuts')}</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				onclick={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full p-5 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<div class="flex flex-col space-y-3 w-full self-start">
					{#each [{ label: $i18n.t('Open new chat'), keys: ['Ctrl/⌘', 'Shift', 'O'] }, { label: $i18n.t('Focus chat input'), keys: ['Shift', 'Esc'] }, { label: $i18n.t('Copy last code block'), keys: ['Ctrl/⌘', 'Shift', ';'] }, { label: $i18n.t('Copy last response'), keys: ['Ctrl/⌘', 'Shift', 'C'] }, { label: $i18n.t('Generate prompt pair'), keys: ['Ctrl/⌘', 'Shift', 'Enter'] }] as shortcut (shortcut.label)}
						<div class="w-full flex justify-between items-center">
							<div class=" text-sm">{shortcut.label}</div>
							<div class="flex space-x-1 text-xs">
								{#each shortcut.keys as key (key)}
									<div
										class=" h-fit py-1 px-2 flex items-center justify-center rounded-sm border border-black/10 capitalize text-gray-600 dark:border-white/10 dark:text-gray-300"
									>
										{key}
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>

				<div class="flex flex-col space-y-3 w-full self-start">
					{#each [{ label: $i18n.t('Toggle settings'), keys: ['Ctrl/⌘', '.'] }, { label: $i18n.t('Toggle sidebar'), keys: ['Ctrl/⌘', 'Shift', 'S'] }, { label: $i18n.t('Delete chat'), keys: ['Ctrl/⌘', 'Shift', '⌫/Delete'] }, { label: $i18n.t('Show shortcuts'), keys: ['Ctrl/⌘', '/'] }] as shortcut (shortcut.label)}
						<div class="w-full flex justify-between items-center">
							<div class=" text-sm">{shortcut.label}</div>
							<div class="flex space-x-1 text-xs">
								{#each shortcut.keys as key (key)}
									<div
										class=" h-fit py-1 px-2 flex items-center justify-center rounded-sm border border-black/10 capitalize text-gray-600 dark:border-white/10 dark:text-gray-300"
									>
										{key}
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<div class=" flex justify-between dark:text-gray-300 px-5">
			<div class=" text-lg font-medium self-center">{$i18n.t('Input commands')}</div>
		</div>

		<div class="flex flex-col md:flex-row w-full p-5 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<div class="flex flex-col space-y-3 w-full self-start">
					{#each [{ label: $i18n.t('Attach file from knowledge'), key: '#' }, { label: $i18n.t('Add custom prompt'), key: '/' }, { label: $i18n.t('Talk to model'), key: '@' }, { label: $i18n.t('Accept autocomplete generation / Jump to prompt variable'), key: 'TAB' }] as command (command.label)}
						<div class="w-full flex justify-between items-center">
							<div class=" text-sm">{command.label}</div>
							<div class="flex space-x-1 text-xs">
								<div
									class=" h-fit py-1 px-2 flex items-center justify-center rounded-sm border border-black/10 capitalize text-gray-600 dark:border-white/10 dark:text-gray-300"
								>
									{command.key}
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</Modal>

<style>
	:global(input::-webkit-outer-spin-button),
	:global(input::-webkit-inner-spin-button) {
		-webkit-appearance: none;
		margin: 0;
	}

	:global(.tabs::-webkit-scrollbar) {
		display: none;
	}

	:global(.tabs) {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}

	:global(input[type='number']) {
		-moz-appearance: textfield;
		appearance: textfield;
	}
</style>
