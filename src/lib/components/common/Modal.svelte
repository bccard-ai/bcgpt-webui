<script lang="ts">
	import { onDestroy } from 'svelte';
	import { fade } from 'svelte/transition';
	import { flyAndScale } from '$lib/utils/transitions';

	/**
	 * Modal — full-screen overlay dialog with size variants and ESC-to-close.
	 *
	 * @example
	 * ```svelte
	 * <Modal bind:show size="md">
	 *   <p>Modal content here</p>
	 * </Modal>
	 * ```
	 *
	 * @props show - Bindable visibility state
	 * @props size - Width preset: 'xs' | 'sm' | 'md' | 'lg' | 'full'
	 * @props containerClassName - Classes on the backdrop overlay
	 * @props className - Classes on the content panel
	 */
	interface Props {
		/** Bindable visibility state. Defaults to `true`. */
		show?: boolean;
		/** Width preset. `'xs'` = 16rem, `'sm'` = 30rem, `'md'` = 42rem, `'lg'` = 56rem, `'full'` = 100%. */
		size?: 'xs' | 'sm' | 'md' | 'lg' | 'full';
		/** CSS classes applied to the backdrop container. */
		containerClassName?: string;
		/** CSS classes applied to the content panel. */
		className?: string;
		/** Optional id for the content panel. */
		contentId?: string;
		/** Id of the visible element that labels the dialog. */
		ariaLabelledby?: string;
		/** Direct accessible name when no visible label id exists. */
		ariaLabel?: string;
		/** Content rendered inside the modal. */
		children?: import('svelte').Snippet;
	}

	let {
		show = $bindable(true),
		size = 'md',
		containerClassName = 'p-3',
		className = 'bg-gray-50 dark:bg-gray-900 rounded-2xl',
		contentId = undefined,
		ariaLabelledby = undefined,
		ariaLabel = undefined,
		children
	}: Props = $props();

	let modalElement: HTMLDivElement | null = $state(null);

	const SIZE_MAP: Record<string, string> = {
		xs: 'w-[16rem]',
		sm: 'w-[30rem]',
		md: 'w-[42rem]',
		lg: 'w-[56rem]',
		full: 'w-full'
	};

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape' && isTopModal()) {
			show = false;
		}
	};

	const isTopModal = (): boolean => {
		const modals = document.getElementsByClassName('modal');
		return modals.length > 0 && modals[modals.length - 1] === modalElement;
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

	$effect(() => {
		if (show && modalElement) {
			mountPortal();
		} else if (modalElement) {
			unmountPortal();
		}
	});

	onDestroy(() => {
		show = false;
		unmountPortal();
	});
</script>

{#if show}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		bind:this={modalElement}
		class="modal fixed top-0 right-0 left-0 bottom-0 bg-black/60 w-full h-screen max-h-[100dvh] {containerClassName} flex justify-center z-9999 overflow-y-auto overscroll-contain"
		in:fade={{ duration: 10 }}
		onmousedown={() => {
			show = false;
		}}
	>
		<div
			id={contentId}
			role={ariaLabelledby || ariaLabel ? 'dialog' : undefined}
			aria-modal={ariaLabelledby || ariaLabel ? 'true' : undefined}
			aria-labelledby={ariaLabelledby}
			aria-label={ariaLabel}
			class="m-auto max-w-full {SIZE_MAP[size] ?? SIZE_MAP.md} {size !== 'full'
				? 'mx-2'
				: ''} shadow-3xl min-h-fit scrollbar-hidden {className}"
			in:flyAndScale
			onmousedown={(e: MouseEvent) => {
				e.stopPropagation();
			}}
		>
			{@render children?.()}
		</div>
	</div>
{/if}

<style>
	.modal-content {
		animation: scaleUp 0.1s ease-out forwards;
	}

	@keyframes scaleUp {
		from {
			transform: scale(0.985);
			opacity: 0;
		}
		to {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
