<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { fade } from 'svelte/transition';
	import { flyAndScale } from '$lib/utils/transitions';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * ConfirmDialog — modal confirmation dialog with optional text input.
	 *
	 * @example
	 * ```svelte
	 * <ConfirmDialog
	 *   bind:show
	 *   title="Delete item?"
	 *   message="This cannot be undone."
	 *   onconfirm={(value) => handleDelete(value)}
	 * />
	 * ```
	 *
	 * @props show - Bindable visibility
	 * @props title - Dialog title
	 * @props message - Body text
	 * @props cancelLabel - Label for the cancel button
	 * @props confirmLabel - Label for the confirm button
	 * @props input - Whether to show a text input
	 * @props inputPlaceholder - Placeholder for the text input
	 * @props inputValue - Bindable input value
	 */
	interface Props {
		/** Dialog title. Falls back to i18n default. */
		title?: string;
		/** Body message. Falls back to i18n default. */
		message?: string;
		/** Cancel button label. */
		cancelLabel?: string;
		/** Confirm button label. */
		confirmLabel?: string;
		/** Called with the inputValue when confirmed. */
		onconfirm?: (value: string) => unknown;
		/** Called when the dialog is cancelled. */
		onCancel?: () => unknown;
		/** Whether to show a textarea input. */
		input?: boolean;
		/** Placeholder for the textarea input. */
		inputPlaceholder?: string;
		/** Bindable value of the textarea input. */
		inputValue?: string;
		/** Bindable visibility state. */
		show?: boolean;
		/** Custom content replacing the default message body. */
		children?: import('svelte').Snippet;
	}

	let {
		title = '',
		message = '',
		cancelLabel = $i18n.t('Cancel'),
		confirmLabel = $i18n.t('Confirm'),
		onconfirm = () => {},
		onCancel = () => {},
		input = false,
		inputPlaceholder = '',
		inputValue = $bindable(''),
		show = $bindable(false),
		children
	}: Props = $props();

	let modalElement: HTMLDivElement | null = $state(null);
	let mounted = $state(false);

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			show = false;
		}
		if (event.key === 'Enter') {
			confirmHandler();
		}
	};

	const confirmHandler = async () => {
		show = false;
		await onconfirm(inputValue);
	};

	const mountPortal = () => {
		if (!modalElement) return;
		document.body.appendChild(modalElement);
		window.addEventListener('keydown', handleKeyDown);
		document.body.style.overflow = 'hidden';
	};

	const unmountPortal = () => {
		if (!modalElement) return;
		window.removeEventListener('keydown', handleKeyDown);
		if (document.body.contains(modalElement)) {
			document.body.removeChild(modalElement);
		}
		document.body.style.overflow = '';
	};

	onMount(() => {
		mounted = true;
	});

	$effect(() => {
		if (!mounted) return;
		if (show && modalElement) {
			mountPortal();
		} else if (modalElement) {
			unmountPortal();
		}
	});
</script>

{#if show}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		bind:this={modalElement}
		class=" fixed top-0 right-0 left-0 bottom-0 bg-black/60 w-full h-screen max-h-[100dvh] flex justify-center z-99999999 overflow-hidden overscroll-contain"
		in:fade={{ duration: 10 }}
		onmousedown={() => {
			show = false;
		}}
	>
		<div
			class=" m-auto rounded-2xl max-w-full w-[32rem] mx-2 bg-gray-50 dark:bg-gray-950 max-h-[100dvh] shadow-3xl"
			in:flyAndScale
			onmousedown={(e: MouseEvent) => {
				e.stopPropagation();
			}}
		>
			<div class="px-[1.75rem] py-6 flex flex-col">
				<div class=" text-lg font-semibold dark:text-gray-200 mb-2.5">
					{#if title !== ''}
						{title}
					{:else}
						{$i18n.t('Confirm your action')}
					{/if}
				</div>

				{#if children}{@render children()}{:else}
					<div class=" text-sm text-gray-500 flex-1">
						{#if message !== ''}
							{message}
						{:else}
							{$i18n.t('This action cannot be undone. Do you wish to continue?')}
						{/if}

						{#if input}
							<textarea
								bind:value={inputValue}
								placeholder={inputPlaceholder ? inputPlaceholder : $i18n.t('Enter your message')}
								class="w-full mt-2 rounded-lg px-4 py-2 text-sm dark:text-gray-300 dark:bg-gray-900 outline-hidden resize-none"
								rows="3"
								required
							></textarea>
						{/if}
					</div>
				{/if}

				<div class="mt-6 flex justify-between gap-1.5">
					<button
						class="bg-gray-100 hover:bg-gray-200 text-gray-800 dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-white font-medium w-full py-2.5 rounded-lg transition"
						onclick={() => {
							show = false;
							onCancel?.();
						}}
						type="button"
					>
						{cancelLabel}
					</button>
					<button
						class="bg-gray-900 hover:bg-gray-850 text-gray-100 dark:bg-gray-100 dark:hover:bg-white dark:text-gray-800 font-medium w-full py-2.5 rounded-lg transition"
						onclick={() => {
							confirmHandler();
						}}
						type="button"
					>
						{confirmLabel}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
