<script lang="ts">
	import DOMPurify from 'dompurify';
	import { toast } from 'svelte-sonner';

	import type { Token } from 'marked';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	import { resolve } from '$app/paths';

	import { APP_BASE_URL } from '$lib/constants';
	import { copyToClipboard, unescapeHtml } from '$lib/utils';

	import Image from '$lib/components/common/Image.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import Source from './Source.svelte';
	import MarkdownInlineTokens from './MarkdownInlineTokens.svelte';

	/** Props for the MarkdownInlineTokens component - renders inline markdown tokens */
	interface Props {
		/** Unique identifier for scoping child component keys */
		id?: string;
		/** Array of inline markdown tokens to render */
		tokens?: Token[];
		/** Callback when a citation source is clicked */
		onSourceClick?: (...args: unknown[]) => void;
	}

	let { id = '', tokens = [], onSourceClick = () => {} }: Props = $props();

	/** Sanitizes HTML content with iframe-specific allowlisting */
	function sanitizeIframeHtml(raw: string): string {
		return DOMPurify.sanitize(raw, {
			ADD_TAGS: ['iframe'],
			ADD_ATTR: ['src', 'title', 'width', 'height', 'frameborder', 'sandbox'],
			FORCE_BODY: true
		}).replace(/<iframe /g, '<iframe sandbox="allow-scripts allow-popups" ');
	}

	/** Copies inline code text to clipboard and shows a toast notification */
	function handleCodespanClick(text: string): void {
		copyToClipboard(unescapeHtml(text));
		toast.success($i18n.t('Copied to clipboard'));
	}

	/** Handles iframe load events by auto-sizing to content height */
	function handleIframeLoad(e: Event): void {
		const target = e.target as HTMLIFrameElement | null;
		if (target) {
			target.style.height =
				target.contentWindow?.document.body.scrollHeight + 20 + 'px';
		}
	}
</script>

{#each tokens as token (token.type + '_' + tokens.indexOf(token))}
	{#if token.type === 'escape'}
		{unescapeHtml(token.text)}
	{:else if token.type === 'html'}
		{@const html = DOMPurify.sanitize(token.text)}
		{#if html && html.includes('<video')}
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: html = DOMPurify.sanitize(token.text) -->
			{@html html}
		{:else if token.text.includes(`<iframe src="${APP_BASE_URL}/api/v1/files/`)}
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: DOMPurify-sanitized; iframe forced to sandbox -->
			{@html sanitizeIframeHtml(token.text)}
		{:else if token.text.includes(`<source_id`)}
			<Source {id} token={{ text: token.text }} onClick={onSourceClick} />
		{:else}
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: html = DOMPurify.sanitize(token.text) -->
			{@html html}
		{/if}
	{:else if token.type === 'link'}
		{#if token.tokens}
			<a
				href={resolve(token.href)}
				target="_blank"
				rel="nofollow noopener noreferrer"
				title={token.title}
			>
				<MarkdownInlineTokens id={`${id}-a`} tokens={token.tokens} {onSourceClick} />
			</a>
		{:else}
			<a
				href={resolve(token.href)}
				target="_blank"
				rel="nofollow noopener noreferrer"
				title={token.title}>{token.text}</a
			>
		{/if}
	{:else if token.type === 'image'}
		<Image src={token.href} alt={token.text} />
	{:else if token.type === 'strong'}
		<strong
			><MarkdownInlineTokens id={`${id}-strong`} tokens={token.tokens} {onSourceClick} /></strong
		>
	{:else if token.type === 'em'}
		<em><MarkdownInlineTokens id={`${id}-em`} tokens={token.tokens} {onSourceClick} /></em>
	{:else if token.type === 'codespan'}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<code
			class="codespan cursor-pointer"
			onclick={() => handleCodespanClick(token.text)}>{unescapeHtml(token.text)}</code
		>
	{:else if token.type === 'br'}
		<br />
	{:else if token.type === 'del'}
		<del><MarkdownInlineTokens id={`${id}-del`} tokens={token.tokens} {onSourceClick} /></del>
	{:else if token.type === 'inlineKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={false} />
		{/if}
	{:else if token.type === 'iframe'}
		<iframe
			src="{APP_BASE_URL}/api/v1/files/{token.fileId}/content"
			title={token.fileId}
			width="100%"
			frameborder="0"
			sandbox="allow-scripts allow-popups"
			onload={handleIframeLoad}
		></iframe>
	{:else if token.type === 'text'}
		{token.raw}
	{/if}
{/each}
