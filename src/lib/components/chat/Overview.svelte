<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import { useSvelteFlow, useNodesInitialized, useStore } from '@xyflow/svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { onMount, tick } from 'svelte';

	import { get, writable } from 'svelte/store';
	import { models, showOverview, user } from '$lib/stores';

	import '@xyflow/svelte/dist/style.css';

	import CustomNode from './Overview/Node.svelte';
	import Flow from './Overview/Flow.svelte';
	import XMark from '../icons/XMark.svelte';
	import ArrowLeft from '../icons/ArrowLeft.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const { width, height } = useStore();
	const { fitView } = useSvelteFlow();
	const nodesInitialized = useNodesInitialized();

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

	let { history, onClose = () => {}, onNodeclick = () => {} }: Props = $props();

	/** Currently selected message ID for view focusing */
	let selectedMessageId = $state<string | null>(null);

	/** Writable stores for xyflow nodes and edges */
	const nodes = writable([]);
	const edges = writable([]);

	/** Custom node type mapping for the flow renderer */
	const nodeTypes = { custom: CustomNode };

	/** Layout constants for flow visualization */
	const LAYOUT = {
		LEVEL_OFFSET: 150,
		SIBLING_OFFSET: 250
	} as const;

	/**
	 * Focus the view on the selected message or the current history position.
	 * Resets selectedMessageId after focusing.
	 */
	const focusNode = async (): Promise<void> => {
		const targetId = selectedMessageId ?? history.currentId;
		if (targetId) {
			await fitView({ nodes: [{ id: targetId }] });
		}
		selectedMessageId = null;
	};

	/**
	 * Recursively check if a given node is an ancestor of the current node.
	 * Used to highlight the active path through the conversation tree.
	 */
	const isAncestorOf = (nodeId: string, currentId: string | null): boolean => {
		const node = history.messages[nodeId];
		if (!node?.childrenIds) return false;
		return node.childrenIds.some((id) => id === currentId || isAncestorOf(id, currentId));
	};

	/**
	 * Build the flow graph from chat history.
	 * Creates nodes with positions and edges connecting parent-child messages.
	 */
	const drawFlow = async (): Promise<void> => {
		const nodeList: unknown[] = [];
		const edgeList: unknown[] = [];

		/** Position map tracking each message's level and position within that level */
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local computation Map, not reactive state
		const positionMap = new Map<string, { id: string; level: number; position: number }>();
		const layerWidths: Record<number, number> = {};

		// First pass: compute level and position for each message
		Object.keys(history.messages).forEach((id) => {
			const message = history.messages[id];
			const level = message.parentId ? (positionMap.get(message.parentId)?.level ?? -1) + 1 : 0;
			if (!layerWidths[level]) layerWidths[level] = 0;

			positionMap.set(id, {
				id: message.id,
				level,
				position: layerWidths[level]++
			});
		});

		// Second pass: create nodes and edges
		Object.keys(history.messages).forEach((id) => {
			const pos = positionMap.get(id);
			if (!pos) return;

			nodeList.push({
				id: pos.id,
				type: 'custom',
				data: {
					user: get(user),
					message: history.messages[id],
					model: get(models).find((model) => model.id === history.messages[id].model)
				},
				position: {
					x: pos.position * LAYOUT.SIBLING_OFFSET,
					y: pos.level * LAYOUT.LEVEL_OFFSET
				}
			});

			const parentId = history.messages[id].parentId;
			if (parentId) {
				edgeList.push({
					id: `${parentId}-${pos.id}`,
					source: parentId,
					target: pos.id,
					selectable: false,
					class: ' dark:fill-gray-300 fill-gray-300',
					type: 'smoothstep',
					animated: history.currentId === id || isAncestorOf(id, history.currentId)
				});
			}
		});

		await edges.set([...edgeList]);
		await nodes.set([...nodeList]);
	};

	onMount(() => {
		drawFlow();

		nodesInitialized.subscribe(async (initialized) => {
			if (initialized) {
				await tick();
				if (history.currentId) {
					await fitView({ nodes: [{ id: history.currentId }] });
				}
			}
		});

		width.subscribe((value) => {
			if (value && history.currentId) {
				fitView({ nodes: [{ id: history.currentId }] });
			}
		});

		height.subscribe((value) => {
			if (value && history.currentId) {
				fitView({ nodes: [{ id: history.currentId }] });
			}
		});
	});

	onDestroy(() => {
		nodes.set([]);
		edges.set([]);
	});

	/** Redraw the flow whenever history changes */
	$effect(() => {
		if (history) {
			drawFlow();
		}
	});

	/** Focus on the current node whenever the current position changes */
	$effect(() => {
		if (history && history.currentId) {
			focusNode();
		}
	});
</script>

<div class="w-full h-full relative">
	<div class=" absolute z-50 w-full flex justify-between dark:text-gray-100 px-4 py-3.5">
		<div class="flex items-center gap-2.5">
			<button
				class="self-center p-0.5"
				onclick={() => {
					showOverview.set(false);
				}}
			>
				<ArrowLeft className="size-3.5" />
			</button>
			<div class=" text-lg font-medium self-center font-primary">{$i18n.t('Chat Overview')}</div>
		</div>
		<button
			class="self-center p-0.5"
			onclick={() => {
				onClose?.();
				showOverview.set(false);
			}}
		>
			<XMark className="size-3.5" />
		</button>
	</div>

	{#if $nodes.length > 0}
		<Flow
			{nodes}
			{nodeTypes}
			{edges}
			onNodeclick={(e: CustomEvent) => {
				onNodeclick?.(e.detail);
				selectedMessageId = e.detail.node.data.message.id;
				fitView({ nodes: [{ id: selectedMessageId }] });
			}}
		/>
	{/if}
</div>
