<script lang="ts">
	import { get } from 'svelte/store';

	import { marked } from 'marked';

	import { toast } from 'svelte-sonner';

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { APP_NAME_STORE, config, models as _models, settings, user } from '$lib/stores';
	import {
		createNewModel,
		deleteModelById,
		getModels as getWorkspaceModels,
		toggleModelById,
		updateModelById
	} from '$lib/apis/models';

	import { getModels } from '$lib/apis';
	import { getGroups } from '$lib/apis/groups';

	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import ModelMenu from './Models/ModelMenu.svelte';
	import ModelDeleteConfirmDialog from '../common/ConfirmDialog.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import GarbageBin from '../icons/GarbageBin.svelte';
	import Search from '../icons/Search.svelte';
	import Plus from '../icons/Plus.svelte';
	import Switch from '../common/Switch.svelte';
	import Spinner from '../common/Spinner.svelte';
	import { capitalizeFirstLetter } from '$lib/utils';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	type ModelItem = {
		id: string;
		name: string;
		is_active?: boolean;
		user_id?: string;
		user?: { email?: string; name?: string } & Record<string, unknown>;
		meta?: { profile_image_url?: string; description?: string } & Record<string, unknown>;
		info?: Record<string, unknown>;
		access_control?: { write: { group_ids: string[] } } & Record<string, unknown>;
	} & Record<string, unknown>;

	let shiftKey = $state(false);

	let importFiles = $state();
	let modelsImportInputElement: HTMLInputElement = $state();
	let loaded = $state(false);

	let models = $state([] as ModelItem[]);

	let filteredModels = $derived(
		models.filter(
			(m) => searchValue === '' || m.name.toLowerCase().includes(searchValue.toLowerCase())
		)
	);
	let selectedModel = $state(null as ModelItem | null);

	let showModelDeleteConfirm = $state(false);

	let group_ids = $state([] as string[]);

	let searchValue = $state('');

	const deleteModelHandler = async (model) => {
		const res = await deleteModelById('', model.id).catch((e) => {
			toast.error(`${e}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t(`Deleted {{name}}`, { name: model.id }));
		}

		await _models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
		models = (await getWorkspaceModels('')) as ModelItem[];
	};

	const cloneModelHandler = async (model) => {
		sessionStorage.model = JSON.stringify({
			...model,
			id: `${model.id}-clone`,
			name: `${model.name} (Clone)`
		});
		goto(resolve('/workspace/agents/create'));
	};

	const shareModelHandler = async (model) => {
		toast.success($i18n.t('Redirecting you to BCGPT Community'));

		const url = 'https://BCGPT.com';

		const tab = await window.open(`${url}/models/create`, '_blank');

		const messageHandler = (event: MessageEvent) => {
			if (event.origin !== url) return;
			if (event.data === 'loaded') {
				tab.postMessage(JSON.stringify(model), url);

				window.removeEventListener('message', messageHandler);
			}
		};

		window.addEventListener('message', messageHandler, false);
	};

	const hideModelHandler = async (model) => {
		let info = model.info;

		if (!info) {
			info = {
				id: model.id,
				name: model.name,
				meta: {
					suggestion_prompts: null
				},
				params: {}
			};
		}

		info.meta = {
			...info.meta,
			hidden: !(info?.meta?.hidden ?? false)
		};

		const res = await updateModelById('', info.id, info);

		if (res) {
			toast.success(
				$i18n.t(`Model {{name}} is now {{status}}`, {
					name: info.id,
					status: info.meta.hidden ? 'hidden' : 'visible'
				})
			);
		}

		await _models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
		models = (await getWorkspaceModels('')) as ModelItem[];
	};

	const downloadModels = async (models) => {
		let blob = new Blob([JSON.stringify(models)], {
			type: 'application/json'
		});
		saveAs(blob, `models-export-${Date.now()}.json`);
	};

	const exportModelHandler = async (model) => {
		let blob = new Blob([JSON.stringify([model])], {
			type: 'application/json'
		});
		saveAs(blob, `${model.id}-${Date.now()}.json`);
	};

	onMount(async () => {
		models = (await getWorkspaceModels('')) as ModelItem[];
		let groups = await getGroups('');
		group_ids = groups.map((group) => group.id);

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
		{$i18n.t('Agents')} | {$APP_NAME_STORE}
	</title>
</svelte:head>

{#if loaded}
	<ModelDeleteConfirmDialog
		bind:show={showModelDeleteConfirm}
		onconfirm={() => {
			deleteModelHandler(selectedModel);
		}}
	/>

	<div class="mb-2 flex flex-col gap-4">
		<div class="flex items-center justify-between gap-3">
			<h1 class="flex items-center gap-2.5 text-xl font-semibold">
				{$i18n.t('Agents')}
				<span class="text-sm font-normal text-muted-foreground tabular-nums"
					>{filteredModels.length}</span
				>
			</h1>
			<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/agents/create')}>
				<Plus className="size-4" />
				{$i18n.t('Create Agent')}
			</a>
		</div>

		<div class="relative">
			<Search
				className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
			/>
			<Input class="pl-9" placeholder={$i18n.t('Search Agents')} bind:value={searchValue} />
		</div>

		{#if filteredModels.length > 0}
			<div class="flex flex-col gap-0.5" id="model-list">
				{#each filteredModels as model (model.id)}
					<div
						class="group flex items-center gap-3 rounded-lg px-2.5 py-2 transition hover:bg-accent/60"
						id="model-item-{model.id}"
					>
						<img
							src={model?.meta?.profile_image_url ?? '/static/favicon.png'}
							alt={model.name}
							class="size-9 shrink-0 rounded-full object-cover {model.is_active
								? ''
								: 'opacity-50'}"
						/>

						<a
							class="flex min-w-0 flex-1 cursor-pointer flex-col"
							href={resolve(`/?models=${encodeURIComponent(model.id)}`)}
						>
							<Tooltip
								content={marked.parse(model?.meta?.description ?? model.id) as string}
								className="w-fit"
								placement="top-start"
							>
								<div
									class="truncate text-sm font-medium {model.is_active
										? ''
										: 'text-muted-foreground'}"
								>
									{model.name}
								</div>
							</Tooltip>
							<div class="truncate text-xs text-muted-foreground">
								{#if (model?.meta?.description ?? '').trim()}
									{model?.meta?.description}
								{:else}
									{model.id}
								{/if}
							</div>
						</a>

						<div class="hidden shrink-0 text-xs text-muted-foreground md:block">
							<Tooltip content={model?.user?.email ?? $i18n.t('Deleted User')} placement="top">
								{$i18n.t('By {{name}}', {
									name: capitalizeFirstLetter(
										model?.user?.name ?? model?.user?.email ?? $i18n.t('Deleted User')
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
										onclick={() => deleteModelHandler(model)}
									>
										<GarbageBin />
									</Button>
								</Tooltip>
							{:else}
								{#if $user?.role === 'admin' || model.user_id === $user?.id || model.access_control?.write?.group_ids?.some( (wg) => group_ids.includes(wg) )}
									<a
										class={buttonVariants({ variant: 'ghost', size: 'sm' })}
										href={resolve(`/workspace/agents/edit?id=${encodeURIComponent(model.id)}`)}
										aria-label={$i18n.t('Edit')}
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
												d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
											/>
										</svg>
										<span class="hidden sm:inline">{$i18n.t('Edit')}</span>
									</a>
								{/if}

								<ModelMenu
									user={$user}
									{model}
									shareHandler={() => shareModelHandler(model)}
									cloneHandler={() => cloneModelHandler(model)}
									exportHandler={() => exportModelHandler(model)}
									hideHandler={() => hideModelHandler(model)}
									deleteHandler={() => {
										selectedModel = model;
										showModelDeleteConfirm = true;
									}}
									onClose={() => {}}
								>
									<Button variant="ghost" size="icon" type="button">
										<EllipsisHorizontal className="size-4" />
									</Button>
								</ModelMenu>

								<Tooltip content={model.is_active ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
									<Switch
										bind:state={model.is_active}
										onchange={async () => {
											toggleModelById('', model.id);
											_models.set(
												await getModels(
													'',
													$config?.features?.enable_direct_connections &&
														($settings?.directConnections ?? null)
												)
											);
										}}
									/>
								</Tooltip>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
				<div class="text-sm font-medium">{$i18n.t('No agents found')}</div>
				<p class="text-xs text-muted-foreground">{$i18n.t('Create an agent to get started.')}</p>
				<a class={buttonVariants({ size: 'sm' })} href={resolve('/workspace/agents/create')}>
					<Plus className="size-4" />
					{$i18n.t('Create Agent')}
				</a>
			</div>
		{/if}
	</div>

	{#if $user?.role === 'admin'}
		<div class=" flex justify-end w-full mb-3">
			<div class="flex space-x-1">
				<input
					id="models-import-input"
					bind:this={modelsImportInputElement}
					bind:files={importFiles}
					type="file"
					accept=".json"
					hidden
					onchange={() => {
						let reader = new FileReader();
						reader.onload = async (event) => {
							let savedModels = JSON.parse(event.target?.result);

							for (const model of savedModels) {
								if (model?.info ?? false) {
									if ($_models.find((m) => m.id === model.id)) {
										await updateModelById('', model.id, model.info).catch((_error) => {
											return null;
										});
									} else {
										await createNewModel('', model.info).catch((_error) => {
											return null;
										});
									}
								} else {
									if (model?.id && model?.name) {
										await createNewModel('', model).catch((_error) => {
											return null;
										});
									}
								}
							}

							await _models.set(
								await getModels(
									'',
									$config?.features?.enable_direct_connections &&
										($settings?.directConnections ?? null)
								)
							);
							models = (await getWorkspaceModels('')) as ModelItem[];
						};

						reader.readAsText(importFiles[0]);
					}}
				/>

				<button
					class="flex text-xs items-center space-x-1 px-3 py-1.5 rounded-xl bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700 dark:text-gray-200 transition"
					onclick={() => {
						modelsImportInputElement.click();
					}}
				>
					<div class=" self-center mr-2 font-medium line-clamp-1">{$i18n.t('Import Agents')}</div>

					<div class=" self-center">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-3.5 h-3.5"
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
						downloadModels(models);
					}}
				>
					<div class=" self-center mr-2 font-medium line-clamp-1">{$i18n.t('Export Agents')}</div>

					<div class=" self-center">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-3.5 h-3.5"
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
