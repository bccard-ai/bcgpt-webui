<script lang="ts">
	/**
	 * Admin Models Settings
	 *
	 * Lists all available models from configured providers, allowing admins to
	 * toggle visibility, activate/deactivate, edit presets, import/export, and
	 * manage model ordering. Shift+click reveals hide/show toggle per model.
	 */
	import { get } from 'svelte/store';

	import { marked } from 'marked';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { onMount, getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { config, models as _models, settings, user } from '$lib/stores';
	import {
		createNewModel,
		getBaseModels,
		toggleModelById,
		updateModelById
	} from '$lib/apis/models';

	import { getModels } from '$lib/apis';
	import Search from '$lib/components/icons/Search.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';

	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';
	import { toast } from 'svelte-sonner';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ConfigureModelsModal from './Models/ConfigureModelsModal.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import ArrowPath from '$lib/components/icons/ArrowPath.svelte';
	import ManageModelsModal from './Models/ManageModelsModal.svelte';
	import ModelMenu from '$lib/components/admin/Settings/Models/ModelMenu.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import Eye from '$lib/components/icons/Eye.svelte';
	import { getModelIconUrl } from '$lib/utils/providers';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface ModelEntry {
		id: string;
		name: string;
		is_active?: boolean;
		meta?: {
			hidden?: boolean;
			description?: string;
			profile_image_url?: string;
			[key: string]: unknown;
		};
		owned_by?: string;
		ollama?: {
			digest?: string;
			modified_at?: string;
			[key: string]: unknown;
		};
		base_model_id?: string | null;
		info?: ModelEntry;
		[key: string]: unknown;
	}

	/** Whether shift key is held (reveals hide/show toggle) */
	let shiftKey = $state(false);

	/** File input ref for model import */
	let importFiles = $state();
	let modelsImportInputElement: HTMLInputElement = $state();

	/** Merged list of base + workspace models */
	let models = $state(null as ModelEntry[] | null);

	/** Unfiltered source lists */
	let workspaceModels: ModelEntry[] | null = null;
	let baseModels: ModelEntry[] | null = null;

	/** Search-filtered and alphabetically sorted models */
	let filteredModels = $derived(
		models
			? models
					.filter(
						(m) => searchValue === '' || m.name.toLowerCase().includes(searchValue.toLowerCase())
					)
					.sort((a, b) => a.name.localeCompare(b.name))
			: []
	);

	/** ID of the model currently being edited, or null for list view */
	let selectedModelId = $state(null as string | null);

	/** Modal visibility */
	let showConfigModal = $state(false);
	let showManageModal = $state(false);

	/** Search input value */
	let searchValue = $state('');

	/**
	 * Export an array of models as a downloadable JSON file.
	 * @param modelList - Array of model objects to export
	 */
	const downloadModels = async (modelList: ModelEntry[]) => {
		const blob = new Blob([JSON.stringify(modelList)], { type: 'application/json' });
		saveAs(blob, `models-export-${Date.now()}.json`);
	};

	/**
	 * Load base models and workspace models, then merge them.
	 * Workspace model overrides take precedence over base model fields.
	 */
	const init = async () => {
		workspaceModels = (await getBaseModels('')) as ModelEntry[];
		baseModels = (await getModels('', null, true)) as ModelEntry[];

		models = baseModels.map((m) => {
			const workspaceModel = (workspaceModels ?? []).find((wm) => wm.id === m.id);
			return workspaceModel
				? { ...m, ...workspaceModel }
				: { ...m, id: m.id, name: m.name, is_active: true };
		});
	};

	/**
	 * Refresh the global models store and reload the model list.
	 * Shows a success toast when complete.
	 */
	const refreshModels = async () => {
		_models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
		await init();
		toast.success($i18n.t('Models refreshed successfully'));
	};

	/**
	 * Create or update a model entry. If the model already exists in workspace,
	 * it updates; otherwise creates new. Refreshes the model list afterward.
	 * @param model - The model object to upsert
	 */
	const upsertModelHandler = async (model: ModelEntry) => {
		model.base_model_id = null;

		if ((workspaceModels ?? []).find((m) => m.id === model.id)) {
			const res = await updateModelById('', model.id, model).catch(() => null);
			if (res) {
				toast.success($i18n.t('Model updated successfully'));
			}
		} else {
			const res = await createNewModel('', model).catch(() => null);
			if (res) {
				toast.success($i18n.t('Model updated successfully'));
			}
		}

		_models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
		await init();
	};

	/**
	 * Toggle a model's active state. Creates a workspace entry if needed.
	 * @param model - The model to toggle
	 */
	const toggleModelHandler = async (model: ModelEntry) => {
		if (!Object.keys(model).includes('base_model_id')) {
			await createNewModel('', {
				id: model.id,
				name: model.name,
				base_model_id: null,
				meta: {},
				params: {},
				access_control: {},
				is_active: model.is_active
			}).catch(() => null);
		} else {
			await toggleModelById('', model.id);
		}

		_models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
	};

	/**
	 * Toggle a model's hidden state and persist the change.
	 * @param model - The model to hide/show
	 */
	const hideModelHandler = async (model: ModelEntry) => {
		model.meta = {
			...model.meta,
			hidden: !(model?.meta?.hidden ?? false)
		};

		toast.success(
			model.meta.hidden
				? $i18n.t('Model {{name}} is now hidden', { name: model.id })
				: $i18n.t('Model {{name}} is now visible', { name: model.id })
		);

		upsertModelHandler(model);
	};

	/**
	 * Export a single model as a downloadable JSON file.
	 * @param model - The model to export
	 */
	const exportModelHandler = async (model: ModelEntry) => {
		const blob = new Blob([JSON.stringify([model])], { type: 'application/json' });
		saveAs(blob, `${model.id}-${Date.now()}.json`);
	};

	/**
	 * Parse an imported JSON file and upsert each valid model entry.
	 * Handles both direct model objects and nested info-style exports.
	 */
	const handleImportFile = async () => {
		const reader = new FileReader();
		reader.onload = async (event) => {
			const savedModels = JSON.parse(event.target?.result);

			for (const model of savedModels) {
				if (Object.keys(model).includes('base_model_id')) {
					if (model.base_model_id === null) {
						upsertModelHandler(model);
					}
				} else {
					if (model?.info ?? false) {
						if (model.info.base_model_id === null) {
							upsertModelHandler(model.info);
						}
					}
				}
			}

			await _models.set(
				await getModels(
					'',
					$config?.features?.enable_direct_connections && ($settings?.directConnections ?? null)
				)
			);
			init();
		};

		reader.readAsText(importFiles[0]);
	};

	onMount(async () => {
		await init();

		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Shift') shiftKey = true;
		};
		const onKeyUp = (event: KeyboardEvent) => {
			if (event.key === 'Shift') shiftKey = false;
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

	/** Filter models by search value and sort alphabetically */
</script>

<ConfigureModelsModal bind:show={showConfigModal} initHandler={init} />
<ManageModelsModal bind:show={showManageModal} />

{#if models !== null}
	{#if selectedModelId === null}
		<div class="flex flex-col gap-1 mt-1.5 mb-2">
			<InfoCallout
				>{$i18n.t(
					'Control which models are available to users here, toggling them on or off, hiding them, and managing their parameter presets. Use the settings and refresh actions to keep the list in sync with your connections.'
				)}</InfoCallout
			>
			<div class="flex justify-between items-center">
				<div class="flex items-center md:self-center text-xl font-medium px-0.5">
					{$i18n.t('Models')}
					<div class="flex self-center w-[1px] h-6 mx-2.5 bg-gray-50 dark:bg-gray-850"></div>
					<span class="text-lg font-medium text-gray-500 dark:text-gray-300"
						>{filteredModels.length}</span
					>
				</div>

				<div class="flex items-center gap-1.5">
					<Tooltip content={$i18n.t('Refresh Models')}>
						<Button
							variant="ghost"
							size="icon"
							type="button"
							onclick={() => {
								refreshModels();
							}}
						>
							<ArrowPath />
						</Button>
					</Tooltip>

					<Tooltip content={$i18n.t('Manage Models')}>
						<Button
							variant="ghost"
							size="icon"
							type="button"
							onclick={() => {
								showManageModal = true;
							}}
						>
							<ArrowDownTray />
						</Button>
					</Tooltip>

					<Tooltip content={$i18n.t('Settings')}>
						<Button
							variant="ghost"
							size="icon"
							type="button"
							onclick={() => {
								showConfigModal = true;
							}}
						>
							<Cog6 />
						</Button>
					</Tooltip>
				</div>
			</div>

			<div class="flex flex-1 items-center w-full">
				<div class="relative flex-1">
					<Search
						className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none"
					/>
					<Input
						size="sm"
						class="pl-9"
						placeholder={$i18n.t('Search Models')}
						bind:value={searchValue}
					/>
				</div>
			</div>
		</div>

		<div class=" my-2 mb-5" id="model-list">
			{#if models.length > 0}
				{#each filteredModels as model (model.id)}
					<div
						class=" flex space-x-4 cursor-pointer w-full px-3 py-2 dark:hover:bg-white/5 hover:bg-black/5 rounded-lg transition {model
							?.meta?.hidden
							? 'opacity-50 dark:opacity-50'
							: ''}"
						id="model-item-{model.id}"
					>
						<button
							class=" flex flex-1 text-left space-x-3.5 cursor-pointer w-full"
							type="button"
							onclick={() => {
								selectedModelId = model.id;
							}}
						>
							<div class=" self-center w-8">
								<div
									class=" rounded-full object-cover {(model?.is_active ?? true)
										? ''
										: 'opacity-50 dark:opacity-50'} "
								>
									<img
										src={getModelIconUrl({
											id: model.id,
											owned_by: model.owned_by,
											profileImageUrl: model?.meta?.profile_image_url
										})}
										alt="modelfile profile"
										class=" rounded-full w-full h-auto object-cover"
									/>
								</div>
							</div>

							<div class=" flex-1 self-center {(model?.is_active ?? true) ? '' : 'text-gray-500'}">
								<Tooltip
									content={marked.parse(
										model?.meta?.description
											? model?.meta?.description
											: model?.ollama?.digest
												? `${model?.ollama?.digest} **(${model?.ollama?.modified_at})**`
												: model.id
									) as string}
									className=" w-fit"
									placement="top-start"
								>
									<div class="  font-semibold line-clamp-1">{model.name}</div>
								</Tooltip>
								<div class=" text-xs overflow-hidden text-ellipsis line-clamp-1 text-gray-500">
									<span class=" line-clamp-1">
										{model?.meta?.description
											? model?.meta?.description
											: model?.ollama?.digest
												? `${model.id} (${model?.ollama?.digest})`
												: model.id}
									</span>
								</div>
							</div>
						</button>
						<div class="flex flex-row gap-0.5 items-center self-center">
							{#if shiftKey}
								<Tooltip content={model?.meta?.hidden ? $i18n.t('Show') : $i18n.t('Hide')}>
									<button
										class="self-center w-fit text-sm px-2 py-2 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
										type="button"
										onclick={() => {
											hideModelHandler(model);
										}}
									>
										{#if model?.meta?.hidden}
											<EyeSlash />
										{:else}
											<Eye />
										{/if}
									</button>
								</Tooltip>
							{:else}
								<button
									class="self-center w-fit text-sm px-2 py-2 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
									type="button"
									aria-label={$i18n.t('Edit')}
									onclick={() => {
										selectedModelId = model.id;
									}}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="1.5"
										stroke="currentColor"
										class="w-4 h-4"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
										/>
									</svg>
								</button>

								<ModelMenu
									user={$user ?? {}}
									{model}
									exportHandler={() => {
										exportModelHandler(model);
									}}
									hideHandler={() => {
										hideModelHandler(model);
									}}
									onClose={() => {}}
								>
									<button
										class="self-center w-fit text-sm p-1.5 dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
										type="button"
									>
										<EllipsisHorizontal className="size-5" />
									</button>
								</ModelMenu>

								<div class="ml-1">
									<Tooltip
										content={(model?.is_active ?? true) ? $i18n.t('Enabled') : $i18n.t('Disabled')}
									>
										<Switch
											bind:state={model.is_active}
											onchange={async () => {
												toggleModelHandler(model);
											}}
										/>
									</Tooltip>
								</div>
							{/if}
						</div>
					</div>
				{/each}
			{:else}
				<div class="flex flex-col items-center justify-center w-full h-20">
					<div class="text-gray-500 dark:text-gray-400 text-xs">
						{$i18n.t('No models found')}
					</div>
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
						onchange={handleImportFile}
					/>

					<Button
						variant="secondary"
						size="sm"
						type="button"
						onclick={() => {
							modelsImportInputElement.click();
						}}
					>
						{$i18n.t('Import Presets')}
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
					</Button>

					<Button
						variant="secondary"
						size="sm"
						type="button"
						onclick={async () => {
							downloadModels(models);
						}}
					>
						{$i18n.t('Export Presets')}
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
					</Button>
				</div>
			</div>
		{/if}
	{:else}
		<ModelEditor
			edit
			model={models.find((m) => m.id === selectedModelId)}
			preset={false}
			onSubmit={(model) => {
				upsertModelHandler(model);
				selectedModelId = null;
			}}
			onBack={() => {
				selectedModelId = null;
			}}
		/>
	{/if}
{:else}
	<div class=" h-full w-full flex justify-center items-center">
		<Spinner />
	</div>
{/if}
