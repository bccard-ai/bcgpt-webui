<script lang="ts">
	import katex from 'katex';
	import 'katex/contrib/mhchem';
	import 'katex/dist/katex.min.css';

	/** Props for the KatexRenderer component - renders mathematical expressions via KaTeX */
	interface Props {
		/** The LaTeX expression to render */
		content: string;
		/** Whether to render in display (block) mode instead of inline mode */
		displayMode?: boolean;
	}

	let { content, displayMode = false }: Props = $props();
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: KaTeX renders to safe HTML (trust:false; no raw HTML/JS) -->
{@html katex.renderToString(content, { displayMode, throwOnError: false })}
