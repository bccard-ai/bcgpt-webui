<script lang="ts">
	import { get } from 'svelte/store';

	import { toast } from 'svelte-sonner';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	import { onMount, getContext, tick } from 'svelte';
	import { fade } from 'svelte/transition';

	import { config, user, models as _models, temporaryChatEnabled, type Model } from '$lib/stores';
	import { getModelIconUrl } from '$lib/utils/providers';
	import { sanitizeResponseContent } from '$lib/utils';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Whether the input area should have a transparent background */
		transparentBackground?: boolean;
		/** Create a pre-filled message pair (user + assistant placeholder) */
		createMessagePair: () => void;
		/** Stop the current streaming response */
		stopResponse: () => void;
		/** Whether any response generation for the current chat is active */
		generating?: boolean;
		/** Whether auto-scroll is enabled (bindable) */
		autoScroll?: boolean;
		/** The @-selected model override */
		atSelectedModel: Model | undefined;
		/** Currently selected model IDs */
		selectedModels: [''];
		/** Chat history object */
		history: Record<string, unknown>;
		/** Current prompt text (bindable) */
		prompt?: string;
		/** Attached files (bindable) */
		files?: Record<string, unknown>[];
		/** Selected tool IDs (bindable) */
		selectedToolIds?: string[];
		/** Whether image generation is enabled (bindable) */
		imageGenerationEnabled?: boolean;
		/** Whether web search is enabled (bindable) */
		webSearchEnabled?: boolean;
		/** Whether context compression is enabled (bindable) */
		contextCompressionEnabled?: boolean;
		/** Whether smart query enhancement is enabled (bindable) */
		smartQueryEnabled?: boolean;
		/** Available tool servers */
		toolServers?: unknown[];
		/** Callback when the composer value changes */
		onchange?: (input: {
			prompt?: string;
			files?: unknown[];
			selectedToolIds?: string[];
			imageGenerationEnabled?: boolean;
			webSearchEnabled?: boolean;
			contextCompressionEnabled?: boolean;
			smartQueryEnabled?: boolean;
		}) => void;
		/** Callback for file upload events */
		onUpload?: (...args: unknown[]) => void;
		/** Callback when the user submits a prompt */
		onSubmit?: (...args: unknown[]) => void;
	}

	let {
		transparentBackground = false,
		createMessagePair,
		stopResponse,
		generating = false,
		autoScroll = $bindable(false),
		atSelectedModel = $bindable(),
		selectedModels,
		history,
		prompt = $bindable(''),
		files = $bindable([]),
		selectedToolIds = $bindable([]),
		imageGenerationEnabled = $bindable(false),
		webSearchEnabled = $bindable(false),
		contextCompressionEnabled = $bindable(false),
		smartQueryEnabled = $bindable(false),
		toolServers = [],
		onchange = () => {},
		onUpload = () => {},
		onSubmit = () => {}
	}: Props = $props();

	/** Resolved model objects from selected IDs (derived from selectedModels) */
	let models = $derived(selectedModels.map((id) => get(_models).find((m) => m.id === id)));

	/** Index of the currently selected model for display */
	let selectedModelIdx = $state(0);

	/**
	 * Handle selection of a suggestion prompt.
	 * Replaces {{CLIPBOARD}} placeholders with actual clipboard content,
	 * then sets the prompt and focuses the input.
	 */
	const selectSuggestionPrompt = async (template: string): Promise<void> => {
		let text = template;

		if (template.includes('{{CLIPBOARD}}')) {
			const clipboardText = await navigator.clipboard.readText().catch(() => {
				toast.error($i18n.t('Failed to read clipboard contents'));
				return '{{CLIPBOARD}}';
			});
			text = template.replaceAll('{{CLIPBOARD}}', clipboardText);
		}

		prompt = text;
		await tick();

		const chatInputContainer = document.getElementById('chat-input-container');
		const chatInput = document.getElementById('chat-input');

		if (chatInputContainer) {
			chatInputContainer.style.height = '';
			chatInputContainer.style.height = Math.min(chatInputContainer.scrollHeight, 200) + 'px';
		}

		await tick();
		if (chatInput) {
			chatInput.focus();
			chatInput.dispatchEvent(new Event('input'));
		}

		await tick();
	};

	/** Default to the last model index when selected models change */
	$effect(() => {
		if (selectedModels.length > 0) {
			selectedModelIdx = models.length - 1;
		}
	});

	onMount(() => {});
</script>

<div class="m-auto w-full max-w-6xl px-2 @2xl:px-20 translate-y-6 py-24 text-center">
	{#if $temporaryChatEnabled}
		<Tooltip
			content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
			className="w-full flex justify-center mb-0.5"
			placement="top"
		>
			<div class="flex items-center gap-2 text-gray-500 font-medium text-lg my-2 w-fit">
				<EyeSlash strokeWidth="2.5" className="size-5" />
				{$i18n.t('Temporary Chat')}
			</div>
		</Tooltip>
	{/if}

	<div
		class="w-full text-3xl text-gray-800 dark:text-gray-100 text-center flex items-center gap-4 font-primary"
	>
		<div class="w-full flex flex-col justify-center items-center">
			<div class="flex flex-row justify-center gap-3 @sm:gap-3.5 w-fit px-5">
				<div class="flex shrink-0 justify-center">
					<div class="flex -space-x-4 mb-0.5" in:fade={{ duration: 100 }}>
						{#each models as model, modelIdx (modelIdx)}
							<Tooltip
								content={(models[modelIdx]?.info?.meta?.tags ?? [])
									.map((tag) => tag.name.toUpperCase())
									.join(', ')}
								placement="top"
							>
								<button
									onclick={() => {
										selectedModelIdx = modelIdx;
									}}
								>
									<img
										crossorigin="anonymous"
										src={getModelIconUrl({
											id: model?.id ?? '',
											owned_by: model?.owned_by,
											direct: model?.direct,
											profileImageUrl: model?.info?.meta?.profile_image_url
										})}
										class=" size-9 @sm:size-10 rounded-full border-[1px] border-gray-100 dark:border-none"
										alt="logo"
										draggable="false"
									/>
								</button>
							</Tooltip>
						{/each}
					</div>
				</div>

				<div class=" text-3xl @sm:text-4xl line-clamp-1" in:fade={{ duration: 100 }}>
					{#if models[selectedModelIdx]?.name}
						{models[selectedModelIdx]?.name}
					{:else}
						{$i18n.t('Hello, {{name}}', { name: $user.name })}
					{/if}
				</div>
			</div>

			<div class="flex mt-1 mb-2">
				<div in:fade={{ duration: 100, delay: 50 }}>
					{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
						<Tooltip
							className=" w-fit"
							content={DOMPurify.sanitize(
								marked.parse(
									sanitizeResponseContent(models[selectedModelIdx]?.info?.meta?.description ?? '')
								)
							)}
							placement="top"
						>
							<div
								class="mt-0.5 px-2 text-sm font-normal text-gray-500 dark:text-gray-400 line-clamp-2 max-w-xl markdown"
							>
								<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: model description, marked output is DOMPurify-sanitized -->
								{@html DOMPurify.sanitize(
									marked.parse(
										sanitizeResponseContent(models[selectedModelIdx]?.info?.meta?.description)
									)
								)}
							</div>
						</Tooltip>

						{#if models[selectedModelIdx]?.info?.meta?.user}
							<div class="mt-0.5 text-sm font-normal text-gray-400 dark:text-gray-500">
								By
								{#if models[selectedModelIdx]?.info?.meta?.user.community}
									<a
										href="https://BCGPT.com/m/{models[selectedModelIdx]?.info?.meta?.user.username}"
										>{models[selectedModelIdx]?.info?.meta?.user.name
											? models[selectedModelIdx]?.info?.meta?.user.name
											: `@${models[selectedModelIdx]?.info?.meta?.user.username}`}</a
									>
								{:else}
									{models[selectedModelIdx]?.info?.meta?.user.name}
								{/if}
							</div>
						{/if}
					{/if}
				</div>
			</div>

			<div class="text-base font-normal @md:max-w-3xl w-full py-3 {atSelectedModel ? 'mt-2' : ''}">
				<MessageInput
					{history}
					{selectedModels}
					bind:files
					bind:prompt
					bind:autoScroll
					bind:selectedToolIds
					bind:imageGenerationEnabled
					bind:webSearchEnabled
					bind:contextCompressionEnabled
					bind:smartQueryEnabled
					bind:atSelectedModel
					{toolServers}
					{onchange}
					{transparentBackground}
					{stopResponse}
					{generating}
					{createMessagePair}
					placeholder={$i18n.t('How can I help you today?')}
					onUpload={(e: CustomEvent) => {
						onUpload?.(e.detail);
					}}
					onSubmit={(text) => {
						onSubmit?.(text);
					}}
				/>
			</div>
		</div>
	</div>
	<div class="mx-auto max-w-2xl font-primary" in:fade={{ duration: 200, delay: 200 }}>
		<div class="mx-5">
			<Suggestions
				suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
					models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
					$config?.default_prompt_suggestions ??
					[]}
				inputValue={prompt}
				onSelect={(content) => {
					selectSuggestionPrompt(content);
				}}
			/>
		</div>
	</div>
</div>
