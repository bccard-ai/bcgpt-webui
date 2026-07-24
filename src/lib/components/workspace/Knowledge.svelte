<script lang="ts">
	import Fuse from 'fuse.js';

	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	dayjs.extend(relativeTime);

	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { APP_NAME_STORE, knowledge } from '$lib/stores';
	import {
		getKnowledgeBases,
		deleteKnowledgeById,
		getKnowledgeBaseList
	} from '$lib/apis/knowledge';

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import DeleteConfirmDialog from '../common/ConfirmDialog.svelte';
	import ItemMenu from './Knowledge/ItemMenu.svelte';
	import Badge from '../common/Badge.svelte';
	import Search from '../icons/Search.svelte';
	import Plus from '../icons/Plus.svelte';
	import Spinner from '../common/Spinner.svelte';
	import { capitalizeFirstLetter } from '$lib/utils';
	import Tooltip from '../common/Tooltip.svelte';
	import { buttonVariants } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface KnowledgeItem {
		id: string;
		name: string;
		description: string;
		updated_at: number;
		meta?: { document?: boolean };
		user?: { name?: string; email?: string };
		[key: string]: unknown;
	}

	let loaded = $state(false);

	let query = $state('');
	let selectedItem = $state<KnowledgeItem | null>(null);
	let showDeleteConfirm = $state(false);

	let knowledgeBases = $state<KnowledgeItem[]>([]);

	let fuse = $derived(
		knowledgeBases ? new Fuse(knowledgeBases, { keys: ['name', 'description'] }) : null
	);

	let filteredItems = $derived(
		query && fuse ? fuse.search(query).map((e: { item: KnowledgeItem }) => e.item) : knowledgeBases
	);

	const deleteHandler = async (item) => {
		const res = await deleteKnowledgeById('', item.id).catch((e) => {
			toast.error(`${e}`);
		});

		if (res) {
			knowledgeBases = (await getKnowledgeBaseList('')) as unknown as KnowledgeItem[];
			knowledge.set(await getKnowledgeBases(''));
			toast.success($i18n.t('Knowledge deleted successfully.'));
		}
	};

	onMount(async () => {
		knowledgeBases = (await getKnowledgeBaseList('')) as unknown as KnowledgeItem[];
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Knowledge')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		onconfirm={() => {
			deleteHandler(selectedItem);
		}}
	/>

	<div class="mb-2 flex flex-col gap-4">
		<div class="flex items-center justify-between gap-3">
			<h1 class="flex items-center gap-2.5 text-xl font-semibold">
				{$i18n.t('Knowledge')}
				<span class="text-sm font-normal text-muted-foreground tabular-nums"
					>{filteredItems.length}</span
				>
			</h1>
			<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/knowledge/create')}>
				<Plus className="size-4" />
				{$i18n.t('Create Knowledge')}
			</a>
		</div>

		<div class="relative">
			<Search
				className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
			/>
			<Input class="pl-9" placeholder={$i18n.t('Search Knowledge')} bind:value={query} />
		</div>

		{#if filteredItems.length > 0}
			<div class="flex flex-col gap-0.5">
				{#each filteredItems as item (item.id)}
					<div
						class="group flex items-center gap-3 rounded-lg px-2.5 py-2 transition hover:bg-accent/60"
						id="knowledge-item-{item.id}"
					>
						<div
							class="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="1.5"
								stroke="currentColor"
								class="size-4"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
								/>
							</svg>
						</div>

						<button
							type="button"
							class="flex min-w-0 flex-1 cursor-pointer flex-col text-left"
							onclick={() => {
								if (item?.meta?.document) {
									toast.error(
										$i18n.t(
											'Only collections can be edited, create a new knowledge base to edit/add documents.'
										)
									);
								} else {
									goto(resolve(`/workspace/knowledge/${item.id}`));
								}
							}}
						>
							<div class="truncate text-sm font-medium">{item.name}</div>
							<div class="truncate text-xs text-muted-foreground">{item.description}</div>
						</button>

						<div class="hidden shrink-0 items-center gap-3 text-xs text-muted-foreground md:flex">
							<Badge
								type={item?.meta?.document ? 'muted' : 'success'}
								content={item?.meta?.document ? $i18n.t('Document') : $i18n.t('Collection')}
							/>
							<Tooltip content={item?.user?.email ?? $i18n.t('Deleted User')} placement="top">
								{$i18n.t('By {{name}}', {
									name: capitalizeFirstLetter(
										item?.user?.name ?? item?.user?.email ?? $i18n.t('Deleted User')
									)
								})}
							</Tooltip>
							<span class="tabular-nums"
								>{$i18n.t('Updated')} {dayjs(item.updated_at * 1000).fromNow()}</span
							>
						</div>

						<ItemMenu
							onDelete={() => {
								selectedItem = item;
								showDeleteConfirm = true;
							}}
						/>
					</div>
				{/each}
			</div>
		{:else}
			<div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
				<div class="text-sm font-medium">{$i18n.t('No knowledge found')}</div>
				<p class="text-xs text-muted-foreground">
					{$i18n.t('Create a knowledge base to get started.')}
				</p>
				<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/knowledge/create')}>
					<Plus className="size-4" />
					{$i18n.t('Create Knowledge')}
				</a>
			</div>
		{/if}

		<div class="text-xs text-muted-foreground">
			{$i18n.t("Use '#' in the prompt input to load and include your knowledge.")}
		</div>
	</div>
{:else}
	<div class="w-full h-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}
