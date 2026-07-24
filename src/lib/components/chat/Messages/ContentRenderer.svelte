<script lang="ts">
	import { get } from 'svelte/store';
	import { onDestroy, onMount, tick } from 'svelte';
	import Markdown from './Markdown.svelte';
	import { chatId, mobile, showArtifacts, showControls } from '$lib/stores';
	import FloatingButtons from '../ContentRenderer/FloatingButtons.svelte';
	import { createMessagesList } from '$lib/utils';

	/** Props for the ContentRenderer component - renders message content with floating action buttons */
	interface Props {
		/** Unique message identifier */
		id: string;
		/** Raw message content (markdown) */
		content: string;
		/** Chat history object */
		history: Record<string, unknown>;
		/** Model information for feature detection */
		model?: Record<string, unknown> | null;
		/** Citation sources */
		sources?: Record<string, unknown>[] | null;
		/** Whether to enable save functionality */
		save?: boolean;
		/** Whether to show floating text-selection buttons */
		floatingButtons?: boolean;
		/** Callback when a source reference is clicked */
		onSourceClick?: (...args: unknown[]) => void;
		/** Callback when a task checkbox is toggled */
		onTaskClick?: (...args: unknown[]) => void;
		/** Callback when messages are added from floating buttons */
		onAddMessages?: (data: Record<string, unknown>) => void;
		/** Callback when content is updated */
		onUpdate?: (data: Record<string, unknown>) => void;
	}

	let {
		id,
		content,
		history,
		model = null,
		sources = null,
		save = false,
		floatingButtons = true,
		onSourceClick = () => {},
		onTaskClick = () => {},
		onAddMessages = () => {},
		onUpdate = () => {}
	}: Props = $props();

	/** Reference to the content container element */
	let contentContainerElement = $state<HTMLElement>();
	/** Reference to the floating buttons component instance */
	let floatingButtonsElement = $state<ReturnType<typeof FloatingButtons>>();

	/** Closes the floating buttons overlay */
	function closeFloatingButtons(): void {
		const buttonsContainerElement = document.getElementById(`floating-buttons-${id}`);
		if (buttonsContainerElement) {
			buttonsContainerElement.style.display = 'none';
		}

		if (floatingButtonsElement) {
			if (typeof floatingButtonsElement?.closeHandler === 'function') {
				floatingButtonsElement?.closeHandler();
			}
		}
	}

	/** Positions the floating buttons near the current text selection */
	function updateButtonPosition(event: MouseEvent): void {
		const buttonsContainerElement = document.getElementById(`floating-buttons-${id}`);
		if (
			!contentContainerElement?.contains(event.target) &&
			!buttonsContainerElement?.contains(event.target)
		) {
			closeFloatingButtons();
			return;
		}

		setTimeout(async () => {
			await tick();

			if (!contentContainerElement?.contains(event.target)) return;

			const selection = window.getSelection();

			if (selection!.toString().trim().length > 0) {
				const range = selection!.getRangeAt(0);
				const rect = range.getBoundingClientRect();
				const parentRect = contentContainerElement.getBoundingClientRect();

				const top = rect.bottom - parentRect.top;
				const left = rect.left - parentRect.left;

				if (buttonsContainerElement) {
					buttonsContainerElement.style.display = 'block';

					const spaceOnRight = parentRect.width - left;
					const halfScreenWidth = get(mobile) ? window.innerWidth / 2 : window.innerWidth / 3;

					if (spaceOnRight < halfScreenWidth) {
						const right = parentRect.right - rect.right;
						buttonsContainerElement.style.right = `${right}px`;
						buttonsContainerElement.style.left = 'auto';
					} else {
						buttonsContainerElement.style.left = `${left}px`;
						buttonsContainerElement.style.right = 'auto';
					}
					buttonsContainerElement.style.top = `${top + 5}px`;
				}
			} else {
				closeFloatingButtons();
			}
		}, 0);
	}

	/** Handles the Escape key to close floating buttons */
	function keydownHandler(e: KeyboardEvent): void {
		if (e.key === 'Escape') {
			closeFloatingButtons();
		}
	}

	/** Computes source IDs from the raw sources array for citation badge rendering */
	function computeSourceIds(
		rawSources: Record<string, unknown>[] | null,
		modelInfo: Record<string, unknown> | null
	): string[] {
		if (!rawSources) return [];

		return rawSources.reduce<string[]>((acc, s) => {
			const ids: string[] = [];
			const documents = s.document as string[];
			const metadata = s.metadata as Array<Record<string, unknown> | undefined>;

			documents.forEach((_: string, index: number) => {
				if ((modelInfo as Record<string, unknown>)?.capabilities?.citations === false) {
					ids.push('N/A');
					return;
				}

				const meta = metadata?.[index];
				const sourceId = meta?.source ?? 'N/A';

				if (meta?.name) {
					ids.push(meta.name as string);
					return;
				}

				if (sourceId.startsWith('http://') || sourceId.startsWith('https://')) {
					ids.push(sourceId);
				} else {
					ids.push((s?.source as Record<string, unknown>)?.name ?? sourceId);
				}
			});

			acc = [...acc, ...ids];
			return acc.filter((item, idx) => acc.indexOf(item) === idx);
		}, []);
	}

	onMount(() => {
		if (floatingButtons) {
			contentContainerElement?.addEventListener('mouseup', updateButtonPosition);
			document.addEventListener('mouseup', updateButtonPosition);
			document.addEventListener('keydown', keydownHandler);
		}
	});

	onDestroy(() => {
		if (floatingButtons) {
			contentContainerElement?.removeEventListener('mouseup', updateButtonPosition);
			document.removeEventListener('mouseup', updateButtonPosition);
			document.removeEventListener('keydown', keydownHandler);
		}
	});
</script>

<div bind:this={contentContainerElement}>
	<Markdown
		{id}
		{content}
		{model}
		{save}
		sourceIds={computeSourceIds(sources, model?.info as Record<string, unknown> | null)}
		{onSourceClick}
		{onTaskClick}
		onUpdate={(data) => {
			onUpdate?.(data);
		}}
		onCode={(data) => {
			const { lang, code } = data as { lang: string; code: string };

			if (
				(['html', 'svg'].includes(lang) || (lang === 'xml' && code.includes('svg'))) &&
				!$mobile &&
				$chatId
			) {
				showArtifacts.set(true);
				showControls.set(true);
			}
		}}
	/>
</div>

{#if floatingButtons && model}
	<FloatingButtons
		bind:this={floatingButtonsElement}
		{id}
		model={(model as Record<string, unknown>)?.id as string}
		messages={createMessagesList(history, id)}
		onAdd={({ modelId, parentId, messages }: Record<string, unknown>) => {
			onAddMessages({ modelId, parentId, messages });
			closeFloatingButtons();
		}}
	/>
{/if}
