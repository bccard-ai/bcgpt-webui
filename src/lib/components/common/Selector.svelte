<script lang="ts">
	import { Select } from 'bits-ui';
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import ChevronDown from '../icons/ChevronDown.svelte';
	import Check from '../icons/Check.svelte';
	import Search from '../icons/Search.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Selector — searchable single-select dropdown built on bits-ui Select.
	 *
	 * @example
	 * ```svelte
	 * <Selector
	 *   bind:value
	 *   items={[{ value: 'a', label: 'Alpha' }]}
	 *   placeholder="Pick one"
	 * />
	 * ```
	 *
	 * @props value - Bindable selected value
	 * @props placeholder - Trigger placeholder text
	 * @props searchEnabled - Whether to show the search filter
	 * @props searchPlaceholder - Search input placeholder
	 * @props items - List of { value, label } options
	 * @props size - 'default' or 'sm'
	 */
	interface Props {
		/** Bindable selected value. */
		value?: string;
		/** Placeholder text shown on the trigger. */
		placeholder?: string;
		/** Whether to show the search input. Defaults to `true`. */
		searchEnabled?: boolean;
		/** Placeholder text for the search input. */
		searchPlaceholder?: string;
		/** List of selectable items. */
		items?: { value: string; label: string }[];
		/** Size variant: `'default'` or `'sm'`. */
		size?: 'default' | 'sm';
		/** Custom content snippet (replaces default item list). */
		children?: import('svelte').Snippet;
	}

	let {
		value = $bindable(''),
		placeholder = $i18n.t('Select a model'),
		searchEnabled = true,
		searchPlaceholder = $i18n.t('Search a model'),
		items = [
			{ value: 'mango', label: 'Mango' },
			{ value: 'watermelon', label: 'Watermelon' },
			{ value: 'apple', label: 'Apple' },
			{ value: 'pineapple', label: 'Pineapple' },
			{ value: 'orange', label: 'Orange' }
		],
		size = 'default',
		children
	}: Props = $props();

	let searchValue = $state('');

	let filteredItems = $derived(
		searchValue
			? items.filter((item) => item.value.toLowerCase().includes(searchValue.toLowerCase()))
			: items
	);
</script>

<Select.Root
	type="single"
	{items}
	onOpenChange={() => {
		searchValue = '';
	}}
	{value}
	onValueChange={(v) => {
		value = v;
	}}
>
	<Select.Trigger class="relative w-full" aria-label={placeholder}>
		<Select.Value
			class="inline-flex items-center {size === 'sm'
				? 'h-8'
				: 'h-input'} px-3 w-full outline-hidden bg-transparent truncate {size === 'sm'
				? 'text-xs'
				: 'text-lg'} {size === 'sm'
				? 'font-medium'
				: 'font-semibold'} placeholder-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-hidden focus:border-gray-300 dark:focus:border-gray-600 transition-colors"
			{placeholder}
		/>
		<ChevronDown
			className="absolute end-2 top-1/2 -translate-y-[45%] {size === 'sm' ? 'size-3' : 'size-3.5'}"
			strokeWidth="2.5"
		/>
	</Select.Trigger>
	<Select.Portal>
		<Select.Content
			class="w-full rounded-lg  bg-white dark:bg-gray-900 dark:text-white shadow-lg border border-gray-300/30 dark:border-gray-700/40  outline-hidden"
			sideOffset={4}
		>
			{#if children}{@render children()}{:else}
				{#if searchEnabled}
					<div class="flex items-center gap-2.5 px-5 mt-3.5 mb-3">
						<Search className="size-4" strokeWidth="2.5" />

						<input
							bind:value={searchValue}
							class="w-full text-sm bg-transparent outline-hidden"
							placeholder={searchPlaceholder}
						/>
					</div>

					<hr class="border-gray-100 dark:border-gray-850" />
				{/if}

				<div class="px-3 my-2 max-h-80 overflow-y-auto">
					{#each filteredItems as item (item.value)}
						<Select.Item
							class="flex w-full font-medium line-clamp-1 select-none items-center rounded-button {size ===
							'sm'
								? 'py-1.5 pl-3 pr-1.5 text-xs'
								: 'py-2 pl-3 pr-1.5 text-sm'}  text-gray-700 dark:text-gray-100  outline-hidden transition-all duration-75 hover:bg-gray-100 dark:hover:bg-gray-850 rounded-lg cursor-pointer data-highlighted:bg-muted"
							value={item.value}
							label={item.label}
						>
							{item.label}

							{#if value === item.value}
								<div class="ml-auto">
									<Check />
								</div>
							{/if}
						</Select.Item>
					{:else}
						<div>
							<div class="block px-5 py-2 text-sm text-gray-700 dark:text-gray-100">
								{$i18n.t('No results found')}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</Select.Content>
	</Select.Portal>
</Select.Root>
