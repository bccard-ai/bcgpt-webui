<script lang="ts">
	import { get } from 'svelte/store';

	import Fuse from 'fuse.js';

	import { DropdownMenu } from 'bits-ui';
	import { onMount, getContext } from 'svelte';
	import { knowledge, user } from '$lib/stores';
	import { getVectorDBCollections } from '$lib/apis/retrieval';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Callback when the dropdown closes */
		onClose?: () => void;
		/** Callback when a knowledge item is selected */
		onSelect?: (item: unknown) => void;
		/** Trigger element rendered inside the dropdown toggle */
		children?: import('svelte').Snippet;
	}

	let { onClose = () => {}, onSelect = () => {}, children }: Props = $props();

	let query = $state('');

	let items = $state([]);
	let filteredItems = $state([]);

	let fuse = $state(null);

	$effect(() => {
		if (fuse) {
			filteredItems = query
				? fuse.search(query).map((e: { item: unknown }) => {
						return e.item;
					})
				: items;
		}
	});

	onMount(async () => {
		let legacy_documents = get(knowledge).filter((item) => item?.meta?.document);
		let legacy_collections =
			legacy_documents.length > 0
				? [
						{
							name: 'All Documents',
							legacy: true,
							type: 'collection',
							description: 'Deprecated (legacy collection), please create a new knowledge base.',

							title: $i18n.t('All Documents'),
							collection_names: legacy_documents.map((item) => item.id)
						},

						...legacy_documents
							.reduce((a, item) => {
								return [...new Set([...a, ...(item?.meta?.tags ?? []).map((tag) => tag.name)])];
							}, [])
							.map((tag) => ({
								name: tag,
								legacy: true,
								type: 'collection',
								description: 'Deprecated (legacy collection), please create a new knowledge base.',

								collection_names: legacy_documents
									.filter((item) => (item?.meta?.tags ?? []).map((tag) => tag.name).includes(tag))
									.map((item) => item.id)
							}))
					]
				: [];

		const kbItems = [...get(knowledge), ...legacy_collections].map((item) => {
			const isLegacy = item?.legacy || item?.meta?.legacy || item?.meta?.document;
			return {
				...item,
				...(isLegacy ? { legacy: true } : {}),
				type: item?.meta?.document ? 'document' : 'collection',
				...(isLegacy ? {} : { source: 'knowledge' })
			};
		});

		let collectionItems: Record<string, unknown>[] = [];
		if (get(user)?.role === 'admin') {
			try {
				const kbIds = new Set(get(knowledge).map((k) => (k as unknown as { id: string }).id));
				const collections = (await getVectorDBCollections('')) ?? [];
				collectionItems = collections
					.filter((c) => !kbIds.has(c.name) && !c.name.startsWith('file-'))
					.map((c) => ({
						id: c.name,
						name: c.name,
						type: 'collection',
						source: 'collection',
						description: $i18n.t('{{count}} documents', { count: c.document_count ?? 0 }),
						document_count: c.document_count ?? 0
					}));
			} catch (_e) {
				// Collections are optional — never block knowledge-base selection on this.
			}
		}

		items = [...kbItems, ...collectionItems];

		fuse = new Fuse(items, {
			keys: ['name', 'description']
		});
	});
</script>

<Dropdown
	onchange={(state: boolean) => {
		if (state === false) {
			onClose();
			query = '';
		}
	}}
>
	{@render children?.()}

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-80 rounded-lg px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					sideOffset={8}
					side="bottom"
					align="start"
				>
					<div class=" flex w-full space-x-2 py-0.5 px-2">
						<div class="flex flex-1">
							<div class=" self-center ml-1 mr-3">
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-4 h-4"
								>
									<path
										fill-rule="evenodd"
										d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
										clip-rule="evenodd"
									/>
								</svg>
							</div>
							<input
								class=" w-full text-sm pr-4 py-1 rounded-r-xl outline-hidden bg-transparent"
								bind:value={query}
								placeholder={$i18n.t('Search Knowledge')}
							/>
						</div>
					</div>

					<hr class=" border-gray-50 dark:border-gray-700 my-1.5" />

					<div class="max-h-48 overflow-y-scroll">
						{#if filteredItems.length === 0}
							<div class="text-center text-sm text-gray-500 dark:text-gray-400">
								{$i18n.t('No knowledge found')}
							</div>
						{:else}
							{#each filteredItems as item, i (i)}
								<DropdownMenu.Item
									class="flex gap-2.5 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
									onclick={() => {
										onSelect?.(item);
									}}
								>
									<div class="flex items-center">
										<div class="flex flex-col">
											<div class=" w-fit mb-0.5">
												{#if item.legacy}
													<div
														class="bg-gray-500/20 text-gray-700 dark:text-gray-200 rounded-sm uppercase text-xs font-bold px-1"
													>
														{$i18n.t('Legacy')}
													</div>
												{:else if item?.meta?.document}
													<div
														class="bg-gray-500/20 text-gray-700 dark:text-gray-200 rounded-sm uppercase text-xs font-bold px-1"
													>
														{$i18n.t('Document')}
													</div>
												{:else if item?.source === 'collection'}
													<div
														class="bg-blue-500/20 text-blue-700 dark:text-blue-200 rounded-sm uppercase text-xs font-bold px-1"
													>
														{$i18n.t('Vector DB')}
													</div>
												{:else if item?.source === 'knowledge'}
													<div
														class="bg-green-500/20 text-green-700 dark:text-green-200 rounded-sm uppercase text-xs font-bold px-1"
													>
														{$i18n.t('Knowledge')}
													</div>
												{:else}
													<div
														class="bg-green-500/20 text-green-700 dark:text-green-200 rounded-sm uppercase text-xs font-bold px-1"
													>
														{$i18n.t('Collection')}
													</div>
												{/if}
											</div>

											<div class="line-clamp-1 font-medium pr-0.5">
												{item.name}
											</div>
										</div>
									</div>
								</DropdownMenu.Item>
							{/each}
						{/if}
					</div>
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
