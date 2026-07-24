<script lang="ts">
	import { get } from 'svelte/store';

	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	import { config, user, models as _models, temporaryChatEnabled } from '$lib/stores';
	import { getModelIconUrl } from '$lib/utils/providers';
	import { onMount, getContext } from 'svelte';

	import { fade } from 'svelte/transition';

	import Suggestions from './Suggestions.svelte';
	import { sanitizeResponseContent } from '$lib/utils';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface ModelInfo {
		id: string;
		name?: string;
		owned_by?: string;
		direct?: boolean;
		info?: {
			meta?: {
				profile_image_url?: string;
				description?: string;
				suggestion_prompts?: unknown[];
				tags?: Array<{ name: string }>;
				user?: {
					name?: string;
					username?: string;
					community?: boolean;
				};
			};
		};
		[key: string]: unknown;
	}

	interface Props {
		/** IDs of the currently selected models */
		modelIds?: string[];
		/** Resolved model objects (populated from modelIds) */
		models?: ModelInfo[];
		/** The @-selected model, if any */
		atSelectedModel?: ModelInfo;
		/** Submit a prompt text */
		submitPrompt: (content: string) => void;
	}

	let { modelIds = [], models = [], atSelectedModel, submitPrompt }: Props = $props();

	/** Whether the component has completed mounting (controls fade-in) */
	let mounted = $state(false);

	/** Index of the currently focused model avatar */
	let selectedModelIdx = $state(0);

	/** Resolve model IDs to full model objects whenever they change */
	$effect(() => {
		models = modelIds.map((id) => get(_models).find((m) => m.id === id));
	});

	/** Default to the last model when the list changes */
	$effect(() => {
		if (modelIds.length > 0) {
			selectedModelIdx = models.length - 1;
		}
	});

	onMount(() => {
		mounted = true;
	});
</script>

{#key mounted}
	<div class="m-auto w-full max-w-6xl px-8 lg:px-20">
		<div class="flex justify-start">
			<div class="flex -space-x-4 mb-0.5" in:fade={{ duration: 200 }}>
				{#each models as model, modelIdx (modelIdx)}
					<button
						onclick={() => {
							selectedModelIdx = modelIdx;
						}}
					>
						<Tooltip
							content={marked.parse(
								sanitizeResponseContent(models[selectedModelIdx]?.info?.meta?.description ?? '')
							) as string}
							placement="right"
						>
							<img
								crossorigin="anonymous"
								src={getModelIconUrl({
									id: model?.id ?? '',
									owned_by: model?.owned_by,
									direct: model?.direct,
									profileImageUrl: model?.info?.meta?.profile_image_url
								})}
								class=" size-[2.7rem] rounded-full border-[1px] border-gray-200 dark:border-none"
								alt="logo"
								draggable="false"
							/>
						</Tooltip>
					</button>
				{/each}
			</div>
		</div>

		{#if $temporaryChatEnabled}
			<Tooltip
				content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
				className="w-fit"
				placement="top-start"
			>
				<div class="flex items-center gap-2 text-gray-500 font-medium text-lg my-2 w-fit">
					<EyeSlash strokeWidth="2.5" className="size-5" />
					{$i18n.t('Temporary Chat')}
				</div>
			</Tooltip>
		{/if}

		<div
			class=" mt-2 mb-4 text-3xl text-gray-800 dark:text-gray-100 font-medium text-left flex items-center gap-4 font-primary"
		>
			<div>
				<div class=" capitalize line-clamp-1" in:fade={{ duration: 200 }}>
					{#if models[selectedModelIdx]?.name}
						{models[selectedModelIdx]?.name}
					{:else}
						{$i18n.t('Hello, {{name}}', { name: $user.name })}
					{/if}
				</div>

				<div in:fade={{ duration: 200, delay: 200 }}>
					{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
						<div
							class="mt-0.5 text-base font-normal text-gray-500 dark:text-gray-400 line-clamp-3 markdown"
						>
							<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: model description, marked output is DOMPurify-sanitized -->
							{@html DOMPurify.sanitize(
								marked.parse(
									sanitizeResponseContent(models[selectedModelIdx]?.info?.meta?.description)
								)
							)}
						</div>
						{#if models[selectedModelIdx]?.info?.meta?.user}
							<div class="mt-0.5 text-sm font-normal text-gray-400 dark:text-gray-500">
								{$i18n.t('By')}
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
					{:else}
						<div class=" font-medium text-gray-400 dark:text-gray-500 line-clamp-1 font-p">
							{$i18n.t('How can I help you today?')}
						</div>
					{/if}
				</div>
			</div>
		</div>

		<div class=" w-full font-primary" in:fade={{ duration: 200, delay: 300 }}>
			<Suggestions
				className="grid grid-cols-2"
				suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
					models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
					$config?.default_prompt_suggestions ??
					[]}
				onSelect={(content) => {
					submitPrompt(content);
				}}
			/>
		</div>
	</div>
{/key}
