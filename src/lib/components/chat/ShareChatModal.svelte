<script lang="ts">
	import { get } from 'svelte/store';
	import { getContext } from 'svelte';
	import { resolve } from '$app/paths';
	import { models, config } from '$lib/stores';

	import { toast } from 'svelte-sonner';
	import { deleteSharedChatById, getChatById, shareChatById } from '$lib/apis/chats';
	import { copyToClipboard } from '$lib/utils';

	import Modal from '../common/Modal.svelte';
	import Link from '../icons/Link.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface ChatRecord {
		id: string;
		share_id?: string;
		chat?: {
			models?: string[];
			[key: string]: unknown;
		};
		[key: string]: unknown;
	}

	interface Props {
		/** The chat ID to share */
		chatId: string;
		/** Controls modal visibility */
		show?: boolean;
	}

	let { chatId, show = $bindable(false) }: Props = $props();

	/** The loaded chat record */
	let chat = $state<ChatRecord | null>(null);

	/** The generated share URL after sharing */
	let shareUrl: string | null = $state(null);

	/**
	 * Share the chat locally by creating a shared link via the API.
	 * Returns the share URL string.
	 */
	const shareLocalChat = async (): Promise<string | null> => {
		const sharedChat = await shareChatById('', chatId);
		shareUrl = `${window.location.origin}/s/${sharedChat.id}`;
		chat = await getChatById('', chatId);
		return shareUrl;
	};

	/**
	 * Share the chat to the BCGPT community by opening a new tab
	 * and posting the chat data via window.postMessage.
	 */
	const shareToCommunity = async (): Promise<void> => {
		if (!chat?.chat) return;

		toast.success($i18n.t('Redirecting you to BCGPT Community'));
		const url = 'https://BCGPT.com';

		const tab = window.open(`${url}/chats/upload`, '_blank');
		if (!tab) {
			toast.error($i18n.t('Failed to open sharing window. Please allow popups.'));
			return;
		}

		window.addEventListener(
			'message',
			(event) => {
				if (event.origin !== url) return;
				if (event.data === 'loaded') {
					tab.postMessage(
						JSON.stringify({
							chat: chat!.chat,
							models: get(models).filter((m) => chat!.chat?.models?.includes(m.id))
						}),
						'*'
					);
				}
			},
			false
		);
	};

	/**
	 * Check if the fetched chat differs from the currently loaded one.
	 * Prevents unnecessary state updates when the same chat is re-fetched.
	 */
	const isDifferentChat = (newChat: ChatRecord | null): boolean => {
		if (!chat) return true;
		if (!newChat) return false;
		return chat.id !== newChat.id || chat.share_id !== newChat.share_id;
	};

	/** Load chat data when the modal opens */
	$effect(() => {
		if (show) {
			(async () => {
				if (chatId) {
					const fetched = await getChatById('', chatId);
					if (isDifferentChat(fetched)) {
						chat = fetched;
					}
				} else {
					chat = null;
				}
			})();
		}
	});
</script>

<Modal bind:show size="md">
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-0.5">
			<div class=" text-lg font-medium self-center">{$i18n.t('Share Chat')}</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				onclick={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		{#if chat}
			<div class="px-5 pt-4 pb-5 w-full flex flex-col justify-center">
				<div class=" text-sm dark:text-gray-300 mb-1">
					{#if chat.share_id}
						<a href={resolve(`/s/${chat.share_id}`)} target="_blank"
							>{$i18n.t('You have shared this chat')}
							<span class=" underline">{$i18n.t('before')}</span>.</a
						>
						{$i18n.t('Click here to')}
						<button
							class="underline"
							onclick={async () => {
								const res = await deleteSharedChatById('', chatId);
								if (res) {
									chat = await getChatById('', chatId);
								}
							}}
							>{$i18n.t('delete this link')}
						</button>
						{$i18n.t('and create a new shared link.')}
					{:else}
						{$i18n.t(
							"Messages you send after creating your link won't be shared. Users with the URL will be able to view the shared chat."
						)}
					{/if}
				</div>

				<div class="flex justify-end">
					<div class="flex flex-col items-end space-x-1 mt-3">
						<div class="flex gap-1">
							{#if $config?.features.enable_community_sharing}
								<button
									class="self-center flex items-center gap-1 px-3.5 py-2 text-sm font-medium bg-gray-100 hover:bg-gray-200 text-gray-800 dark:bg-gray-850 dark:text-white dark:hover:bg-gray-800 transition rounded-full"
									type="button"
									onclick={() => {
										shareToCommunity();
										show = false;
									}}
								>
									{$i18n.t('Share to BCGPT Community')}
								</button>
							{/if}

							<button
								class="self-center flex items-center gap-1 px-3.5 py-2 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
								type="button"
								id="copy-and-share-chat-button"
								onclick={async () => {
									const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

									if (isSafari) {
										const getUrlPromise = async () => {
											const url = await shareLocalChat();
											return new Blob([url ?? ''], { type: 'text/plain' });
										};

										navigator.clipboard
											.write([
												new ClipboardItem({
													'text/plain': getUrlPromise
												})
											])
											.then(() => {
												return true;
											})
											.catch(() => {
												return false;
											});
									} else {
										copyToClipboard((await shareLocalChat()) ?? '');
									}

									toast.success($i18n.t('Copied shared chat URL to clipboard!'));
									show = false;
								}}
							>
								<Link />

								{#if chat.share_id}
									{$i18n.t('Update and Copy Link')}
								{:else}
									{$i18n.t('Copy Link')}
								{/if}
							</button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</Modal>
