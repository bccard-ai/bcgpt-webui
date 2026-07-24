<script lang="ts">
	import { toast } from 'svelte-sonner';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { onMount, getContext } from 'svelte';
	import { APP_NAME_STORE, tools as _tools, user } from '$lib/stores';

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import {
		createNewTool,
		deleteToolById,
		exportTools,
		getToolById,
		getToolList,
		getTools
	} from '$lib/apis/tools';
	import Tooltip from '../common/Tooltip.svelte';
	import ConfirmDialog from '../common/ConfirmDialog.svelte';
	import ToolMenu from './Tools/ToolMenu.svelte';
	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import ValvesModal from './common/ValvesModal.svelte';
	import ManifestModal from './common/ManifestModal.svelte';
	import Heart from '../icons/Heart.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import GarbageBin from '../icons/GarbageBin.svelte';
	import Search from '../icons/Search.svelte';
	import Plus from '../icons/Plus.svelte';
	import Spinner from '../common/Spinner.svelte';
	import { capitalizeFirstLetter } from '$lib/utils';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Tool {
		id: string;
		name: string;
		meta: {
			description?: string;
			manifest?: {
				version?: string;
				funding_url?: string;
			};
		};
		user?: {
			name?: string;
			email?: string;
		};
	}

	let shiftKey = $state(false);
	let loaded = $state(false);

	let toolsImportInputElement: HTMLInputElement = $state();
	let importFiles = $state();

	let showConfirm = $state(false);
	let query = $state('');

	let showManifestModal = $state(false);
	let showValvesModal = $state(false);
	let selectedTool = $state(null as Tool | null);

	let showDeleteConfirm = $state(false);

	let tools = $state([] as Tool[]);
	let filteredItems = $derived(
		tools.filter(
			(t) =>
				query === '' ||
				t.name.toLowerCase().includes(query.toLowerCase()) ||
				t.id.toLowerCase().includes(query.toLowerCase())
		)
	);

	const shareHandler = async (tool) => {
		const item = await getToolById('', tool.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		toast.success($i18n.t('Redirecting you to BCGPT Community'));

		const url = 'https://BCGPT.com';

		const tab = await window.open(`${url}/tools/create`, '_blank');

		const messageHandler = (event: MessageEvent) => {
			if (event.origin !== url) return;
			if (event.data === 'loaded') {
				tab.postMessage(JSON.stringify(item), url);

				window.removeEventListener('message', messageHandler);
			}
		};

		window.addEventListener('message', messageHandler, false);
	};

	const cloneHandler = async (tool) => {
		const _tool = await getToolById('', tool.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (_tool) {
			sessionStorage.tool = JSON.stringify({
				..._tool,
				id: `${_tool.id}_clone`,
				name: `${_tool.name} (Clone)`
			});
			goto(resolve('/workspace/tools/create'));
		}
	};

	const exportHandler = async (tool) => {
		const _tool = await getToolById('', tool.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (_tool) {
			let blob = new Blob([JSON.stringify([_tool])], {
				type: 'application/json'
			});
			saveAs(blob, `tool-${_tool.id}-export-${Date.now()}.json`);
		}
	};

	const deleteHandler = async (tool) => {
		const res = await deleteToolById('', tool.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Tool deleted successfully'));

			init();
		}
	};

	const init = async () => {
		tools = (await getToolList('')) as Tool[];
		_tools.set(await getTools(''));
	};

	onMount(async () => {
		await init();
		loaded = true;

		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Shift') {
				shiftKey = true;
			}
		};

		const onKeyUp = (event: KeyboardEvent) => {
			if (event.key === 'Shift') {
				shiftKey = false;
			}
		};

		const onBlur = () => {
			shiftKey = false;
		};

		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);
		window.addEventListener('blur-sm', onBlur);

		return () => {
			window.removeEventListener('keydown', onKeyDown);
			window.removeEventListener('keyup', onKeyUp);
			window.removeEventListener('blur-sm', onBlur);
		};
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Tools')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<div class="mb-2 flex flex-col gap-4">
		<div class="flex items-center justify-between gap-3">
			<h1 class="flex items-center gap-2.5 text-xl font-semibold">
				{$i18n.t('Tools')}
				<span class="text-sm font-normal text-muted-foreground tabular-nums"
					>{filteredItems.length}</span
				>
			</h1>
			<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/tools/create')}>
				<Plus className="size-4" />
				{$i18n.t('Create Tool')}
			</a>
		</div>

		<div class="relative">
			<Search
				className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
			/>
			<Input class="pl-9" placeholder={$i18n.t('Search Tools')} bind:value={query} />
		</div>

		{#if filteredItems.length > 0}
			<div class="flex flex-col gap-0.5">
				{#each filteredItems as tool (tool.id)}
					<div
						class="group flex items-center gap-3 rounded-lg px-2.5 py-2 transition hover:bg-accent/60"
						id="tool-item-{tool.id}"
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
									d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"
								/></svg
							>
						</div>

						<a
							class="flex min-w-0 flex-1 cursor-pointer flex-col"
							href={resolve(`/workspace/tools/edit?id=${encodeURIComponent(tool.id)}`)}
						>
							<div class="flex items-center gap-1.5">
								<span class="truncate text-sm font-medium">{tool.name}</span>
								{#if tool?.meta?.manifest?.version}
									<span
										class="shrink-0 rounded-sm bg-muted px-1 text-[0.65rem] font-medium text-muted-foreground"
										>v{tool?.meta?.manifest?.version ?? ''}</span
									>
								{/if}
							</div>
							<div class="truncate text-xs text-muted-foreground">{tool.meta.description}</div>
						</a>

						<div class="hidden shrink-0 text-xs text-muted-foreground md:block">
							<Tooltip content={tool?.user?.email ?? $i18n.t('Deleted User')} placement="top">
								{$i18n.t('By {{name}}', {
									name: capitalizeFirstLetter(
										tool?.user?.name ?? tool?.user?.email ?? $i18n.t('Deleted User')
									)
								})}
							</Tooltip>
						</div>

						<div class="flex shrink-0 items-center gap-1">
							{#if shiftKey}
								<Tooltip content={$i18n.t('Delete')}>
									<Button
										variant="ghost"
										size="icon"
										type="button"
										onclick={() => deleteHandler(tool)}
									>
										<GarbageBin />
									</Button>
								</Tooltip>
							{:else}
								{#if tool?.meta?.manifest?.funding_url ?? false}
									<Tooltip content={$i18n.t('Support')}>
										<Button
											variant="ghost"
											size="icon"
											type="button"
											onclick={() => {
												selectedTool = tool;
												showManifestModal = true;
											}}
										>
											<Heart />
										</Button>
									</Tooltip>
								{/if}

								<Tooltip content={$i18n.t('Valves')}>
									<Button
										variant="ghost"
										size="icon"
										type="button"
										aria-label={$i18n.t('Valves')}
										onclick={() => {
											selectedTool = tool;
											showValvesModal = true;
										}}
									>
										<Cog6 />
									</Button>
								</Tooltip>

								<ToolMenu
									editHandler={() => {
										goto(resolve(`/workspace/tools/edit?id=${encodeURIComponent(tool.id)}`));
									}}
									shareHandler={() => shareHandler(tool)}
									cloneHandler={() => cloneHandler(tool)}
									exportHandler={() => exportHandler(tool)}
									deleteHandler={async () => {
										selectedTool = tool;
										showDeleteConfirm = true;
									}}
									onClose={() => {}}
								>
									<Button variant="ghost" size="icon" type="button">
										<EllipsisHorizontal className="size-4" />
									</Button>
								</ToolMenu>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
				<div class="text-sm font-medium">{$i18n.t('No tools found')}</div>
				<p class="text-xs text-muted-foreground">{$i18n.t('Create a tool to get started.')}</p>
				<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/tools/create')}>
					<Plus className="size-4" />
					{$i18n.t('Create Tool')}
				</a>
			</div>
		{/if}
	</div>

	{#if $user?.role === 'admin'}
		<div class=" flex justify-end w-full mb-2">
			<div class="flex space-x-2">
				<input
					id="documents-import-input"
					bind:this={toolsImportInputElement}
					bind:files={importFiles}
					type="file"
					accept=".json"
					hidden
					onchange={() => {
						showConfirm = true;
					}}
				/>

				<button
					class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 transition"
					onclick={() => {
						toolsImportInputElement.click();
					}}
				>
					<div class=" self-center mr-2 font-medium line-clamp-1">{$i18n.t('Import Tools')}</div>

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
						const _tools = await exportTools('').catch((error) => {
							toast.error(`${error}`);
							return null;
						});

						if (_tools) {
							let blob = new Blob([JSON.stringify(_tools)], {
								type: 'application/json'
							});
							saveAs(blob, `tools-export-${Date.now()}.json`);
						}
					}}
				>
					<div class=" self-center mr-2 font-medium line-clamp-1">{$i18n.t('Export Tools')}</div>

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

	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		title={$i18n.t('Delete tool?')}
		onconfirm={() => {
			deleteHandler(selectedTool);
		}}
	>
		<div class=" text-sm text-gray-500">
			{$i18n.t('This will delete')} <span class="  font-semibold">{selectedTool?.name}</span>.
		</div>
	</DeleteConfirmDialog>

	<ValvesModal bind:show={showValvesModal} type="tool" id={selectedTool?.id ?? null} />
	<ManifestModal bind:show={showManifestModal} manifest={selectedTool?.meta?.manifest ?? {}} />

	<ConfirmDialog
		bind:show={showConfirm}
		onconfirm={() => {
			const reader = new FileReader();
			reader.onload = async (event) => {
				const _tools = JSON.parse(event.target?.result);

				for (const tool of _tools) {
					await createNewTool('', tool).catch((error) => {
						toast.error(`${error}`);
						return null;
					});
				}

				toast.success($i18n.t('Tool imported successfully'));
				_tools.set(await getTools(''));
			};

			reader.readAsText(importFiles[0]);
		}}
	>
		<div class="text-sm text-gray-500">
			<div class=" bg-yellow-500/20 text-yellow-700 dark:text-yellow-200 rounded-lg px-4 py-3">
				<div>{$i18n.t('Please carefully review the following warnings:')}</div>

				<ul class=" mt-1 list-disc pl-4 text-xs">
					<li>
						{$i18n.t('Tools have a function calling system that allows arbitrary code execution')}.
					</li>
					<li>{$i18n.t('Do not install tools from sources you do not fully trust.')}</li>
				</ul>
			</div>

			<div class="my-3">
				{$i18n.t(
					'I acknowledge that I have read and I understand the implications of my action. I am aware of the risks associated with executing arbitrary code and I have verified the trustworthiness of the source.'
				)}
			</div>
		</div>
	</ConfirmDialog>
{:else}
	<div class="w-full h-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}
