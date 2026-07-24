<script lang="ts">
	/**
	 * Admin Interface Settings
	 *
	 * Configures interface-wide defaults including task model,
	 * prompt templates, banners, and default prompt suggestions.
	 */
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';
	import { v4 as uuidv4 } from 'uuid';

	import { getBackendConfig, getTaskConfig, updateTaskConfig } from '$lib/apis';
	import { setDefaultPromptSuggestions } from '$lib/apis/configs';
	import { config, models, user } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import { banners as _banners } from '$lib/stores';
	import type { Banner } from '$lib/types';
	import { getBanners, setBanners } from '$lib/apis/configs';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Select } from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	/** Task model configuration state */
	interface TaskConfig {
		TASK_MODEL: string;
		TASK_MODEL_EXTERNAL: string;
		ENABLE_TITLE_GENERATION: boolean;
		TITLE_GENERATION_PROMPT_TEMPLATE: string;
		IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE: string;
		ENABLE_AUTOCOMPLETE_GENERATION: boolean;
		AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: number;
		TAGS_GENERATION_PROMPT_TEMPLATE: string;
		ENABLE_TAGS_GENERATION: boolean;
		ENABLE_SEARCH_QUERY_GENERATION: boolean;
		ENABLE_RETRIEVAL_QUERY_GENERATION: boolean;
		QUERY_GENERATION_PROMPT_TEMPLATE: string;
		TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: string;
	}

	interface Props {
		/** Optional callback invoked after settings are saved */
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	// --- State ---
	let taskConfig = $state<TaskConfig>({
		TASK_MODEL: '',
		TASK_MODEL_EXTERNAL: '',
		ENABLE_TITLE_GENERATION: true,
		TITLE_GENERATION_PROMPT_TEMPLATE: '',
		IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE: '',
		ENABLE_AUTOCOMPLETE_GENERATION: true,
		AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: -1,
		TAGS_GENERATION_PROMPT_TEMPLATE: '',
		ENABLE_TAGS_GENERATION: true,
		ENABLE_SEARCH_QUERY_GENERATION: true,
		ENABLE_RETRIEVAL_QUERY_GENERATION: true,
		QUERY_GENERATION_PROMPT_TEMPLATE: '',
		TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: ''
	});

	let promptSuggestions = $state<Array<{ content: string; title: string[] }>>([]);
	let banners: Banner[] = $state([]);

	// --- Computed ---
	const ollamaModels = $derived($models.filter((m) => m.owned_by === 'ollama'));

	// --- Handlers ---

	/** Save all interface settings */
	const updateInterfaceHandler = async () => {
		taskConfig = await updateTaskConfig('', taskConfig);
		promptSuggestions = await setDefaultPromptSuggestions('', promptSuggestions);
		await persistBanners();
		await config.set(await getBackendConfig());
	};

	/** Persist banner configuration */
	const persistBanners = async () => {
		_banners.set(await setBanners('', banners));
	};

	/** Add a new empty banner */
	const addBanner = () => {
		if (banners.length === 0 || banners.at(-1)?.content !== '') {
			banners = [
				...banners,
				{
					id: uuidv4(),
					type: '',
					title: '',
					content: '',
					dismissible: true,
					timestamp: Math.floor(Date.now() / 1000)
				}
			];
		}
	};

	/** Remove a banner by index */
	const removeBanner = (index: number) => {
		banners.splice(index, 1);
		banners = banners;
	};

	/** Add a new empty prompt suggestion */
	const addPromptSuggestion = () => {
		if (promptSuggestions.length === 0 || promptSuggestions.at(-1)?.content !== '') {
			promptSuggestions = [...promptSuggestions, { content: '', title: ['', ''] }];
		}
	};

	/** Remove a prompt suggestion by index */
	const removePromptSuggestion = (index: number) => {
		promptSuggestions.splice(index, 1);
		promptSuggestions = promptSuggestions;
	};

	/** Handle form submission */
	const handleSubmit = async () => {
		await updateInterfaceHandler();
		onSave?.();
	};

	onMount(async () => {
		taskConfig = await getTaskConfig('');
		promptSuggestions = get(config)?.default_prompt_suggestions ?? [];
		banners = await getBanners('');
	});
</script>

{#if taskConfig}
	<form
		class="flex flex-col h-full justify-between space-y-3 text-sm"
		onsubmit={preventDefault(handleSubmit)}
	>
		<div class="overflow-y-scroll scrollbar-hidden h-full pr-1.5">
			<div class="mb-2.5">
				<InfoCallout>
					{$i18n.t(
						'Set interface-wide defaults here, including task model prompt templates, banners, and default prompt suggestions shown to all users.'
					)}
				</InfoCallout>
			</div>

			<!-- Task Model -->
			<SettingsSection title={$i18n.t('Task Model')}>
				<div class="mb-1 font-medium flex items-center">
					<div class="text-xs mr-1">{$i18n.t('Set Task Model')}</div>
					<Tooltip
						content={$i18n.t(
							'A task model is used when performing tasks such as generating titles for chats and web search queries'
						)}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke="currentColor"
							class="size-3.5"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
							/>
						</svg>
					</Tooltip>
				</div>

				<div class="mb-2.5 flex w-full gap-2">
					<Field class="flex-1" label={$i18n.t('Local Models')}>
						<Select
							size="sm"
							class="w-full"
							bind:value={taskConfig.TASK_MODEL}
							placeholder={$i18n.t('Current Model')}
							items={[
								{ value: '', label: $i18n.t('Current Model') },
								...ollamaModels.map((model) => ({ value: model.id, label: model.name }))
							]}
						/>
					</Field>

					<Field class="flex-1" label={$i18n.t('External Models')}>
						<Select
							size="sm"
							class="w-full"
							bind:value={taskConfig.TASK_MODEL_EXTERNAL}
							placeholder={$i18n.t('Current Model')}
							items={[
								{ value: '', label: $i18n.t('Current Model') },
								...$models.map((model) => ({ value: model.id, label: model.name }))
							]}
						/>
					</Field>
				</div>
			</SettingsSection>

			<!-- Auto-Generation Features -->
			<SettingsSection title={$i18n.t('Auto-Generation Features')}>
				<!-- Title Generation -->
				<Field class="mb-2.5" inline label={$i18n.t('Title Generation')}>
					<Switch bind:state={taskConfig.ENABLE_TITLE_GENERATION} />
				</Field>

				{#if taskConfig.ENABLE_TITLE_GENERATION}
					<Field class="mb-2.5" label={$i18n.t('Title Generation Prompt')}>
						<Tooltip
							content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
							placement="top-start"
						>
							<Textarea
								bind:value={taskConfig.TITLE_GENERATION_PROMPT_TEMPLATE}
								placeholder={$i18n.t(
									'Leave empty to use the default prompt, or enter a custom prompt'
								)}
							/>
						</Tooltip>
					</Field>
				{/if}

				<!-- Tags Generation -->
				<Field class="mb-2.5" inline label={$i18n.t('Tags Generation')}>
					<Switch bind:state={taskConfig.ENABLE_TAGS_GENERATION} />
				</Field>

				{#if taskConfig.ENABLE_TAGS_GENERATION}
					<Field class="mb-2.5" label={$i18n.t('Tags Generation Prompt')}>
						<Tooltip
							content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
							placement="top-start"
						>
							<Textarea
								bind:value={taskConfig.TAGS_GENERATION_PROMPT_TEMPLATE}
								placeholder={$i18n.t(
									'Leave empty to use the default prompt, or enter a custom prompt'
								)}
							/>
						</Tooltip>
					</Field>
				{/if}

				<!-- Retrieval Query Generation -->
				<Field class="mb-2.5" inline label={$i18n.t('Retrieval Query Generation')}>
					<Switch bind:state={taskConfig.ENABLE_RETRIEVAL_QUERY_GENERATION} />
				</Field>

				<!-- Web Search Query Generation -->
				<Field class="mb-2.5" inline label={$i18n.t('Web Search Query Generation')}>
					<Switch bind:state={taskConfig.ENABLE_SEARCH_QUERY_GENERATION} />
				</Field>

				<!-- Autocomplete Generation -->
				<Field class="mb-2.5" inline label={$i18n.t('Autocomplete Generation')}>
					<Tooltip content={$i18n.t('Enable autocomplete generation for chat messages')}>
						<Switch bind:state={taskConfig.ENABLE_AUTOCOMPLETE_GENERATION} />
					</Tooltip>
				</Field>

				{#if taskConfig.ENABLE_AUTOCOMPLETE_GENERATION}
					<Field class="mb-2.5" label={$i18n.t('Autocomplete Generation Input Max Length')}>
						<Tooltip
							content={$i18n.t('Character limit for autocomplete generation input')}
							placement="top-start"
						>
							<input
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								bind:value={taskConfig.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH}
								placeholder={$i18n.t('-1 for no limit, or a positive integer for a specific limit')}
							/>
						</Tooltip>
					</Field>
				{/if}
			</SettingsSection>

			<!-- Prompt Templates (advanced) -->
			<SettingsSection title={$i18n.t('Prompt Templates')} open={false}>
				<!-- Query Generation Prompt -->
				<Field class="mb-2.5" label={$i18n.t('Query Generation Prompt')}>
					<Tooltip
						content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
						placement="top-start"
					>
						<Textarea
							bind:value={taskConfig.QUERY_GENERATION_PROMPT_TEMPLATE}
							placeholder={$i18n.t(
								'Leave empty to use the default prompt, or enter a custom prompt'
							)}
						/>
					</Tooltip>
				</Field>

				<!-- Image Prompt Generation -->
				<Field class="mb-2.5" label={$i18n.t('Image Prompt Generation Prompt')}>
					<Tooltip
						content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
						placement="top-start"
					>
						<Textarea
							bind:value={taskConfig.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE}
							placeholder={$i18n.t(
								'Leave empty to use the default prompt, or enter a custom prompt'
							)}
						/>
					</Tooltip>
				</Field>

				<!-- Tools Function Calling -->
				<Field class="mb-2.5" label={$i18n.t('Tools Function Calling Prompt')}>
					<Tooltip
						content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
						placement="top-start"
					>
						<Textarea
							bind:value={taskConfig.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE}
							placeholder={$i18n.t(
								'Leave empty to use the default prompt, or enter a custom prompt'
							)}
						/>
					</Tooltip>
				</Field>
			</SettingsSection>

			<!-- Banners -->
			<SettingsSection title={$i18n.t('Banners')}>
				<div class={banners.length > 0 ? 'mb-3' : ''}>
					<div
						class="mb-2.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
					>
						<div class="self-center text-sm font-semibold">
							{$i18n.t('Banners')}
						</div>
						<Button
							variant="ghost"
							size="icon"
							type="button"
							aria-label={$i18n.t('Add Banner')}
							onclick={addBanner}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 20 20"
								fill="currentColor"
								class="w-4 h-4"
							>
								<path
									d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z"
								/>
							</svg>
						</Button>
					</div>

					<div class="flex flex-col space-y-1">
						{#each banners as banner, bannerIdx (bannerIdx)}
							<div class="flex justify-between">
								<div
									class="flex flex-row flex-1 border rounded-xl border-gray-100 dark:border-gray-850"
								>
									<select
										class="w-fit capitalize rounded-xl py-2 px-4 text-xs bg-transparent outline-hidden"
										bind:value={banner.type}
										required
									>
										{#if banner.type == ''}
											<option value="" selected disabled class="text-gray-900">
												{$i18n.t('Type')}
											</option>
										{/if}
										<option value="info" class="text-gray-900">{$i18n.t('Info')}</option>
										<option value="warning" class="text-gray-900">{$i18n.t('Warning')}</option>
										<option value="error" class="text-gray-900">{$i18n.t('Error')}</option>
										<option value="success" class="text-gray-900">{$i18n.t('Success')}</option>
									</select>

									<input
										class="pr-5 py-1.5 text-xs w-full bg-transparent outline-hidden"
										placeholder={$i18n.t('Content')}
										bind:value={banner.content}
									/>

									<div class="relative top-1.5 -left-2">
										<Tooltip content={$i18n.t('Dismissible')} className="flex h-fit items-center">
											<Switch bind:state={banner.dismissible} />
										</Tooltip>
									</div>
								</div>

								<button
									class="px-2"
									type="button"
									aria-label={$i18n.t('Remove Banner')}
									onclick={() => removeBanner(bannerIdx)}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
										/>
									</svg>
								</button>
							</div>
						{/each}
					</div>
				</div>
			</SettingsSection>

			<!-- Default Prompt Suggestions (advanced) -->
			{#if $user.role === 'admin'}
				<SettingsSection title={$i18n.t('Default Prompt Suggestions')} open={false}>
					<div class="space-y-3">
						<div class="flex w-full justify-between mb-2">
							<div class="self-center text-sm font-semibold">
								{$i18n.t('Default Prompt Suggestions')}
							</div>
							<Button
								variant="ghost"
								size="icon"
								type="button"
								aria-label={$i18n.t('Add Prompt Suggestion')}
								onclick={addPromptSuggestion}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-4 h-4"
								>
									<path
										d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z"
									/>
								</svg>
							</Button>
						</div>

						<div class="grid lg:grid-cols-2 flex-col gap-1.5">
							{#each promptSuggestions as prompt, promptIdx (promptIdx)}
								<div
									class="flex border border-gray-100 dark:border-none dark:bg-gray-850 rounded-xl py-1.5"
								>
									<div class="flex flex-col flex-1 pl-1">
										<div class="flex border-b border-gray-100 dark:border-gray-850 w-full">
											<input
												class="px-3 py-1.5 text-xs w-full bg-transparent outline-hidden border-r border-gray-100 dark:border-gray-850"
												placeholder={$i18n.t('Title (e.g. Tell me a fun fact)')}
												bind:value={prompt.title[0]}
											/>
											<input
												class="px-3 py-1.5 text-xs w-full bg-transparent outline-hidden border-r border-gray-100 dark:border-gray-850"
												placeholder={$i18n.t('Subtitle (e.g. about the Roman Empire)')}
												bind:value={prompt.title[1]}
											/>
										</div>

										<textarea
											class="px-3 py-1.5 text-xs w-full bg-transparent outline-hidden border-r border-gray-100 dark:border-gray-850 resize-none"
											placeholder={$i18n.t(
												'Prompt (e.g. Tell me a fun fact about the Roman Empire)'
											)}
											rows="3"
											bind:value={prompt.content}
											aria-label="Prompt content"
										></textarea>
									</div>

									<button
										class="px-3"
										type="button"
										aria-label={$i18n.t('Remove Prompt Suggestion')}
										onclick={() => removePromptSuggestion(promptIdx)}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											class="w-4 h-4"
										>
											<path
												d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
											/>
										</svg>
									</button>
								</div>
							{/each}
						</div>

						{#if promptSuggestions.length > 0}
							<div class="text-xs text-left w-full mt-2">
								{$i18n.t('Adjusting these settings will apply changes universally to all users.')}
							</div>
						{/if}
					</div>
				</SettingsSection>
			{/if}
		</div>

		<div class="flex justify-end pt-3">
			<Button type="submit">{$i18n.t('Save')}</Button>
		</div>
	</form>
{/if}
