<script lang="ts">
	import Fuse from 'fuse.js';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import { getContext } from 'svelte';
	import { APP_NAME_STORE } from '$lib/stores';
	import { APP_VERSION } from '$lib/constants';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/** A single suggestion prompt with optional display structure */
	interface Prompt {
		id?: string;
		content: string;
		title?: string[];
	}

	interface Props {
		/** Pool of suggestion prompts to display and filter */
		suggestionPrompts?: Prompt[];
		/** Additional CSS class names for the container */
		className?: string;
		/** Current input value used for fuzzy filtering suggestions */
		inputValue?: string;
		/** Callback when a suggestion is selected */
		onSelect?: (content: string) => void;
	}

	let {
		suggestionPrompts = [],
		className = '',
		inputValue = '',
		onSelect = () => {}
	}: Props = $props();

	/** Randomly shuffled prompts, re-shuffled only when the source list changes */
	let sortedPrompts: Prompt[] = $state([]);

	/** Fuse.js instance for fuzzy search over sorted prompts */
	const fuseOptions = { keys: ['content', 'title'], threshold: 0.5 };
	let fuse = $derived(new Fuse(sortedPrompts, fuseOptions));

	/** Prompts filtered by the current input value */
	let filteredPrompts: Prompt[] = $state([]);

	/**
	 * Compare two prompt arrays by identity (id or content).
	 * Used to avoid unnecessary re-renders when the filtered list hasn't actually changed.
	 */
	const arePromptArraysEqual = (a: Prompt[], b: Prompt[]): boolean => {
		if (a.length !== b.length) return false;
		return a.every((item, i) => (item.id ?? item.content) === (b[i].id ?? b[i].content));
	};

	/**
	 * Filter the sorted prompts using Fuse.js fuzzy search.
	 * Skips filtering when input exceeds 500 characters to avoid performance issues.
	 */
	const updateFilteredPrompts = (currentInput: string): void => {
		if (currentInput.length > 500) {
			filteredPrompts = [];
			return;
		}

		const newFiltered =
			currentInput.trim() && fuse
				? fuse.search(currentInput.trim()).map((result) => result.item)
				: sortedPrompts;

		if (!arePromptArraysEqual(filteredPrompts, newFiltered)) {
			filteredPrompts = newFiltered;
		}
	};

	/** Re-shuffle prompts only when the suggestion list source changes */
	$effect(() => {
		if (suggestionPrompts) {
			sortedPrompts = [...(suggestionPrompts ?? [])].sort(() => Math.random() - 0.5);
		}
	});

	/** Update filtered prompts when input value changes */
	$effect(() => {
		updateFilteredPrompts(inputValue);
	});
</script>

<div class="mb-1 flex gap-1 text-xs font-medium items-center text-gray-400 dark:text-gray-600">
	{#if filteredPrompts.length > 0}
		<Bolt />
		{$i18n.t('Suggested')}
	{:else}
		<div
			class="flex w-full text-center items-center justify-center self-start text-gray-400 dark:text-gray-600"
		>
			{$APP_NAME_STORE} ‧ v{APP_VERSION}
		</div>
	{/if}
</div>

<div class="h-40 overflow-auto scrollbar-none {className} items-start">
	{#if filteredPrompts.length > 0}
		{#each filteredPrompts as prompt, idx (prompt.id || prompt.content)}
			<button
				class="waterfall flex flex-col flex-1 shrink-0 w-full justify-between
				       px-3 py-2 rounded-xl bg-transparent hover:bg-black/5
				       dark:hover:bg-white/5 transition group"
				style="animation-delay: {idx * 60}ms"
				onclick={() => onSelect?.(prompt.content)}
			>
				<div class="flex flex-col text-left">
					{#if prompt.title && prompt.title[0] !== ''}
						<div
							class="font-medium dark:text-gray-300 dark:group-hover:text-gray-200 transition line-clamp-1"
						>
							{prompt.title[0]}
						</div>
						<div class="text-xs text-gray-500 font-normal line-clamp-1">
							{prompt.title[1]}
						</div>
					{:else}
						<div
							class="font-medium dark:text-gray-300 dark:group-hover:text-gray-200 transition line-clamp-1"
						>
							{prompt.content}
						</div>
						<div class="text-xs text-gray-500 font-normal line-clamp-1">{$i18n.t('Prompt')}</div>
					{/if}
				</div>
			</button>
		{/each}
	{/if}
</div>

<style>
	/* Waterfall stagger animation for suggestion buttons */
	@keyframes fadeInUp {
		0% {
			opacity: 0;
			transform: translateY(20px);
		}
		100% {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.waterfall {
		opacity: 0;
		animation-name: fadeInUp;
		animation-duration: 200ms;
		animation-fill-mode: forwards;
		animation-timing-function: ease;
	}
</style>
