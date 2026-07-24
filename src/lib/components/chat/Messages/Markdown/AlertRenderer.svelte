<script lang="ts" module>
	import { marked, type Token } from 'marked';
	import type { ComponentType } from 'svelte';

	/** Supported GitHub-flavored alert types */
	type AlertType = 'NOTE' | 'TIP' | 'IMPORTANT' | 'WARNING' | 'CAUTION';

	/** Theme configuration for an alert variant */
	interface AlertTheme {
		border: string;
		text: string;
		icon: ComponentType;
	}

	/** Parsed alert data extracted from a blockquote token */
	export interface AlertData {
		type: AlertType;
		text: string;
		tokens: Token[];
	}

	/** Visual styles mapped to each alert type */
	const alertStyles: Record<AlertType, AlertTheme> = {
		NOTE: {
			border: 'border-sky-500',
			text: 'text-sky-500',
			icon: Info
		},
		TIP: {
			border: 'border-emerald-500',
			text: 'text-emerald-500',
			icon: LightBlub
		},
		IMPORTANT: {
			border: 'border-purple-500',
			text: 'text-purple-500',
			icon: Star
		},
		WARNING: {
			border: 'border-yellow-500',
			text: 'text-yellow-500',
			icon: ArrowRightCircle
		},
		CAUTION: {
			border: 'border-rose-500',
			text: 'text-rose-500',
			icon: Bolt
		}
	};

	/**
	 * Detects and extracts an alert directive from a blockquote token.
	 * Returns parsed AlertData if the blockquote starts with `[!TYPE]`, or `false` otherwise.
	 */
	export function alertComponent(token: Token): AlertData | false {
		const regExpStr = `^(?:\\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\\])\\s*?\n*`;
		const regExp = new RegExp(regExpStr);
		const matches = token.text?.match(regExp);

		if (matches && matches.length) {
			const alertType = matches[1] as AlertType;
			const newText = token.text.replace(regExp, '');
			const newTokens = marked.lexer(newText);
			return {
				type: alertType,
				text: newText,
				tokens: newTokens
			};
		}
		return false;
	}
</script>

<script lang="ts">
	import Info from '$lib/components/icons/Info.svelte';
	import Star from '$lib/components/icons/Star.svelte';
	import LightBlub from '$lib/components/icons/LightBlub.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import ArrowRightCircle from '$lib/components/icons/ArrowRightCircle.svelte';
	import MarkdownTokens from './MarkdownTokens.svelte';

	/** Props for the AlertRenderer component */
	interface Props {
		/** The original blockquote token */
		token: Token;
		/** Parsed alert data from alertComponent() */
		alert: AlertData;
		/** Optional unique identifier for child components */
		id?: string;
		/** Optional token index for generating unique keys */
		tokenIdx?: number;
		/** Callback for task checkbox interactions */
		onTaskClick?: ((event: MouseEvent) => void) | undefined;
		/** Callback for source reference clicks */
		onSourceClick?: ((event: MouseEvent) => void) | undefined;
	}

	let {
		token: _token,
		alert,
		id = '',
		tokenIdx = 0,
		onTaskClick = undefined,
		onSourceClick = undefined
	}: Props = $props();

	/** Dynamically resolved icon component for the current alert type */
	const SvelteComponent = $derived(alertStyles[alert.type].icon);
</script>

<!--
Renders the following Markdown as alerts:

> [!NOTE]
> Example note

> [!TIP]
> Example tip

> [!IMPORTANT]
> Example important

> [!CAUTION]
> Example caution

> [!WARNING]
> Example warning
-->
<div class={`border-l-2 pl-2 ${alertStyles[alert.type].border}`}>
	<p class={alertStyles[alert.type].text}>
		<SvelteComponent className="inline-block size-4" />
		<b>{alert.type}</b>
	</p>
	<MarkdownTokens id={`${id}-${tokenIdx}`} tokens={alert.tokens} {onTaskClick} {onSourceClick} />
</div>
