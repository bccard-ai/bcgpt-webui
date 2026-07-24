<script lang="ts">
	import DOMPurify from 'dompurify';
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { marked, type Token } from 'marked';
	import { unescapeHtml } from '$lib/utils';

	import { APP_BASE_URL } from '$lib/constants';

	import CodeBlock from '$lib/components/chat/Messages/CodeBlock.svelte';
	import MarkdownInlineTokens from '$lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import AlertRenderer, { alertComponent } from './AlertRenderer.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';

	import Source from './Source.svelte';
	import MarkdownTokens from './MarkdownTokens.svelte';
	import { settings } from '$lib/stores';

	/** Props for the MarkdownTokens component - renders block-level markdown tokens */
	interface Props {
		/** Unique identifier for scoping child component keys */
		id?: string;
		/** Array of block-level markdown tokens to render */
		tokens?: Token[];
		/** Whether this is the top-level token list (affects text token wrapping) */
		top?: boolean;
		/** Additional HTML attributes to pass through */
		attributes?: Record<string, unknown>;
		/** Whether to show save buttons on code blocks */
		save?: boolean;
		/** Callback for task checkbox interactions */
		onTaskClick?: (...args: unknown[]) => void;
		/** Callback for source reference clicks */
		onSourceClick?: (...args: unknown[]) => void;
		/** Callback when code block content is reported */
		onCode?: (...args: unknown[]) => void;
		/** Callback when code block content is saved/updated */
		onUpdate?: (...args: unknown[]) => void;
	}

	let {
		id = '',
		tokens = [],
		top = true,
		attributes = {},
		save = false,
		onTaskClick = () => {},
		onSourceClick = () => {},
		onCode = () => {},
		onUpdate = () => {}
	}: Props = $props();

	/** Returns the HTML heading element tag for a given depth (1-6) */
	function headerTag(depth: number): string {
		return 'h' + depth;
	}

	/**
	 * Exports a markdown table token to CSV and triggers a file download.
	 * Handles Unicode via BOM prefix for proper encoding.
	 */
	function exportTableToCSV(token: Token, tokenIdx: number = 0): void {
		const header = token.header.map(
			(headerCell: Token) => `"${headerCell.text.replace(/"/g, '""')}"`
		);

		const rows = token.rows.map((row: Token[]) =>
			row.map((cell: Token) => {
				const cellContent = cell.tokens.map((t: Token) => t.text).join('');
				return `"${cellContent.replace(/"/g, '""')}"`;
			})
		);

		const csvData = [header, ...rows];
		const csvContent = csvData.map((row: string[]) => row.join(',')).join('\n');

		const bom = '\uFEFF';
		const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=UTF-8' });
		saveAs(blob, `table-${id}-${tokenIdx}.csv`);
	}

	/** Sanitizes HTML content with iframe-specific allowlisting */
	function sanitizeIframeHtml(raw: string): string {
		return DOMPurify.sanitize(raw, {
			ADD_TAGS: ['iframe'],
			ADD_ATTR: ['src', 'title', 'width', 'height', 'frameborder', 'sandbox'],
			FORCE_BODY: true
		}).replace(/<iframe /g, '<iframe sandbox="allow-scripts allow-popups" ');
	}

	/** Handles iframe load events by auto-sizing to content height */
	function handleIframeLoad(e: Event): void {
		const target = e.target as HTMLIFrameElement | null;
		if (target) {
			target.style.height = target.contentWindow?.document.body.scrollHeight + 20 + 'px';
		}
	}

	/** Common handler for task checkbox changes */
	function handleTaskChange(
		e: Event,
		token: Token,
		tokenIdx: number,
		item: Token,
		itemIdx: number
	): void {
		onTaskClick({
			id,
			token,
			tokenIdx,
			item,
			itemIdx,
			checked: (e.target as HTMLInputElement)?.checked
		});
	}

	/** Computes the text-align style for a table cell based on column alignment */
	function alignStyle(align: (string | null)[] | undefined, index: number): string {
		return align?.[index] ? `text-align: ${align[index]}` : '';
	}
</script>

{#each tokens as token, tokenIdx (tokenIdx)}
	{#if token.type === 'hr'}
		<hr class="border-gray-100 dark:border-gray-850" />
	{:else if token.type === 'heading'}
		<svelte:element this={headerTag(token.depth)} dir="auto">
			<MarkdownInlineTokens id={`${id}-${tokenIdx}-h`} tokens={token.tokens} {onSourceClick} />
		</svelte:element>
	{:else if token.type === 'code'}
		{#if token.raw.includes('```')}
			<CodeBlock
				id={`${id}-${tokenIdx}`}
				collapsed={$settings?.collapseCodeBlocks ?? false}
				collapsible={$settings?.collapseCodeBlocks ?? false}
				{token}
				lang={token?.lang ?? ''}
				code={token?.text ?? ''}
				{attributes}
				{save}
				onCode={(value: unknown) => {
					onCode?.(value);
				}}
				onSave={(value: string) => {
					onUpdate?.({
						raw: token.raw,
						oldContent: token.text,
						newContent: value
					});
				}}
			/>
		{:else}
			{token.text}
		{/if}
	{:else if token.type === 'table'}
		<div class="relative w-full group">
			<div class="scrollbar-hidden relative overflow-x-auto max-w-full rounded-lg">
				<table
					class="w-full text-sm text-left text-gray-500 dark:text-gray-400 max-w-full rounded-xl"
				>
					<thead
						class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-850 dark:text-gray-400 border-none"
					>
						<tr class="">
							{#each token.header as header, headerIdx (headerIdx)}
								<th
									scope="col"
									class="px-3! py-1.5! cursor-pointer border border-gray-100 dark:border-gray-850"
									style={alignStyle(token.align, headerIdx)}
								>
									<div class="gap-1.5 text-left">
										<div class="shrink-0 break-normal">
											<MarkdownInlineTokens
												id={`${id}-${tokenIdx}-header-${headerIdx}`}
												tokens={header.tokens}
												{onSourceClick}
											/>
										</div>
									</div>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each token.rows as row, rowIdx (rowIdx)}
							<tr class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs">
								{#each row ?? [] as cell, cellIdx (cellIdx)}
									<td
										class="px-3! py-1.5! text-gray-900 dark:text-white w-max border border-gray-100 dark:border-gray-850"
										style={alignStyle(token.align, cellIdx)}
									>
										<div class="break-normal">
											<MarkdownInlineTokens
												id={`${id}-${tokenIdx}-row-${rowIdx}-${cellIdx}`}
												tokens={cell.tokens}
												{onSourceClick}
											/>
										</div>
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class="absolute top-1 right-1.5 z-20 invisible group-hover:visible">
				<Tooltip content={$i18n.t('Export to CSV')}>
					<button
						class="p-1 rounded-lg bg-transparent transition"
						onclick={(e: MouseEvent) => {
							e.stopPropagation();
							exportTableToCSV(token, tokenIdx);
						}}
					>
						<ArrowDownTray className="size-3.5" strokeWidth="1.5" />
					</button>
				</Tooltip>
			</div>
		</div>
	{:else if token.type === 'blockquote'}
		{@const alert = alertComponent(token)}
		{#if alert}
			<AlertRenderer {token} {alert} />
		{:else}
			<blockquote dir="auto">
				<MarkdownTokens
					id={`${id}-${tokenIdx}`}
					tokens={token.tokens}
					{onTaskClick}
					{onSourceClick}
				/>
			</blockquote>
		{/if}
	{:else if token.type === 'list'}
		{#if token.ordered}
			<ol start={token.start || 1}>
				{#each token.items as item, itemIdx (itemIdx)}
					<li dir="auto" class="text-start">
						{#if item?.task}
							<input
								class="translate-y-[1px] -translate-x-1"
								type="checkbox"
								checked={item.checked}
								onchange={(e: Event) => handleTaskChange(e, token, tokenIdx, item, itemIdx)}
							/>
						{/if}

						<MarkdownTokens
							id={`${id}-${tokenIdx}-${itemIdx}`}
							tokens={item.tokens}
							top={token.loose}
							{onTaskClick}
							{onSourceClick}
						/>
					</li>
				{/each}
			</ol>
		{:else}
			<ul>
				{#each token.items as item, itemIdx (itemIdx)}
					<li dir="auto" class="text-start">
						{#if item?.task}
							<input
								class="translate-y-[1px] -translate-x-1"
								type="checkbox"
								checked={item.checked}
								onchange={(e: Event) => handleTaskChange(e, token, tokenIdx, item, itemIdx)}
							/>
						{/if}

						<MarkdownTokens
							id={`${id}-${tokenIdx}-${itemIdx}`}
							tokens={item.tokens}
							top={token.loose}
							{onTaskClick}
							{onSourceClick}
						/>
					</li>
				{/each}
			</ul>
		{/if}
	{:else if token.type === 'details'}
		<Collapsible
			title={token.summary}
			open={$settings?.expandDetails ?? false}
			attributes={token?.attributes}
			className="w-full space-y-1"
			dir="auto"
		>
			<div class="mb-1.5" slot="content">
				<MarkdownTokens
					id={`${id}-${tokenIdx}-d`}
					tokens={marked.lexer(token.text)}
					attributes={token?.attributes}
					{onTaskClick}
					{onSourceClick}
				/>
			</div>
		</Collapsible>
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
			{token.text}
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
	{:else if token.type === 'paragraph'}
		<p dir="auto">
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-p`}
				tokens={token.tokens ?? []}
				{onSourceClick}
			/>
		</p>
	{:else if token.type === 'text'}
		{#if top}
			<p dir="auto">
				{#if token.tokens}
					<MarkdownInlineTokens id={`${id}-${tokenIdx}-t`} tokens={token.tokens} {onSourceClick} />
				{:else}
					{unescapeHtml(token.text)}
				{/if}
			</p>
		{:else if token.tokens}
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-p`}
				tokens={token.tokens ?? []}
				{onSourceClick}
			/>
		{:else}
			{unescapeHtml(token.text)}
		{/if}
	{:else if token.type === 'inlineKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={token?.displayMode ?? false} />
		{/if}
	{:else if token.type === 'blockKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={token?.displayMode ?? false} />
		{/if}
	{:else if token.type === 'space'}
		<div class="my-2"></div>
	{/if}
{/each}
