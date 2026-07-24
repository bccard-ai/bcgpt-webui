<script lang="ts">
	/**
	 * Admin Image Generation Settings
	 *
	 * Configures image generation backends (AUTOMATIC1111, ComfyUI, DALL-E, Gemini)
	 * and manages default model, image size, steps, and workflow settings.
	 */
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';
	import { config as backendConfig, user } from '$lib/stores';
	import { getBackendConfig } from '$lib/apis';
	import {
		getImageGenerationModels,
		getImageGenerationConfig,
		updateImageGenerationConfig,
		getConfig,
		updateConfig,
		verifyConfigUrl
	} from '$lib/apis/images';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	/** Workflow node configuration for ComfyUI */
	interface WorkflowNode {
		type: string;
		key: string;
		node_ids: string;
	}

	interface Props {
		/** Optional callback invoked after settings are saved */
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	// --- State ---
	let loading = $state(false);
	// eslint-disable-next-line @typescript-eslint/no-explicit-any -- dynamic image-gen config shape from API
	let config = $state<Record<string, any> | null>(null);
	// eslint-disable-next-line @typescript-eslint/no-explicit-any -- dynamic image-gen config shape from API
	let imageGenerationConfig = $state<Record<string, any> | null>(null);
	let models = $state<{ id: string; name: string }[] | null>(null);

	/**
	 * Collapsed advanced groups start closed, but auto-open after config loads when their
	 * feature is already in use (image generation enabled / ComfyUI engine selected).
	 */
	let samplingOpen = $state(false);
	let comfyuiWorkflowOpen = $state(false);

	/** Available AUTOMATIC1111 samplers */
	const samplers = [
		'DPM++ 2M',
		'DPM++ SDE',
		'DPM++ 2M SDE',
		'DPM++ 2M SDE Heun',
		'DPM++ 2S a',
		'DPM++ 3M SDE',
		'Euler a',
		'Euler',
		'LMS',
		'Heun',
		'DPM2',
		'DPM2 a',
		'DPM fast',
		'DPM adaptive',
		'Restart',
		'DDIM',
		'DDIM CFG++',
		'PLMS',
		'UniPC'
	];

	/** Available AUTOMATIC1111 schedulers */
	const schedulers = [
		'Automatic',
		'Uniform',
		'Karras',
		'Exponential',
		'Polyexponential',
		'SGM Uniform',
		'KL Optimal',
		'Align Your Steps',
		'Simple',
		'Normal',
		'DDIM',
		'Beta'
	];

	/** Required ComfyUI workflow nodes */
	let requiredWorkflowNodes = $state<WorkflowNode[]>([
		{ type: 'prompt', key: 'text', node_ids: '' },
		{ type: 'model', key: 'ckpt_name', node_ids: '' },
		{ type: 'width', key: 'width', node_ids: '' },
		{ type: 'height', key: 'height', node_ids: '' },
		{ type: 'steps', key: 'steps', node_ids: '' },
		{ type: 'seed', key: 'seed', node_ids: '' }
	]);

	/** Fetch available image generation models */
	const getModels = async () => {
		models = await getImageGenerationModels('').catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	};

	/** Validate that a string is valid JSON */
	const isValidJSON = (json: string): boolean => {
		try {
			const obj = JSON.parse(json);
			return obj !== null && typeof obj === 'object';
		} catch {
			return false;
		}
	};

	/** Update the image engine config and refresh backend state */
	const updateConfigHandler = async () => {
		const res = await updateConfig('', config).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			config = res;
		}

		if (config.enabled) {
			backendConfig.set(await getBackendConfig());
			getModels();
		}
	};

	/** Verify the connection URL for the current engine */
	const verifyConnection = async () => {
		await updateConfigHandler();
		const res = await verifyConfigUrl('').catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('Server connection verified'));
		}
	};

	/** Handle the image generation toggle with validation */
	const handleEnabledToggle = (e: CustomEvent) => {
		const enabled = e.detail;

		if (enabled) {
			const engine = config.engine;
			const checks: Array<{ condition: boolean; message: string }> = [
				{
					condition:
						engine === 'automatic1111' && config.automatic1111.AUTOMATIC1111_BASE_URL === '',
					message: $i18n.t('AUTOMATIC1111 Base URL is required.')
				},
				{
					condition: engine === 'comfyui' && config.comfyui.COMFYUI_BASE_URL === '',
					message: $i18n.t('ComfyUI Base URL is required.')
				},
				{
					condition: engine === 'openai' && config.openai.OPENAI_API_KEY === '',
					message: $i18n.t('OpenAI API Key is required.')
				},
				{
					condition: engine === 'gemini' && config.gemini.GEMINI_API_KEY === '',
					message: $i18n.t('Gemini API Key is required.')
				}
			];

			const failed = checks.find((c) => c.condition);
			if (failed) {
				toast.error(failed.message);
				config.enabled = false;
				return;
			}
		}

		updateConfigHandler();
	};

	/** Handle ComfyUI workflow file upload */
	const handleWorkflowUpload = (e: Event) => {
		const target = e.target as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;

		const reader = new FileReader();
		reader.onload = (ev) => {
			config.comfyui.COMFYUI_WORKFLOW = ev.target?.result;
			if (target) target.value = null;
		};
		reader.readAsText(file);
	};

	/** Save all image generation settings */
	const saveHandler = async () => {
		loading = true;

		// Validate ComfyUI workflow JSON
		if (config?.comfyui?.COMFYUI_WORKFLOW) {
			if (!isValidJSON(config.comfyui.COMFYUI_WORKFLOW)) {
				toast.error($i18n.t('Invalid JSON format for ComfyUI Workflow.'));
				loading = false;
				return;
			}

			// Build workflow nodes from form state
			config.comfyui.COMFYUI_WORKFLOW_NODES = requiredWorkflowNodes.map((node) => ({
				type: node.type,
				key: node.key,
				node_ids: node.node_ids.trim() === '' ? [] : node.node_ids.split(',').map((id) => id.trim())
			}));
		}

		await updateConfig('', config).catch((error) => {
			toast.error(`${error}`);
			loading = false;
			return null;
		});

		await updateImageGenerationConfig('', imageGenerationConfig).catch((error) => {
			toast.error(`${error}`);
			loading = false;
			return null;
		});

		getModels();
		onSave?.();
		loading = false;
	};

	onMount(async () => {
		if (get(user).role === 'admin') {
			const res = await getConfig('').catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (res) {
				config = res;
			}

			if (config.enabled) {
				getModels();
			}

			// Pretty-print ComfyUI workflow JSON
			if (config.comfyui.COMFYUI_WORKFLOW) {
				try {
					config.comfyui.COMFYUI_WORKFLOW = JSON.stringify(
						JSON.parse(config.comfyui.COMFYUI_WORKFLOW),
						null,
						2
					);
				} catch {
					// Keep original if parse fails
				}
			}

			// Map persisted workflow nodes to form state
			requiredWorkflowNodes = requiredWorkflowNodes.map((node) => {
				const persisted =
					config.comfyui.COMFYUI_WORKFLOW_NODES.find((n) => n.type === node.type) ?? node;
				return {
					type: persisted.type,
					key: persisted.key,
					node_ids:
						typeof persisted.node_ids === 'string'
							? persisted.node_ids
							: persisted.node_ids.join(',')
				};
			});

			const imageConfigRes = await getImageGenerationConfig('').catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (imageConfigRes) {
				imageGenerationConfig = imageConfigRes;
			}

			// Auto-open advanced groups whose feature is already active on load.
			samplingOpen = !!config?.enabled;
			comfyuiWorkflowOpen = config?.engine === 'comfyui';
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(saveHandler)}
>
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden pr-2">
		{#if config && imageGenerationConfig}
			<div class="mb-2.5">
				<InfoCallout>
					{$i18n.t(
						'Connect an image generation backend such as AUTOMATIC1111, ComfyUI, DALL·E, or Gemini, then set the default model and image options used to render images in chat.'
					)}
				</InfoCallout>
			</div>

			<!-- Image Generation -->
			<SettingsSection title={$i18n.t('Image Generation')}>
				<Field inline separator label={$i18n.t('Image Generation (Experimental)')}>
					<Switch bind:state={config.enabled} onchange={handleEnabledToggle} />
				</Field>
			</SettingsSection>

			{#if config.enabled}
				<!-- Prompt Processing -->
				<SettingsSection title={$i18n.t('Prompt Processing')}>
					<Field inline separator label={$i18n.t('Image Prompt Generation')}>
						<Switch bind:state={config.prompt_generation} />
					</Field>

					<Field
						inline
						separator
						label={$i18n.t('Image Prompt Translation')}
						description={$i18n.t('Automatically translate non-English prompts to English')}
					>
						<Switch bind:state={config.prompt_translation} />
					</Field>

					<Field
						inline
						separator
						label={$i18n.t('Image Prompt Expansion')}
						description={$i18n.t('Enhance prompts with quality modifiers and artistic details')}
					>
						<Switch bind:state={config.prompt_expansion} />
					</Field>
				</SettingsSection>
			{/if}

			<!-- Engine Connection -->
			<SettingsSection title={$i18n.t('Engine Connection')}>
				<Field inline separator label={$i18n.t('Image Generation Engine')}>
					<Select
						class="w-44"
						bind:value={config.engine}
						onValueChange={updateConfigHandler}
						items={[
							{ value: 'openai', label: $i18n.t('Default (Open AI)') },
							{ value: 'comfyui', label: $i18n.t('ComfyUI') },
							{ value: 'automatic1111', label: $i18n.t('Automatic1111') },
							{ value: 'gemini', label: $i18n.t('Gemini') }
						]}
					/>
				</Field>

				<div class="flex flex-col gap-3 pt-2">
					{#if (config?.engine ?? 'automatic1111') === 'automatic1111'}
						<!-- AUTOMATIC1111 connection -->
						<Field label={$i18n.t('AUTOMATIC1111 Base URL')}>
							<div class="flex w-full items-center gap-2">
								<Input
									size="sm"
									class="flex-1"
									placeholder={$i18n.t('Enter URL (e.g. http://127.0.0.1:7860/)')}
									bind:value={config.automatic1111.AUTOMATIC1111_BASE_URL}
								/>
								<Button
									variant="secondary"
									size="icon"
									type="button"
									aria-label={$i18n.t('Verify connection')}
									onclick={verifyConnection}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											fill-rule="evenodd"
											d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
											clip-rule="evenodd"
										/>
									</svg>
								</Button>
							</div>
							<p class="mt-1 text-xs text-muted-foreground">
								{$i18n.t('Include `--api` flag when running stable-diffusion-webui')}
								<a
									class="font-medium text-primary underline"
									href="https://github.com/AUTOMATIC1111/stable-diffusion-webui/discussions/3734"
									target="_blank"
								>
									{$i18n.t('(e.g. `sh webui.sh --api`)')}
								</a>
							</p>
						</Field>

						<Field label={$i18n.t('AUTOMATIC1111 Api Auth String')}>
							<SensitiveInput
								placeholder={$i18n.t('Enter api auth string (e.g. username:password)')}
								bind:value={config.automatic1111.AUTOMATIC1111_API_AUTH}
								required={false}
							/>
							<p class="mt-1 text-xs text-muted-foreground">
								{$i18n.t('Include `--api-auth` flag when running stable-diffusion-webui')}
								<a
									class="font-medium text-primary underline"
									href="https://github.com/AUTOMATIC1111/stable-diffusion-webui/discussions/13993"
									target="_blank"
								>
									{$i18n
										.t('(e.g. `sh webui.sh --api --api-auth username_password`)')
										.replace('_', ':')}
								</a>
							</p>
						</Field>
					{:else if config?.engine === 'comfyui'}
						<!-- ComfyUI connection -->
						<Field label={$i18n.t('ComfyUI Base URL')}>
							<div class="flex w-full items-center gap-2">
								<Input
									size="sm"
									class="flex-1"
									placeholder={$i18n.t('Enter URL (e.g. http://127.0.0.1:7860/)')}
									bind:value={config.comfyui.COMFYUI_BASE_URL}
								/>
								<Button
									variant="secondary"
									size="icon"
									type="button"
									aria-label={$i18n.t('Verify connection')}
									onclick={verifyConnection}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											fill-rule="evenodd"
											d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
											clip-rule="evenodd"
										/>
									</svg>
								</Button>
							</div>
						</Field>

						<Field label={$i18n.t('ComfyUI API Key')}>
							<SensitiveInput
								placeholder={$i18n.t('sk-1234')}
								bind:value={config.comfyui.COMFYUI_API_KEY}
								required={false}
							/>
						</Field>
					{:else if config?.engine === 'openai'}
						<!-- OpenAI -->
						<Field label={$i18n.t('OpenAI API Base URL')}>
							<Input
								size="sm"
								placeholder={$i18n.t('Enter URL (e.g. https://api.openai.com/v1)')}
								bind:value={config.openai.OPENAI_API_BASE_URL}
								required
							/>
						</Field>

						<Field label={$i18n.t('OpenAI API Key')}>
							<SensitiveInput
								placeholder={$i18n.t('API Key')}
								bind:value={config.openai.OPENAI_API_KEY}
							/>
						</Field>
					{:else if config?.engine === 'gemini'}
						<!-- Gemini -->
						<Field label={$i18n.t('Gemini API Base URL')}>
							<Input
								size="sm"
								placeholder={$i18n.t('Enter URL (e.g. https://generativelanguage.googleapis.com)')}
								bind:value={config.gemini.GEMINI_API_BASE_URL}
								required
							/>
						</Field>

						<Field label={$i18n.t('Gemini API Key')}>
							<SensitiveInput
								placeholder={$i18n.t('API Key')}
								bind:value={config.gemini.GEMINI_API_KEY}
							/>
						</Field>
					{/if}
				</div>
			</SettingsSection>

			<!-- Sampling & Generation Parameters -->
			<SettingsSection title={$i18n.t('Sampling & Generation Parameters')} bind:open={samplingOpen}>
				<div class="flex flex-col gap-3">
					{#if (config?.engine ?? 'automatic1111') === 'automatic1111'}
						<Field label={$i18n.t('Set Sampler')}>
							<Tooltip content={$i18n.t('Enter Sampler (e.g. Euler a)')} placement="top-start">
								<Input
									size="sm"
									list="sampler-list"
									placeholder={$i18n.t('Enter Sampler (e.g. Euler a)')}
									bind:value={config.automatic1111.AUTOMATIC1111_SAMPLER}
								/>
								<datalist id="sampler-list">
									{#each samplers as sampler (sampler)}
										<option value={sampler}>{sampler}</option>
									{/each}
								</datalist>
							</Tooltip>
						</Field>

						<Field label={$i18n.t('Set Scheduler')}>
							<Tooltip content={$i18n.t('Enter Scheduler (e.g. Karras)')} placement="top-start">
								<Input
									size="sm"
									list="scheduler-list"
									placeholder={$i18n.t('Enter Scheduler (e.g. Karras)')}
									bind:value={config.automatic1111.AUTOMATIC1111_SCHEDULER}
								/>
								<datalist id="scheduler-list">
									{#each schedulers as scheduler (scheduler)}
										<option value={scheduler}>{scheduler}</option>
									{/each}
								</datalist>
							</Tooltip>
						</Field>

						<Field label={$i18n.t('Set CFG Scale')}>
							<Tooltip content={$i18n.t('Enter CFG Scale (e.g. 7.0)')} placement="top-start">
								<Input
									size="sm"
									placeholder={$i18n.t('Enter CFG Scale (e.g. 7.0)')}
									bind:value={config.automatic1111.AUTOMATIC1111_CFG_SCALE}
								/>
							</Tooltip>
						</Field>
					{/if}

					{#if config?.enabled}
						<Field label={$i18n.t('Set Default Model')}>
							<Tooltip content={$i18n.t('Enter Model ID')} placement="top-start">
								<Input
									size="sm"
									list="model-list"
									bind:value={imageGenerationConfig.MODEL}
									placeholder={$i18n.t('Select a model')}
									required
								/>
								<datalist id="model-list">
									{#each models ?? [] as model (model.id)}
										<option value={model.id}>{model.name}</option>
									{/each}
								</datalist>
							</Tooltip>
						</Field>

						<Field label={$i18n.t('Set Image Size')}>
							<Tooltip content={$i18n.t('Enter Image Size (e.g. 512x512)')} placement="top-start">
								<Input
									size="sm"
									placeholder={$i18n.t('Enter Image Size (e.g. 512x512)')}
									bind:value={imageGenerationConfig.IMAGE_SIZE}
									required
								/>
							</Tooltip>
						</Field>

						<Field label={$i18n.t('Set Steps')}>
							<Tooltip content={$i18n.t('Enter Number of Steps (e.g. 50)')} placement="top-start">
								<Input
									size="sm"
									placeholder={$i18n.t('Enter Number of Steps (e.g. 50)')}
									bind:value={imageGenerationConfig.IMAGE_STEPS}
									required
								/>
							</Tooltip>
						</Field>
					{/if}
				</div>
			</SettingsSection>

			<!-- ComfyUI Workflow -->
			<SettingsSection title={$i18n.t('ComfyUI Workflow')} bind:open={comfyuiWorkflowOpen}>
				<div class="flex flex-col gap-3">
					{#if config?.engine === 'comfyui'}
						<Field
							label={$i18n.t('ComfyUI Workflow')}
							helper={$i18n.t(
								'Make sure to export a workflow.json file as API format from ComfyUI.'
							)}
						>
							{#if config.comfyui.COMFYUI_WORKFLOW}
								<Textarea
									class="mb-2"
									rows={10}
									bind:value={config.comfyui.COMFYUI_WORKFLOW}
									required
								/>
							{/if}
							<input
								id="upload-comfyui-workflow-input"
								hidden
								type="file"
								accept=".json"
								onchange={handleWorkflowUpload}
							/>
							<Button
								variant="outline"
								size="sm"
								class="w-full border-dashed"
								type="button"
								onclick={() => document.getElementById('upload-comfyui-workflow-input')?.click()}
							>
								{$i18n.t('Click here to upload a workflow.json file.')}
							</Button>
						</Field>

						{#if config.comfyui.COMFYUI_WORKFLOW}
							<Field label={$i18n.t('ComfyUI Workflow Nodes')}>
								<div class="flex flex-col gap-1.5">
									{#each requiredWorkflowNodes as node (node)}
										<div
											class="flex w-full items-center overflow-hidden rounded-md border border-input"
										>
											<div class="shrink-0">
												<div
													class="flex h-8 w-20 items-center justify-center px-3 text-center font-medium capitalize line-clamp-1 bg-green-500/10 text-green-700 dark:text-green-200"
												>
													{node.type}{node.type === 'prompt' ? '*' : ''}
												</div>
											</div>
											<Tooltip content={$i18n.t('Input Key (e.g. text, unet_name, steps)')}>
												<Input
													size="sm"
													class="w-24 border-0 rounded-none bg-transparent text-center shadow-none focus-visible:ring-0"
													placeholder={$i18n.t('Key')}
													bind:value={node.key}
													required
												/>
											</Tooltip>
											<div class="w-full">
												<Tooltip
													content={$i18n.t('Comma separated Node Ids (e.g. 1 or 1,2)')}
													placement="top-start"
												>
													<Input
														size="sm"
														class="w-full border-0 rounded-none bg-transparent text-center shadow-none focus-visible:ring-0"
														placeholder={$i18n.t('Node Ids')}
														bind:value={node.node_ids}
													/>
												</Tooltip>
											</div>
										</div>
									{/each}
								</div>
								<p class="mt-1 text-right text-xs text-muted-foreground">
									{$i18n.t('*Prompt node ID(s) are required for image generation')}
								</p>
							</Field>
						{/if}
					{/if}
				</div>
			</SettingsSection>
		{/if}
	</div>

	<div class="flex justify-end pt-3">
		<Button type="submit" disabled={loading}>
			{$i18n.t('Save')}
			{#if loading}
				<div class="ml-2 self-center">
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
								100% {
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
				</div>
			{/if}
		</Button>
	</div>
</form>
