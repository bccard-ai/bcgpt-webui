<script lang="ts">
	import { get } from 'svelte/store';

	import { marked, type Token } from 'marked';
	import { replaceTokens, processResponseContent } from '$lib/utils';
	import { user } from '$lib/stores';

	import markedExtension from '$lib/utils/marked/extension';
	import markedKatexExtension from '$lib/utils/marked/katex-extension';

	import MarkdownTokens from './Markdown/MarkdownTokens.svelte';

	/** Props for the Markdown component - top-level markdown rendering entry point */
	interface Props {
		/** Unique identifier for scoping child component keys */
		id?: string;
		/** Raw markdown content to render */
		content: string;
		/** Model info for source reference resolution */
		model?: Record<string, unknown> | null;
		/** Whether to enable save functionality on code blocks */
		save?: boolean;
		/** Source IDs for citation badge rendering */
		sourceIds?: string[];
		/** Callback when a source reference is clicked */
		onSourceClick?: (...args: unknown[]) => void;
		/** Callback when a task checkbox is toggled */
		onTaskClick?: (...args: unknown[]) => void;
		/** Callback when content is updated (e.g. code block save) */
		onUpdate?: (...args: unknown[]) => void;
		/** Callback when a code block is rendered */
		onCode?: (...args: unknown[]) => void;
	}

	let {
		id = '',
		content,
		model = null,
		save = false,
		sourceIds = [],
		onSourceClick = () => {},
		onTaskClick = () => {},
		onUpdate = () => {},
		onCode = () => {}
	}: Props = $props();

	/** Parsed markdown token array */
	let tokens = $state<Token[]>([]);

	/** KaTeX extension options */
	const katexOptions = { throwOnError: false };

	marked.use(markedKatexExtension(katexOptions));
	marked.use(markedExtension(katexOptions));

	/** Parses content into markdown tokens when it changes */
	$effect(() => {
		if (content) {
			tokens = marked.lexer(
				replaceTokens(
					processResponseContent(content),
					sourceIds,
					model?.name as string | undefined,
					get(user)?.name
				)
			);
		}
	});
</script>

{#key id}
	<MarkdownTokens
		{tokens}
		{id}
		{save}
		{onTaskClick}
		{onSourceClick}
		onUpdate={(data) => {
			onUpdate?.(data);
		}}
		onCode={(data) => {
			onCode?.(data);
		}}
	/>
{/key}
