<script lang="ts">
	import { onDestroy } from 'svelte';
	import { fly } from 'svelte/transition';
	import { isApp } from '$lib/stores';

	/**
	 * Drawer — slide-up panel that overlays the viewport.
	 *
	 * @example
	 * ```svelte
	 * <Drawer bind:show onClose={() => console.log('closed')}>
	 *   <p>Drawer content</p>
	 * </Drawer>
	 * ```
	 *
	 * @props show - Bindable visibility state
	 * @props className - Additional classes for the content panel
	 * @props onClose - Callback fired when the drawer closes
	 */
	interface Props {
		/** Bindable visibility state. */
		show?: boolean;
		/** CSS classes applied to the inner content panel. */
		className?: string;
		/** Content rendered inside the drawer. */
		children?: import('svelte').Snippet;
		/** Callback fired after the drawer closes. */
		onClose?: (...args: unknown[]) => void;
	}

	let { show = $bindable(false), className = '', children, onClose = () => {} }: Props = $props();

	let modalElement: HTMLDivElement | null = $state(null);

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
		onClose?.();
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
		if (modalElement && document.body.contains(modalElement)) {
			document.body.removeChild(modalElement);
		}
		document.body.style.overflow = '';
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->

<div
	bind:this={modalElement}
	class="modal fixed right-0 {$isApp
		? ' ml-[4.5rem] max-w-[calc(100%-4.5rem)]'
		: ''} left-0 bottom-0 bg-black/60 w-full h-screen max-h-[100dvh] flex justify-center z-999 overflow-hidden overscroll-contain"
	in:fly={{ y: 100, duration: 100 }}
	onmousedown={() => {
		show = false;
	}}
>
	<div
		class=" mt-auto w-full bg-gray-50 dark:bg-gray-900 dark:text-gray-100 {className} max-h-[100dvh] overflow-y-auto scrollbar-hidden"
		onmousedown={(e: MouseEvent) => {
			e.stopPropagation();
		}}
	>
		{@render children?.()}
	</div>
</div>

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
