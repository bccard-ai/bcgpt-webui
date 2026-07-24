<script lang="ts">
	import { theme } from '$lib/stores';
	import { Background, Controls, SvelteFlow, BackgroundVariant } from '@xyflow/svelte';

	interface FlowNode {
		id: string;
		[key: string]: unknown;
	}

	interface FlowEdge {
		id: string;
		source: string;
		target: string;
		[key: string]: unknown;
	}

	interface Props {
		/** Writable store of flow nodes */
		nodes: import('svelte/store').Writable<FlowNode[]>;
		/** Map of custom node type components */
		nodeTypes: Record<string, unknown>;
		/** Writable store of flow edges */
		edges: import('svelte/store').Writable<FlowEdge[]>;
		/** Callback when a node is clicked */
		onNodeclick?: (detail: unknown) => void;
	}

	let { nodes, nodeTypes, edges, onNodeclick = () => {} }: Props = $props();

	/**
	 * Resolves the xyflow color mode from the application theme setting.
	 * Supports 'dark', 'light', and 'system' (which checks prefers-color-scheme).
	 */
	const resolveColorMode = (): 'dark' | 'light' => {
		if ($theme.includes('dark')) return 'dark';
		if ($theme === 'system') {
			return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}
		return 'light';
	};
</script>

<SvelteFlow
	{nodes}
	{nodeTypes}
	{edges}
	fitView
	minZoom={0.001}
	colorMode={resolveColorMode()}
	nodesConnectable={false}
	nodesDraggable={false}
	onnodeclick={(e) => onNodeclick?.(e.detail)}
	oninit={() => {}}
>
	<Controls showLock={false} />
	<Background variant={BackgroundVariant.Dots} />
</SvelteFlow>
