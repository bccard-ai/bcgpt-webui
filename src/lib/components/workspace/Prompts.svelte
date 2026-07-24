<script lang="ts">
	import { toast } from 'svelte-sonner';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, getContext } from 'svelte';
	import { APP_NAME_STORE, prompts as _prompts, user } from '$lib/stores';

	import {
		createNewPrompt,
		deletePromptByCommand,
		getPrompts,
		getPromptList
	} from '$lib/apis/prompts';

	import PromptMenu from './Prompts/PromptMenu.svelte';
	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Search from '../icons/Search.svelte';
	import Plus from '../icons/Plus.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import { capitalizeFirstLetter } from '$lib/utils';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface PromptListItem {
		command: string;
		title: string;
		content: string;
		user?: { name?: string; email?: string };
		[key: string]: unknown;
	}

	let promptsImportInputElement: HTMLInputElement = $state();
	let loaded = $state(false);

	let query = $state('');

	let prompts = $state<PromptListItem[]>([]);

	let showDeleteConfirm = $state(false);
	let deletePrompt = $state<PromptListItem | null>(null);

	let filteredItems = $derived(prompts.filter((p) => query === '' || p.command.includes(query)));

	const shareHandler = async (prompt) => {
		toast.success($i18n.t('Redirecting you to BCGPT Community'));

		const url = 'https://BCGPT.com';

		const tab = await window.open(`${url}/prompts/create`, '_blank');
		window.addEventListener(
			'message',
			(event) => {
				if (event.origin !== url) return;
				if (event.data === 'loaded') {
					tab.postMessage(JSON.stringify(prompt), url);
				}
			},
			false
		);
	};

	const cloneHandler = async (prompt) => {
		sessionStorage.prompt = JSON.stringify(prompt);
		goto(resolve('/workspace/prompts/create'));
	};

	const exportHandler = async (prompt) => {
		let blob = new Blob([JSON.stringify([prompt])], {
			type: 'application/json'
		});
		saveAs(blob, `prompt-export-${Date.now()}.json`);
	};

	const deleteHandler = async (prompt) => {
		const command = prompt.command;
		await deletePromptByCommand('', command);
		await init();
	};

	const init = async () => {
		prompts = (await getPromptList('')) as PromptListItem[];
		await _prompts.set(await getPrompts(''));
	};

	onMount(async () => {
		await init();
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Prompts')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		title={$i18n.t('Delete prompt?')}
		onconfirm={() => {
			deleteHandler(deletePrompt);
		}}
	>
		<div class=" text-sm text-gray-500">
			{$i18n.t('This will delete')} <span class="  font-semibold">{deletePrompt?.command}</span>.
		</div>
	</DeleteConfirmDialog>

	<div class="mb-2 flex flex-col gap-4">
		<div class="flex items-center justify-between gap-3">
			<h1 class="flex items-center gap-2.5 text-xl font-semibold">
				{$i18n.t('Prompts')}
				<span class="text-sm font-normal text-muted-foreground tabular-nums"
					>{filteredItems.length}</span
				>
			</h1>
			<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/prompts/create')}>
				<Plus className="size-4" />
				{$i18n.t('Create Prompt')}
			</a>
		</div>

		<div class="relative">
			<Search
				className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
			/>
			<Input class="pl-9" placeholder={$i18n.t('Search Prompts')} bind:value={query} />
		</div>

		{#if filteredItems.length > 0}
			<div class="flex flex-col gap-0.5">
				{#each filteredItems as prompt (prompt.command)}
					<div
						class="group flex items-center gap-3 rounded-lg px-2.5 py-2 transition hover:bg-accent/60"
						id="prompt-item-{prompt.command}"
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
								><path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M2.25 12.76c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.077a1.14 1.14 0 0 1 .778-.332 48.294 48.294 0 0 0 5.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z"
								/></svg
							>
						</div>

						<a
							class="flex min-w-0 flex-1 cursor-pointer flex-col"
							href={resolve(
								`/workspace/prompts/edit?command=${encodeURIComponent(prompt.command)}`
							)}
						>
							<div class="truncate text-sm font-medium capitalize">{prompt.title}</div>
							<div class="truncate font-mono text-xs text-muted-foreground">{prompt.command}</div>
						</a>

						<div class="hidden shrink-0 text-xs text-muted-foreground md:block">
							<Tooltip content={prompt?.user?.email ?? $i18n.t('Deleted User')} placement="top">
								{$i18n.t('By {{name}}', {
									name: capitalizeFirstLetter(
										prompt?.user?.name ?? prompt?.user?.email ?? $i18n.t('Deleted User')
									)
								})}
							</Tooltip>
						</div>

						<div class="flex shrink-0 items-center gap-1">
							<a
								class={buttonVariants({ variant: 'ghost', size: 'sm' })}
								href={resolve(
									`/workspace/prompts/edit?command=${encodeURIComponent(prompt.command)}`
								)}
								aria-label={$i18n.t('Edit')}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="1.5"
									stroke="currentColor"
									class="size-4"
									><path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
									/></svg
								>
								<span class="hidden sm:inline">{$i18n.t('Edit')}</span>
							</a>

							<PromptMenu
								shareHandler={() => shareHandler(prompt)}
								cloneHandler={() => cloneHandler(prompt)}
								exportHandler={() => exportHandler(prompt)}
								deleteHandler={async () => {
									deletePrompt = prompt;
									showDeleteConfirm = true;
								}}
								onClose={() => {}}
							>
								<Button variant="ghost" size="icon" type="button">
									<EllipsisHorizontal className="size-4" />
								</Button>
							</PromptMenu>
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
				<div class="text-sm font-medium">{$i18n.t('No prompts found')}</div>
				<p class="text-xs text-muted-foreground">{$i18n.t('Create a prompt to get started.')}</p>
				<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/prompts/create')}>
					<Plus className="size-4" />
					{$i18n.t('Create Prompt')}
				</a>
			</div>
		{/if}
	</div>

	{#if $user?.role === 'admin'}
		<div class=" flex justify-end w-full mb-3">
			<div class="flex space-x-2">
				<input
					id="prompts-import-input"
					bind:this={promptsImportInputElement}
					type="file"
					accept=".json"
					hidden
					onchange={() => {
						const files = promptsImportInputElement.files;
						if (!files || files.length === 0) return;

						const reader = new FileReader();
						reader.onload = async (event) => {
							const savedPrompts = JSON.parse(event.target?.result);

							for (const prompt of savedPrompts) {
								await createNewPrompt('', {
									command:
										prompt.command.charAt(0) === '/' ? prompt.command.slice(1) : prompt.command,
									title: prompt.title,
									content: prompt.content
								}).catch((error) => {
									toast.error(`${error}`);
									return null;
								});
							}

							prompts = (await getPromptList('')) as PromptListItem[];
							await _prompts.set(await getPrompts(''));

							promptsImportInputElement.value = '';
						};

						reader.readAsText(files[0]);
					}}
				/>

				<button
					class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 transition"
					onclick={() => {
						promptsImportInputElement.click();
					}}
				>
					<div class=" self-center mr-2 font-medium line-clamp-1">{$i18n.t('Import Prompts')}</div>

					<div class=" self-center">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M4 2a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5V6.621a1.5 1.5 0 0 0-.44-1.06L9.94 2.439A1.5 1.5 0 0 0 8.878 2H4Zm4 9.5a.75.75 0 0 1-.75-.75V8.06l-.72.72a.75.75 0 0 1-1.06-1.06l2-2a.75.75 0 0 1 1.06 0l2 2a.75.75 0 1 1-1.06 1.06l-.72-.72v2.69a.75.75 0 0 1-.75.75Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
				</button>

				<button
					class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 transition"
					onclick={async () => {
						let blob = new Blob([JSON.stringify(prompts)], {
							type: 'application/json'
						});
						saveAs(blob, `prompts-export-${Date.now()}.json`);
					}}
				>
					<div class=" self-center mr-2 font-medium line-clamp-1">{$i18n.t('Export Prompts')}</div>

					<div class=" self-center">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M4 2a1.5 1.5 0 0 0-1.5 1.5v9A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5V6.621a1.5 1.5 0 0 0-.44-1.06L9.94 2.439A1.5 1.5 0 0 0 8.878 2H4Zm4 3.5a.75.75 0 0 1 .75.75v2.69l.72-.72a.75.75 0 1 1 1.06 1.06l-2 2a.75.75 0 0 1-1.06 0l-2-2a.75.75 0 0 1 1.06-1.06l.72.72V6.25A.75.75 0 0 1 8 5.5Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
				</button>
			</div>
		</div>
	{/if}
{:else}
	<div class="w-full h-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}
