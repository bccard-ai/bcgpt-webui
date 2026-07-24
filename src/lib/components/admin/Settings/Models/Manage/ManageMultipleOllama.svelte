<script lang="ts">
	/**
	 * Manage Multiple Ollama Instances
	 *
	 * Wrapper that provides a URL selector dropdown for multi-instance Ollama
	 * setups, then delegates to ManageOllama for the selected instance index.
	 */
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import ManageOllama from './ManageOllama.svelte';

	interface Props {
		/** Ollama config containing OLLAMA_BASE_URLS array */
		ollamaConfig?: { OLLAMA_BASE_URLS?: string[]; [key: string]: unknown } | null;
	}

	let { ollamaConfig = null }: Props = $props();

	/** Currently selected Ollama instance index */
	let selectedUrlIdx = $state(0);
</script>

{#if ollamaConfig}
	<div class="flex-1 mb-2.5 pr-1.5 rounded-lg bg-gray-50 dark:text-gray-300 dark:bg-gray-850">
		<select
			class="w-full py-1.5 px-3 text-xs outline-hidden bg-transparent"
			bind:value={selectedUrlIdx}
			placeholder={$i18n.t('Select an Ollama instance')}
		>
			{#each ollamaConfig.OLLAMA_BASE_URLS as url, idx (idx)}
				<option value={idx}>{url}</option>
			{/each}
		</select>
	</div>

	<ManageOllama urlIdx={selectedUrlIdx} />
{/if}
