<script lang="ts">
	/**
	 * Manage Models Modal
	 *
	 * Modal wrapper for model management interfaces. Currently supports
	 * Ollama model management (pull, delete, list). Auto-selects the
	 * first available inference engine on mount.
	 */
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { get } from 'svelte/store';

	import { getContext, onMount } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');
	import { user } from '$lib/stores';

	import Modal from '$lib/components/common/Modal.svelte';
	import { getOllamaConfig } from '$lib/apis/ollama';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ManageMultipleOllama from './Manage/ManageMultipleOllama.svelte';

	interface Props {
		/** Controls modal visibility (two-way bindable) */
		show?: boolean;
	}

	let { show = $bindable(false) }: Props = $props();

	/** Currently selected management engine tab (e.g. 'ollama') */
	let selected = $state(null);
	/** Ollama configuration fetched on mount */
	let ollamaConfig = $state(null);

	onMount(async () => {
		if (get(user).role === 'admin') {
			ollamaConfig = await getOllamaConfig('');

			if (ollamaConfig) {
				selected = 'ollama';
				return;
			}

			selected = '';
		}
	});
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-100 px-5 pt-4">
			<div class=" text-lg font-medium self-center font-primary">
				{$i18n.t('Manage Models')}
			</div>
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

		<div class="flex flex-col md:flex-row w-full px-3 pb-4 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				{#if selected === ''}
					<div class=" py-5 text-gray-400 text-xs">
						<div>
							{$i18n.t('No inference engine with management support found')}
						</div>
					</div>
				{:else if selected !== null}
					<div class=" flex w-full flex-col">
						<div
							class="flex gap-1 scrollbar-none overflow-x-auto w-fit text-center text-sm font-medium rounded-full bg-transparent dark:text-gray-200"
						>
							<button
								class="min-w-fit rounded-full p-1.5 {selected === 'ollama'
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								onclick={() => {
									selected = 'ollama';
								}}>{$i18n.t('Ollama')}</button
							>

							<!-- <button
								class="min-w-fit rounded-full p-1.5 {selected === 'llamacpp'
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								onclick={() => {
									selected = 'llamacpp';
								}}>{$i18n.t('Llama.cpp')}</button
							> -->
						</div>

						<div class=" px-1.5 py-1">
							{#if selected === 'ollama'}
								<ManageMultipleOllama {ollamaConfig} />
							{/if}
						</div>
					</div>
				{:else}
					<div class=" py-5">
						<Spinner />
					</div>
				{/if}
			</div>
		</div>
	</div>
</Modal>
