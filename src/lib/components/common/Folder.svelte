<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	import ChevronDown from '../icons/ChevronDown.svelte';
	import ChevronRight from '../icons/ChevronRight.svelte';
	import Collapsible from './Collapsible.svelte';
	import Tooltip from './Tooltip.svelte';
	import Plus from '../icons/Plus.svelte';

	/**
	 * Folder — collapsible folder container with optional drag-and-drop and add button.
	 *
	 * @example
	 * ```svelte
	 * <Folder name="My Folder" bind:open onDrop={handleDrop}>
	 *   <ChatItem ... />
	 * </Folder>
	 * ```
	 *
	 * @props open - Bindable expanded state
	 * @props name - Folder display name
	 * @props collapsible - Whether the folder can be collapsed
	 * @props onAdd - Callback for the add button (null hides the button)
	 * @props onAddLabel - Tooltip label for the add button
	 * @props dragAndDrop - Enable drag-and-drop events
	 */
	interface Props {
		/** Bindable expanded state. Defaults to `true`. */
		open?: boolean;
		/** HTML id attribute. */
		id?: string;
		/** Folder display name. */
		name?: string;
		/** Whether the folder can be collapsed. Defaults to `true`. */
		collapsible?: boolean;
		/** Tooltip label for the add button. */
		onAddLabel?: string;
		/** Callback for the add button. `null` hides the button. */
		onAdd?: null | (() => void);
		/** Enable drag-and-drop events. Defaults to `true`. */
		dragAndDrop?: boolean;
		/** CSS classes on the wrapper div. */
		className?: string;
		/** Folder children content. */
		children?: import('svelte').Snippet;
		/** Called on import. */
		onImport?: (...args: unknown[]) => void;
		/** Called when items are dropped onto the folder. */
		onDrop?: (...args: unknown[]) => void;
		/** Called when open state changes. */
		onchange?: (...args: unknown[]) => void;
	}

	let {
		open = $bindable(true),
		name = '',
		collapsible = true,
		onAddLabel = '',
		onAdd = null,
		dragAndDrop = true,
		className = '',
		children,
		onDrop = () => {},
		onchange = () => {}
	}: Props = $props();

	let folderElement: HTMLElement = $state();
	let draggedOver = $state(false);

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		draggedOver = true;
	};

	const onDragLeave = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		draggedOver = false;
	};

	onMount(() => {
		if (!dragAndDrop || !folderElement) return;
		folderElement.addEventListener('dragover', onDragOver);
		folderElement.addEventListener('drop', onDrop);
		folderElement.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		if (!dragAndDrop || !folderElement) return;
		folderElement.removeEventListener('dragover', onDragOver);
		folderElement.removeEventListener('drop', onDrop);
		folderElement.removeEventListener('dragleave', onDragLeave);
	});
</script>

<div bind:this={folderElement} class="relative {className}">
	{#if draggedOver}
		<div
			class="absolute top-0 left-0 w-full h-full rounded-xs bg-gray-100/50 dark:bg-gray-700/20 bg-opacity-50 dark:bg-opacity-10 z-50 pointer-events-none touch-none"
		></div>
	{/if}

	{#if collapsible}
		<Collapsible
			bind:open
			className="w-full "
			buttonClassName="w-full"
			onchange={(state: unknown) => {
				onchange?.((state as CustomEvent).detail);
			}}
		>
			<div
				class="w-full group rounded-md relative flex items-center justify-between hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-500 dark:text-gray-500 transition"
			>
				<button class="w-full py-1.5 pl-2 flex items-center gap-1.5 text-xs font-medium">
					<div class="text-gray-300 dark:text-gray-600">
						{#if open}
							<ChevronDown className=" size-3" strokeWidth="2.5" />
						{:else}
							<ChevronRight className=" size-3" strokeWidth="2.5" />
						{/if}
					</div>

					<div class="translate-y-[0.5px]">
						{name}
					</div>
				</button>

				{#if onAdd}
					<button
						class="absolute z-10 right-2 invisible group-hover:visible self-center flex items-center dark:text-gray-300"
						onpointerup={(e: PointerEvent) => {
							e.stopPropagation();
						}}
						onclick={(e: MouseEvent) => {
							e.stopPropagation();
							onAdd();
						}}
					>
						<Tooltip content={onAddLabel}>
							<button
								class="p-0.5 dark:hover:bg-gray-850 rounded-lg touch-auto"
								onclick={(_e: MouseEvent) => {}}
							>
								<Plus className=" size-3" strokeWidth="2.5" />
							</button>
						</Tooltip>
					</button>
				{/if}
			</div>

			{#snippet content()}
				<div class="w-full">
					{@render children?.()}
				</div>
			{/snippet}
		</Collapsible>
	{:else}
		{@render children?.()}
	{/if}
</div>
