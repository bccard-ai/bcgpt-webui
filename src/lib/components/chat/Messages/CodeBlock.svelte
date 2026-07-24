<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { copyToClipboard } from '$lib/utils';

	import 'highlight.js/styles/github-dark.min.css';

	import CodeEditor from '$lib/components/common/CodeEditor.svelte';
	import SvgPanZoom from '$lib/components/common/SVGPanZoom.svelte';
	import ChevronUpDown from '$lib/components/icons/ChevronUpDown.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/** Props for the CodeBlock component - renders code with syntax highlighting */
	interface Props {
		/** Unique identifier for the code block */
		id?: string;
		/** Callback when code content is saved */
		onSave?: (code: string) => void;
		/** Callback when code content is reported */
		onCode?: (code: Record<string, string>) => void;
		/** Whether to show the save button */
		save?: boolean;
		/** Whether the code block is runnable (reserved for future use) */
		run?: boolean;
		/** Whether the code block is collapsed */
		collapsed?: boolean;
		/** The original marked token */
		token: Record<string, unknown>;
		/** Programming language identifier */
		lang?: string;
		/** The code content */
		code?: string;
		/** Additional HTML attributes */
		attributes?: Record<string, unknown>;
		/** Additional CSS class for the outer container */
		className?: string;
		/** Whether to show the Collapse/Expand toggle (on when collapseCodeBlocks is enabled). */
		collapsible?: boolean;
	}

	let {
		id = '',
		onSave = () => {},
		onCode = () => {},
		save = false,
		// eslint-disable-next-line @typescript-eslint/no-unused-vars -- prop may be used in template extensions
		run = true,
		collapsed = $bindable(false),
		token: _token,
		lang = '',
		code = $bindable(''),
		// eslint-disable-next-line @typescript-eslint/no-unused-vars -- prop may be used in template extensions
		attributes = {},
		className = 'my-2',
		collapsible = false
	}: Props = $props();

	/** Internal working copy of the code for the editor */
	let _code = $state('');

	/** Rendered mermaid diagram HTML (null until rendered) */
	let mermaidHtml = $state<string | null>(null);

	/** Whether the copy feedback is showing */
	let copied = $state(false);
	/** Whether the save feedback is showing */
	let saved = $state(false);

	/** Syncs the internal code copy when the prop changes */
	function syncCode(): void {
		_code = code;
	}

	/** Toggles the collapsed state of the code block */
	function collapseCodeBlock(): void {
		collapsed = !collapsed;
	}

	/** Persists the edited code and notifies the parent */
	function saveCode(): void {
		saved = true;
		code = _code;
		onSave(code);

		setTimeout(() => {
			saved = false;
		}, 1000);
	}

	/** Copies the code content to the system clipboard */
	async function copyCode(): Promise<void> {
		copied = true;
		await copyToClipboard(code);

		setTimeout(() => {
			copied = false;
		}, 1000);
	}

	onMount(async () => {
		if (lang) {
			onCode({ lang, code });
		}
		// Mermaid is a heavy dependency (~1MB); load + initialize it lazily, and only for
		// actual mermaid blocks, so it never ships in the per-message bundle for plain code.
		if (lang === 'mermaid') {
			const mermaid = (await import('mermaid')).default;
			const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'default';
			mermaid.initialize({ startOnLoad: true, theme, securityLevel: 'strict' });
		}
	});

	$effect(() => {
		if (code) {
			syncCode();
		}
	});
</script>

<div>
	<div
		class="codeblock relative {className} flex flex-col rounded-lg border border-gray-200 dark:border-[#3a3f4b] overflow-hidden bg-white dark:bg-[#282c34]"
		dir="ltr"
	>
		{#if lang === 'mermaid'}
			{#if mermaidHtml}
				<SvgPanZoom
					className="border border-gray-100 dark:border-gray-850 rounded-lg max-h-fit overflow-hidden"
					svg={mermaidHtml}
					content={_token.text as string}
				/>
			{:else}
				<pre class="mermaid">{code}</pre>
			{/if}
		{:else}
			<!-- Header bar: language label (left) + actions (right) -->
			<div
				class="flex items-center justify-between h-9 pl-4 pr-2 bg-gray-50 dark:bg-[#21252b] border-b border-gray-200 dark:border-[#3a3f4b]"
			>
				<span class="text-xs font-medium text-gray-500 dark:text-gray-400 lowercase truncate">
					{lang || 'text'}
				</span>

				<div class="flex items-center gap-0.5">
					{#if save}
						<button
							class="save-code-button inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200/60 dark:hover:bg-white/10 rounded-md px-2 py-1 transition"
							onclick={saveCode}
						>
							{saved ? $i18n.t('Saved') : $i18n.t('Save')}
						</button>
					{/if}

					{#if collapsible}
						<button
							class="inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200/60 dark:hover:bg-white/10 rounded-md px-2 py-1 transition"
							onclick={collapseCodeBlock}
						>
							<ChevronUpDown className="size-3.5" />
							{collapsed ? $i18n.t('Expand') : $i18n.t('Collapse')}
						</button>
					{/if}

					<button
						class="copy-code-button inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200/60 dark:hover:bg-white/10 rounded-md px-2 py-1 transition"
						onclick={copyCode}
						aria-label={$i18n.t('Copy')}
					>
						{#if copied}
							<Check className="size-3.5" />
							<span>{$i18n.t('Copied')}</span>
						{:else}
							<Clipboard className="size-3.5" />
							<span>{$i18n.t('Copy')}</span>
						{/if}
					</button>
				</div>
			</div>

			<!-- Body -->
			{#if !collapsed}
				<CodeEditor
					viewer
					value={code}
					{id}
					{lang}
					onSave={() => {
						saveCode();
					}}
					onchange={(value: string) => {
						_code = value;
					}}
				/>
			{:else}
				<div
					class="bg-white dark:bg-[#282c34] dark:text-white pt-2 pb-2 px-4 flex flex-col gap-2 text-xs"
				>
					<span class="text-gray-500 italic">
						{$i18n.t('{{COUNT}} hidden lines', {
							COUNT: code.split('\n').length
						})}
					</span>
				</div>
			{/if}
		{/if}
	</div>
</div>
