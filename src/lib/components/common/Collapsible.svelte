<script lang="ts">
	import { decode } from 'html-entities';
	import { getContext } from 'svelte';

	import dayjs from '$lib/dayjs';
	import duration from 'dayjs/plugin/duration';
	import relativeTime from 'dayjs/plugin/relativeTime';

	dayjs.extend(duration);
	dayjs.extend(relativeTime);

	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	import ChevronUp from '../icons/ChevronUp.svelte';
	import ChevronDown from '../icons/ChevronDown.svelte';
	import Spinner from './Spinner.svelte';
	import Markdown from '../chat/Messages/Markdown.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	async function loadLocale(locales: string[]) {
		for (const locale of locales) {
			try {
				dayjs.locale(locale);
				break;
			} catch (error) {
				console.error(`Could not load locale '${locale}':`, error);
			}
		}
	}

	/**
	 * CollapsibleAttributes — metadata for reasoning / tool-call / code-interpreter blocks.
	 */
	interface CollapsibleAttributes {
		done?: string;
		type?: string;
		duration?: number;
		id?: string;
		name?: string;
		arguments?: string;
		result?: string;
		[key: string]: unknown;
	}

	/**
	 * Collapsible — expandable/collapsible section with optional title or custom trigger.
	 *
	 * Supports special rendering for reasoning, code-interpreter, and tool-call attributes,
	 * as well as generic title + content patterns.
	 *
	 * @example
	 * ```svelte
	 * <Collapsible title="Details" bind:open>
	 *   {#snippet content()}
	 *     <p>Expanded content here</p>
	 *   {/snippet}
	 * </Collapsible>
	 * ```
	 *
	 * @props open - Bindable expanded state
	 * @props title - Header text (use `null` for custom children trigger)
	 * @props attributes - Optional metadata for reasoning/tool-call rendering
	 * @props chevron - Show chevron icon in custom-children mode
	 * @props grow - Content grows inline instead of below
	 * @props disabled - Prevent toggling
	 * @props hide - Hide content even when open
	 */
	interface Props {
		/** Bindable expanded state. */
		open?: boolean;
		/** CSS classes on the wrapper div. */
		className?: string;
		/** CSS classes on the toggle button. */
		buttonClassName?: string;
		/** HTML id attribute. */
		id?: string;
		/** Header text. `null` switches to custom-children trigger mode. */
		title?: string | null;
		/** Metadata for special rendering (reasoning, tool-calls, etc.). */
		attributes?: CollapsibleAttributes | null;
		/** Show chevron icons in custom-children mode. */
		chevron?: boolean;
		/** Content grows inline rather than below the trigger. */
		grow?: boolean;
		/** Prevent toggling. */
		disabled?: boolean;
		/** Hide content even when open. */
		hide?: boolean;
		/** Custom trigger content (used when title is null). */
		children?: import('svelte').Snippet;
		/** Expanded content. */
		content?: import('svelte').Snippet;
		/** Called when open state changes. */
		onchange?: (...args: unknown[]) => void;
	}

	let {
		open = $bindable(false),
		className = '',
		buttonClassName = 'w-fit text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition',
		id = '',
		title = null,
		attributes = null,
		chevron = false,
		grow = false,
		disabled = false,
		hide = false,
		children,
		content,
		onchange = () => {}
	}: Props = $props();

	/** Attempt to parse and pretty-print a double-encoded JSON string. */
	function formatJSONString(obj: string): string {
		try {
			const parsed = JSON.parse(JSON.parse(obj));
			if (typeof parsed === 'object') {
				return JSON.stringify(parsed, null, 2);
			}
			return String(parsed);
		} catch (_e) {
			return obj;
		}
	}

	$effect(() => {
		loadLocale($i18n.languages);
	});
	$effect(() => {
		onchange?.(open);
	});
</script>

<div {id} class={className}>
	{#if title !== null}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="{buttonClassName} cursor-pointer"
			onpointerup={() => {
				if (!disabled) {
					open = !open;
				}
			}}
		>
			<div
				class=" w-full font-medium flex items-center justify-between gap-2 {attributes?.done &&
				attributes?.done !== 'true'
					? 'shimmer'
					: ''}
			"
			>
				{#if attributes?.done && attributes?.done !== 'true'}
					<div>
						<Spinner className="size-4" />
					</div>
				{/if}

				<div class="">
					{#if attributes?.type === 'reasoning'}
						{#if attributes?.done === 'true' && attributes?.duration}
							{#if attributes.duration < 60}
								{$i18n.t('Thought for {{DURATION}} seconds', {
									DURATION: attributes.duration
								})}
							{:else}
								{$i18n.t('Thought for {{DURATION}}', {
									DURATION: dayjs.duration(attributes.duration, 'seconds').humanize()
								})}
							{/if}
						{:else}
							{$i18n.t('Thinking...')}
						{/if}
					{:else if attributes?.type === 'code_interpreter'}
						{#if attributes?.done === 'true'}
							{$i18n.t('Analyzed')}
						{:else}
							{$i18n.t('Analyzing...')}
						{/if}
					{:else if attributes?.type === 'tool_calls'}
						{#if attributes?.done === 'true'}
							<Markdown
								id={`tool-calls-${attributes?.id}`}
								content={$i18n.t('View Result from `{{NAME}}`', {
									NAME: attributes.name
								})}
							/>
						{:else}
							<Markdown
								id={`tool-calls-${attributes?.id}`}
								content={$i18n.t('Executing `{{NAME}}`...', {
									NAME: attributes.name
								})}
							/>
						{/if}
					{:else}
						{title}
					{/if}
				</div>

				<div class="flex self-center translate-y-[1px]">
					{#if open}
						<ChevronUp strokeWidth="3.5" className="size-3.5" />
					{:else}
						<ChevronDown strokeWidth="3.5" className="size-3.5" />
					{/if}
				</div>
			</div>
		</div>
	{:else}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="{buttonClassName} cursor-pointer"
			onpointerup={() => {
				if (!disabled) {
					open = !open;
				}
			}}
		>
			<div>
				<div class="flex items-start justify-between">
					{@render children?.()}

					{#if chevron}
						<div class="flex self-start translate-y-1">
							{#if open}
								<ChevronUp strokeWidth="3.5" className="size-3.5" />
							{:else}
								<ChevronDown strokeWidth="3.5" className="size-3.5" />
							{/if}
						</div>
					{/if}
				</div>

				{#if grow}
					{#if open && !hide}
						<div
							transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}
							onpointerup={(e: PointerEvent) => {
								e.stopPropagation();
							}}
						>
							{@render content?.()}
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{/if}

	{#if !grow}
		{#if open && !hide}
			<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
				{#if attributes?.type === 'tool_calls'}
					{@const args = decode(attributes?.arguments)}
					{@const result = decode(attributes?.result ?? '')}

					{#if attributes?.done === 'true'}
						<Markdown
							id={`tool-calls-${attributes?.id}-result`}
							content={`> \`\`\`json
> ${formatJSONString(args)}
> ${formatJSONString(result)}
> \`\`\``}
						/>
					{:else}
						<Markdown
							id={`tool-calls-${attributes?.id}-result`}
							content={`> \`\`\`json
> ${formatJSONString(args)}
> \`\`\``}
						/>
					{/if}
				{:else}
					{@render content?.()}
				{/if}
			</div>
		{/if}
	{/if}
</div>
