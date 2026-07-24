<script lang="ts">
	/**
	 * Admin Pipelines Settings
	 *
	 * Manages Pipeline plugins: upload, download from GitHub, configure valves,
	 * and delete pipelines. Pipelines extend the platform with custom processing logic.
	 */
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';
	import { toast } from 'svelte-sonner';
	import { config, models, settings } from '$lib/stores';
	import { getContext, onMount, tick } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import {
		getPipelineValves,
		getPipelineValvesSpec,
		updatePipelineValves,
		getPipelines,
		getModels,
		getPipelinesList,
		downloadPipeline,
		deletePipeline,
		uploadPipeline
	} from '$lib/apis';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';

	const i18n: Writable<i18nType> = getContext('i18n');

	interface Props {
		/** Callback invoked after settings are saved */
		saveHandler: () => void;
	}

	let { saveHandler }: Props = $props();

	// --- Loading states ---
	let downloading = $state(false);
	let uploading = $state(false);

	// --- File upload ---
	let pipelineFiles = $state<FileList | null>(null);

	// --- Pipeline list ---
	let PIPELINES_LIST: Array<{ idx: number; url: string }> | null = $state(null);
	let selectedPipelinesUrlIdx = $state('');

	// --- Pipeline details ---
	/* eslint-disable @typescript-eslint/no-explicit-any -- loosely-typed backend payloads */
	let pipelines: Array<any> | null = $state(null);
	let valves: Record<string, any> | null = $state(null);
	let valves_spec: Record<string, any> | null = $state(null);
	/* eslint-enable @typescript-eslint/no-explicit-any */
	let selectedPipelineIdx: number | null = $state(null);

	// --- Download URL ---
	let pipelineDownloadUrl = $state('');

	/** Refresh models list from backend */
	const refreshModels = async () => {
		models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
	};

	/** Update valves for the selected pipeline */
	const updateHandler = async () => {
		const pipeline = pipelines?.[selectedPipelineIdx!];
		if (!pipeline?.valves) {
			toast.error($i18n.t('No valves to update'));
			return;
		}

		// Convert comma-separated arrays
		for (const property in valves_spec.properties) {
			if (valves_spec.properties[property]?.type === 'array') {
				valves[property] = valves[property].split(',').map((v) => v.trim());
			}
		}

		const res = await updatePipelineValves('', pipeline.id, valves, selectedPipelinesUrlIdx).catch(
			(error) => {
				toast.error(`${error}`);
			}
		);

		if (res) {
			toast.success($i18n.t('Valves updated successfully'));
			await setPipelines();
			await refreshModels();
			saveHandler();
		}
	};

	/** Load valves for a pipeline at the given index */
	const getValves = async (idx: number) => {
		valves = null;
		valves_spec = null;

		valves_spec = await getPipelineValvesSpec('', pipelines[idx].id, selectedPipelinesUrlIdx);
		valves = await getPipelineValves('', pipelines[idx].id, selectedPipelinesUrlIdx);

		// Convert arrays to comma-separated strings for editing
		for (const property in valves_spec.properties) {
			if (valves_spec.properties[property]?.type === 'array') {
				valves[property] = valves[property].join(',');
			}
		}
	};

	/** Load pipelines for the selected URL */
	const setPipelines = async () => {
		pipelines = null;
		valves = null;
		valves_spec = null;

		if (PIPELINES_LIST!.length > 0) {
			pipelines = await getPipelines('', selectedPipelinesUrlIdx);
			if (pipelines.length > 0) {
				selectedPipelineIdx = 0;
				await getValves(selectedPipelineIdx);
			}
		} else {
			pipelines = [];
		}
	};

	/** Download and install a pipeline from GitHub URL */
	const addPipelineHandler = async () => {
		downloading = true;
		const res = await downloadPipeline('', pipelineDownloadUrl, selectedPipelinesUrlIdx).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		if (res) {
			toast.success($i18n.t('Pipeline downloaded successfully'));
			await setPipelines();
			await refreshModels();
		}
		downloading = false;
	};

	/** Upload a pipeline from a local .py file */
	const uploadPipelineHandler = async () => {
		uploading = true;

		if (pipelineFiles && pipelineFiles.length !== 0) {
			const file = pipelineFiles[0];
			const res = await uploadPipeline('', file, selectedPipelinesUrlIdx).catch((_error) => {
				toast.error($i18n.t('Something went wrong :/'));
				return null;
			});

			if (res) {
				toast.success($i18n.t('Pipeline uploaded successfully'));
				await setPipelines();
				await refreshModels();
			}
		} else {
			toast.error($i18n.t('No file selected'));
		}

		pipelineFiles = null;
		const uploadInput = document.getElementById('pipelines-upload-input') as HTMLInputElement;
		if (uploadInput) uploadInput.value = null;
		uploading = false;
	};

	/** Delete the currently selected pipeline */
	const deletePipelineHandler = async () => {
		const res = await deletePipeline(
			'',
			pipelines![selectedPipelineIdx!].id,
			selectedPipelinesUrlIdx
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Pipeline deleted successfully'));
			await setPipelines();
			await refreshModels();
		}
	};

	/** Trigger the hidden file input */
	const triggerFileUpload = () => {
		document.getElementById('pipelines-upload-input')?.click();
	};

	/** Toggle a valve property between null and empty string */
	const toggleValveProperty = (property: string) => {
		valves![property] = (valves![property] ?? null) === null ? '' : null;
	};

	onMount(async () => {
		PIPELINES_LIST = await getPipelinesList('');
		if (PIPELINES_LIST.length > 0) {
			selectedPipelinesUrlIdx = PIPELINES_LIST[0].idx.toString();
		}
		await setPipelines();
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(updateHandler)}
>
	<div class="overflow-y-scroll scrollbar-hidden h-full">
		{#if PIPELINES_LIST !== null}
			<!-- About Pipelines -->
			<SettingsSection title={$i18n.t('About Pipelines')}>
				<InfoCallout variant="warning">
					{$i18n.t(
						'Install and configure Pipelines plugins to extend the platform with custom processing logic. Pipelines run arbitrary code, so only add ones from sources you trust.'
					)}
				</InfoCallout>
			</SettingsSection>

			{#if PIPELINES_LIST.length > 0}
				<!-- Pipeline Connection -->
				<SettingsSection title={$i18n.t('Pipeline Connection')}>
					<!-- Pipeline URL Selector -->
					<Select
						class="w-full"
						bind:value={selectedPipelinesUrlIdx}
						placeholder={$i18n.t('Select a pipeline url')}
						items={PIPELINES_LIST.map((pipeline) => ({
							value: pipeline.idx.toString(),
							label: pipeline.url
						}))}
						onValueChange={async () => {
							await tick();
							await setPipelines();
						}}
					/>
				</SettingsSection>

				<!-- Install a Pipeline -->
				<SettingsSection title={$i18n.t('Install a Pipeline')} open={false}>
					<!-- Upload Pipeline -->
					<Field class="my-2" label={$i18n.t('Upload Pipeline')}>
						<div class="flex w-full">
							<div class="flex-1 mr-2">
								<input
									id="pipelines-upload-input"
									bind:files={pipelineFiles}
									type="file"
									accept=".py"
									hidden
								/>
								<button
									class="w-full text-sm font-medium py-2 bg-transparent hover:bg-accent border border-dashed border-input text-center rounded-md"
									type="button"
									onclick={triggerFileUpload}
								>
									{#if pipelineFiles}
										{$i18n.t('{{count}} pipeline(s) selected.', {
											count: pipelineFiles.length > 0 ? pipelineFiles.length : 0
										})}
									{:else}
										{$i18n.t('Click here to select a py file.')}
									{/if}
								</button>
							</div>
							<Button
								variant="secondary"
								size="sm"
								onclick={uploadPipelineHandler}
								disabled={uploading}
								type="button"
							>
								{#if uploading}
									<svg
										class="w-4 h-4"
										viewBox="0 0 24 24"
										fill="currentColor"
										xmlns="http://www.w3.org/2000/svg"
									>
										<style>
											.spinner_ajPY {
												transform-origin: center;
												animation: spinner_AtaB 0.75s infinite linear;
											}
											@keyframes spinner_AtaB {
												to {
													transform: rotate(360deg);
												}
											}
										</style>
										<path
											d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
											opacity=".25"
										/>
										<path
											d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
											class="spinner_ajPY"
										/>
									</svg>
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 16 16"
										fill="currentColor"
										class="size-4"
									>
										<path
											d="M7.25 10.25a.75.75 0 0 0 1.5 0V4.56l2.22 2.22a.75.75 0 1 0 1.06-1.06l-3.5-3.5a.75.75 0 0 0-1.06 0l-3.5 3.5a.75.75 0 0 0 1.06 1.06l2.22-2.22v5.69Z"
										/>
										<path
											d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z"
										/>
									</svg>
								{/if}
							</Button>
						</div>
					</Field>

					<!-- Install from URL -->
					<Field class="my-2" label={$i18n.t('Install from Github URL')}>
						<div class="flex w-full">
							<div class="flex-1 mr-2">
								<Input
									size="sm"
									placeholder={$i18n.t('Enter Github Raw URL')}
									bind:value={pipelineDownloadUrl}
								/>
							</div>
							<Button
								variant="secondary"
								size="sm"
								onclick={addPipelineHandler}
								disabled={downloading}
								type="button"
							>
								{#if downloading}
									<svg
										class="w-4 h-4"
										viewBox="0 0 24 24"
										fill="currentColor"
										xmlns="http://www.w3.org/2000/svg"
									>
										<style>
											.spinner_ajPY {
												transform-origin: center;
												animation: spinner_AtaB 0.75s infinite linear;
											}
											@keyframes spinner_AtaB {
												to {
													transform: rotate(360deg);
												}
											}
										</style>
										<path
											d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
											opacity=".25"
										/>
										<path
											d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
											class="spinner_ajPY"
										/>
									</svg>
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 16 16"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z"
										/>
										<path
											d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z"
										/>
									</svg>
								{/if}
							</Button>
						</div>
						<div class="mt-2 text-xs text-muted-foreground">
							<span class="font-semibold">{$i18n.t('Warning:')}</span>
							{$i18n.t('Pipelines are a plugin system with arbitrary code execution —')}
							<span class="font-medium"
								>{$i18n.t("don't fetch random pipelines from sources you don't trust.")}</span
							>
						</div>
					</Field>
				</SettingsSection>

				<!-- Manage & Configure Pipelines -->
				<SettingsSection title={$i18n.t('Manage & Configure Pipelines')}>
					<!-- Pipeline Valves -->
					{#if pipelines !== null}
						{#if pipelines.length > 0}
							<div class="flex w-full justify-between mb-2">
								<div class="self-center text-sm font-semibold">{$i18n.t('Pipelines Valves')}</div>
							</div>
							<div class="space-y-1">
								<div class="flex gap-2">
									<div class="flex-1">
										<select
											class="h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring"
											bind:value={selectedPipelineIdx}
											onchange={async () => {
												await tick();
												await getValves(selectedPipelineIdx!);
											}}
										>
											{#each pipelines as pipeline, idx (idx)}
												<option value={idx} class="bg-gray-100 dark:bg-gray-700">
													{pipeline.name} ({pipeline.type ?? 'pipe'})
												</option>
											{/each}
										</select>
									</div>
									<Button
										variant="secondary"
										size="sm"
										onclick={deletePipelineHandler}
										type="button"
										aria-label={$i18n.t('Delete')}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 16 16"
											fill="currentColor"
											class="w-4 h-4"
										>
											<path
												fill-rule="evenodd"
												d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.711Z"
												clip-rule="evenodd"
											/>
										</svg>
									</Button>
								</div>

								<div class="space-y-1">
									{#if pipelines[selectedPipelineIdx!].valves}
										{#if valves}
											{#each Object.keys(valves_spec.properties) as property (property)}
												<div class="py-0.5 w-full justify-between">
													<div
														class="flex w-full justify-between pb-2 border-b border-dashed border-border"
													>
														<div class="self-center text-sm font-medium">
															{valves_spec.properties[property].title}
														</div>
														<button
															class="p-1 px-3 text-xs flex rounded-md transition hover:bg-accent"
															type="button"
															onclick={() => toggleValveProperty(property)}
														>
															{#if (valves[property] ?? null) === null}
																<span class="ml-2 self-center">{$i18n.t('None')}</span>
															{:else}
																<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
															{/if}
														</button>
													</div>

													{#if (valves[property] ?? null) !== null}
														<div class="flex mt-0.5 mb-1.5 space-x-2">
															<div class="flex-1">
																{#if valves_spec.properties[property]?.enum ?? null}
																	<select
																		class="h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring"
																		bind:value={valves[property]}
																	>
																		{#each valves_spec.properties[property].enum as option (option)}
																			<option value={option} selected={option === valves[property]}
																				>{option}</option
																			>
																		{/each}
																	</select>
																{:else if (valves_spec.properties[property]?.type ?? null) === 'boolean'}
																	<div class="flex justify-between items-center">
																		<div class="text-xs text-muted-foreground">
																			{valves[property] ? $i18n.t('Enabled') : $i18n.t('Disabled')}
																		</div>
																		<div class="pr-2">
																			<Switch bind:state={valves[property]} />
																		</div>
																	</div>
																{:else}
																	<input
																		class="h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring"
																		type="text"
																		placeholder={valves_spec.properties[property].title}
																		bind:value={valves[property]}
																		autocomplete="off"
																		required
																	/>
																{/if}
															</div>
														</div>
													{/if}
												</div>
											{/each}
										{:else}
											<Spinner className="size-5" />
										{/if}
									{:else}
										<div>{$i18n.t('No valves')}</div>
									{/if}
								</div>
							</div>
						{:else if pipelines.length === 0}
							<div>{$i18n.t('Pipelines Not Detected')}</div>
						{/if}
					{:else}
						<div class="flex justify-center">
							<div class="my-auto"><Spinner className="size-4" /></div>
						</div>
					{/if}
				</SettingsSection>
			{:else}
				<div>{$i18n.t('Pipelines Not Detected')}</div>
			{/if}
		{:else}
			<div class="flex justify-center h-full">
				<div class="my-auto"><Spinner className="size-6" /></div>
			</div>
		{/if}
	</div>

	{#if PIPELINES_LIST !== null && PIPELINES_LIST.length > 0}
		<div class="flex justify-end pt-3">
			<Button type="submit">{$i18n.t('Save')}</Button>
		</div>
	{/if}
</form>
