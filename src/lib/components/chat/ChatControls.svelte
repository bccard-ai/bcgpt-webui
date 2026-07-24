<script lang="ts">
	import { get } from 'svelte/store';
	import { Pane, PaneResizer } from 'paneforge';

	import { onDestroy, onMount, tick } from 'svelte';
	import type { Component } from 'svelte';
	import type { PaneAPI } from 'paneforge';
	import { showControls, showCallOverlay, showOverview, showArtifacts } from '$lib/stores';

	import Controls from './Controls/Controls.svelte';
	import CallOverlay from './MessageInput/CallOverlay.svelte';
	import Drawer from '../common/Drawer.svelte';
	import EllipsisVertical from '../icons/EllipsisVertical.svelte';
	import Artifacts from './Artifacts.svelte';

	interface HistoryMessage {
		id: string;
		role: string;
		parentId: string | null;
		childrenIds: string[];
		[key: string]: unknown;
	}

	interface HistoryType {
		messages: Record<string, HistoryMessage>;
		currentId: string | null;
		[key: string]: unknown;
	}

	interface Props {
		/** Chat history state (bindable) */
		history: HistoryType;
		/** Resolved model objects for the selected models */
		models?: unknown[];
		/** Current chat ID */
		chatId?: string | null;
		/** Files attached to the chat (bindable) */
		chatFiles?: Record<string, unknown>[];
		/** Chat parameters (bindable) */
		params?: Record<string, unknown>;
		/** Event target for chat events (TTS, streaming) */
		eventTarget: EventTarget;
		/** Submit a prompt to the chat */
		submitPrompt: (...args: unknown[]) => void;
		/** Stop the current response */
		stopResponse: () => void;
		/** Navigate to a specific message in the chat */
		showMessage: (...args: unknown[]) => void;
		/** Files attached to the current message (bindable) */
		files: Record<string, unknown>[];
		/** The primary model ID */
		modelId: string;
		/** Pane API for resizing (bindable) */
		pane: PaneAPI | null;
	}

	let {
		history = $bindable(),
		models: _models = [],
		chatId = null,
		chatFiles = $bindable([]),
		params = $bindable({}),
		eventTarget,
		submitPrompt,
		stopResponse,
		showMessage,
		files = $bindable(),
		modelId,
		pane = $bindable()
	}: Props = $props();

	/** Whether the viewport is large (>= 1024px) */
	let largeScreen = $state(false);

	/** Lazily-loaded overview component (deferred until first opened) */
	let LazyOverview = $state<Component | null>(null);

	let overviewPromise: Promise<typeof import('./Overview/OverviewWithProvider.svelte')> | null =
		null;

	$effect(() => {
		if ($showOverview && !overviewPromise) {
			overviewPromise = import('./Overview/OverviewWithProvider.svelte').then((m) => {
				LazyOverview = m.default;
				return m;
			});
		}
	});

	/** Whether the pane is currently being dragged */
	let dragged = $state(false);

	/** Minimum pane size as a percentage of the container */
	let minSize = $state(0);

	let mediaQuery: MediaQueryList | undefined;
	let resizeObserver: ResizeObserver | undefined;

	/** Open the control pane, restoring its last saved size */
	export const openPane = (): void => {
		const savedSize = parseInt(localStorage?.chatControlsSize);
		if (savedSize) {
			pane!.resize(savedSize);
		} else {
			pane!.resize(minSize);
		}
	};

	/** Handle viewport width changes between large and small screens */
	const handleMediaQuery = async (e: MediaQueryListEvent): Promise<void> => {
		largeScreen = e.matches;

		// Re-render the call overlay when screen size changes
		if (get(showCallOverlay)) {
			showCallOverlay.set(false);
			await tick();
			showCallOverlay.set(true);
		}

		if (!e.matches) {
			pane = null;
		}
	};

	const onMouseDown = (): void => {
		dragged = true;
	};

	const onMouseUp = (): void => {
		dragged = false;
	};

	/** Close all control panel views */
	const closeHandler = (): void => {
		showControls.set(false);
		showOverview.set(false);
		showArtifacts.set(false);

		if (get(showCallOverlay)) {
			showCallOverlay.set(false);
		}
	};

	onMount(() => {
		mediaQuery = window.matchMedia('(min-width: 1024px)');
		mediaQuery.addEventListener('change', handleMediaQuery);
		handleMediaQuery(mediaQuery);

		const container = document.getElementById('chat-container');
		if (!container) return;

		// Calculate the minimum pane size as a percentage of the container
		minSize = Math.floor((350 / container.clientWidth) * 100);

		resizeObserver = new ResizeObserver((entries) => {
			for (const entry of entries) {
				const width = entry.contentRect.width;
				minSize = Math.floor((350 / width) * 100);

				if (get(showControls) && pane?.isExpanded() && pane.getSize() < minSize) {
					pane.resize(minSize);
				}
			}
		});

		resizeObserver.observe(container);

		document.addEventListener('mousedown', onMouseDown);
		document.addEventListener('mouseup', onMouseUp);
	});

	onDestroy(() => {
		showControls.set(false);
		mediaQuery?.removeEventListener('change', handleMediaQuery);
		resizeObserver?.disconnect();
		document.removeEventListener('mousedown', onMouseDown);
		document.removeEventListener('mouseup', onMouseUp);
	});

	/** Close controls when the chat ID is cleared (new chat) */
	$effect(() => {
		if (!chatId) {
			closeHandler();
		}
	});
</script>

{#if !largeScreen}
	{#if $showControls}
		<Drawer
			show={$showControls}
			onClose={() => {
				showControls.set(false);
			}}
		>
			<div
				class=" {$showCallOverlay || $showOverview || $showArtifacts
					? ' h-screen  w-full'
					: 'px-6 py-4'} h-full"
			>
				{#if $showCallOverlay}
					<div
						class=" h-full max-h-[100dvh] bg-white text-gray-700 dark:bg-black dark:text-gray-300 flex justify-center"
					>
						<CallOverlay
							bind:files
							{submitPrompt}
							{stopResponse}
							{modelId}
							chatId={chatId!}
							{eventTarget}
							onClose={() => {
								showControls.set(false);
							}}
						/>
					</div>
				{:else if $showArtifacts}
					<Artifacts {history} />
				{:else if $showOverview}
					{#if LazyOverview}
						<LazyOverview
							{history}
							onNodeclick={(e: CustomEvent) => {
								showMessage(e.detail.node.data.message);
							}}
							onClose={() => {
								showControls.set(false);
							}}
						/>
					{/if}
				{:else}
					<Controls
						onClose={() => {
							showControls.set(false);
						}}
						bind:chatFiles
						bind:params
					/>
				{/if}
			</div>
		</Drawer>
	{/if}
{:else}
	{#if $showControls}
		<PaneResizer class="relative flex w-2 items-center justify-center bg-background group">
			<div class="z-10 flex h-7 w-5 items-center justify-center rounded-xs">
				<EllipsisVertical className="size-4 invisible group-hover:visible" />
			</div>
		</PaneResizer>
	{/if}

	<Pane
		bind:pane
		defaultSize={0}
		onResize={(size) => {
			if ($showControls && pane!.isExpanded()) {
				if (size < minSize) {
					pane!.resize(minSize);
				}

				localStorage.chatControlsSize = size < minSize ? 0 : size;
			}
		}}
		onCollapse={() => {
			showControls.set(false);
		}}
		collapsible={true}
		class="pt-8"
	>
		{#if $showControls}
			<div class="pr-4 pb-8 flex max-h-full min-h-full">
				<div
					class="w-full {($showOverview || $showArtifacts) && !$showCallOverlay
						? ' '
						: 'px-4 py-4 bg-white dark:shadow-lg dark:bg-gray-850  border border-gray-100 dark:border-gray-850'}  rounded-xl z-40 pointer-events-auto overflow-y-auto scrollbar-hidden"
				>
					{#if $showCallOverlay}
						<div class="w-full h-full flex justify-center">
							<CallOverlay
								bind:files
								{submitPrompt}
								{stopResponse}
								{modelId}
								chatId={chatId!}
								{eventTarget}
								onClose={() => {
									showControls.set(false);
								}}
							/>
						</div>
					{:else if $showArtifacts}
						<Artifacts {history} overlay={dragged} />
					{:else if $showOverview}
						{#if LazyOverview}
							<LazyOverview
								{history}
								onNodeclick={(e: CustomEvent) => {
									if (e.detail.node.data.message.favorite) {
										history.messages[e.detail.node.data.message.id].favorite = true;
									} else {
										history.messages[e.detail.node.data.message.id].favorite = null;
									}

									showMessage(e.detail.node.data.message);
								}}
								onClose={() => {
									showControls.set(false);
								}}
							/>
						{/if}
					{:else}
						<Controls
							onClose={() => {
								showControls.set(false);
							}}
							bind:chatFiles
							bind:params
						/>
					{/if}
				</div>
			</div>
		{/if}
	</Pane>
{/if}
