<script lang="ts">
	import { get } from 'svelte/store';
	import { settings, playingNotificationSound, isLastActiveTab } from '$lib/stores';
	import DOMPurify from 'dompurify';

	import { marked } from 'marked';
	import { onMount } from 'svelte';

	/**
	 * A notification toast component that displays a title and markdown-rendered content.
	 * Plays a notification sound on mount if enabled in settings and the tab is active.
	 *
	 * @example
	 * ```svelte
	 * <NotificationToast
	 *   title="New Message"
	 *   content="You have a **new** message from Alice."
	 *   onClick={() => navigateToMessage()}
	 *   onCloseToast={() => dismissToast()}
	 * />
	 * ```
	 *
	 * @param onClick - Callback when the toast is clicked.
	 * @param onCloseToast - Callback when the toast is dismissed.
	 * @param title - The notification title.
	 * @param content - The notification content (supports markdown).
	 */
	interface Props {
		onClick?: () => void;
		onCloseToast?: () => void;
		title?: string;
		content: string;
	}

	let { onClick = () => {}, onCloseToast = () => {}, title = 'HI', content }: Props = $props();

	onMount(() => {
		if (!navigator.userActivation.hasBeenActive) {
			return;
		}

		if (get(settings)?.notificationSound ?? true) {
			if (!get(playingNotificationSound) && get(isLastActiveTab)) {
				playingNotificationSound.set(true);

				const audio = new Audio(`/audio/notification.mp3`);
				audio.play().finally(() => {
					playingNotificationSound.set(false);
				});
			}
		}
	});
</script>

<button
	class="flex gap-2.5 text-left min-w-[var(--width)] w-full dark:bg-gray-850 dark:text-white bg-white text-black border border-gray-100 dark:border-gray-850 rounded-xl px-3.5 py-3.5"
	onclick={() => {
		onClick();
		onCloseToast?.();
	}}
>
	<div class="shrink-0 self-top -translate-y-0.5">
		<img src="/static/favicon.png" alt="favicon" class="size-7 rounded-full" />
	</div>

	<div>
		{#if title}
			<div class=" text-[13px] font-medium mb-0.5 line-clamp-1 capitalize">{title}</div>
		{/if}

		<div class=" line-clamp-2 text-xs self-center dark:text-gray-300 font-normal">
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: marked output is DOMPurify-sanitized -->
			{@html DOMPurify.sanitize(marked.parse(content) as string)}
		</div>
	</div>
</button>
