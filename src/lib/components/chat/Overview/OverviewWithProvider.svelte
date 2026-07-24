<!--
	SPDX-FileCopyrightText: 2026 BC Card
	SPDX-License-Identifier: Apache-2.0

	Lazy-loaded wrapper that provides the SvelteFlow context to Overview.
	By isolating @xyflow/svelte (SvelteFlowProvider + child components) behind a
	dynamic import, the xyflow + d3 bundle chunk is only fetched when the user
	actually opens the overview panel, keeping it out of the initial page load.
-->
<script lang="ts">
	import { SvelteFlowProvider } from '@xyflow/svelte';
	import Overview from '../Overview.svelte';

	interface HistoryMessage {
		id: string;
		role: string;
		parentId: string | null;
		childrenIds: string[];
		model?: string;
		[key: string]: unknown;
	}

	interface Props {
		/** Chat history containing messages and current position */
		history: {
			messages: Record<string, HistoryMessage>;
			currentId: string | null;
			[key: string]: unknown;
		};
		/** Callback when the overview panel is closed */
		onClose?: () => void;
		/** Callback when a flow node is clicked */
		onNodeclick?: (detail: unknown) => void;
	}

	let { history, onClose, onNodeclick }: Props = $props();
</script>

<SvelteFlowProvider>
	<Overview {history} {onClose} {onNodeclick} />
</SvelteFlowProvider>
