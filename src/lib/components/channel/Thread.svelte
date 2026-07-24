<script lang="ts">
	import { get } from 'svelte/store';

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import { socket, user } from '$lib/stores';

	import { getChannelThreadMessages, sendMessage } from '$lib/apis/channels';

	import XMark from '$lib/components/icons/XMark.svelte';
	import MessageInput from './MessageInput.svelte';
	import Messages from './Messages.svelte';
	import { onDestroy, onMount, tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Channel {
		id: string;
		name: string;
		created_at: number;
		[key: string]: unknown;
	}

	interface ChannelMessage {
		id: string;
		user_id: string;
		channel_id: string;
		content: string;
		parent_id?: string | null;
		reactions: { name: string; user_ids: string[]; count: number }[];
		[key: string]: unknown;
	}

	interface TypingUser {
		id: string;
		name: string;
	}

	/**
	 * Thread view component for displaying and interacting with message threads
	 * within a channel. Handles real-time updates via socket events.
	 *
	 * @example
	 * ```svelte
	 * <Thread threadId="msg-123" channel={channelData} onClose={() => {}} />
	 * ```
	 *
	 * @param threadId - The ID of the parent message for the thread.
	 * @param channel - The channel object the thread belongs to.
	 * @param onClose - Callback invoked when the thread is closed.
	 */
	interface Props {
		threadId?: string | null;
		channel?: Channel | null;
		onClose?: () => void;
	}

	let { threadId = null, channel = null, onClose = () => {} }: Props = $props();

	let messages = $state<ChannelMessage[] | null>(null);
	let top = $state(false);

	let typingUsers = $state<TypingUser[]>([]);
	let typingUsersTimeout: Record<string, ReturnType<typeof setTimeout>> = {};

	let messagesContainerElement = $state<HTMLElement | null>(null);

	const scrollToBottom = () => {
		if (messagesContainerElement) {
			messagesContainerElement.scrollTop = messagesContainerElement.scrollHeight;
		}
	};

	const initHandler = async () => {
		messages = null;
		top = false;

		typingUsers = [];
		typingUsersTimeout = {};

		if (channel) {
			messages = await getChannelThreadMessages('', channel.id, threadId ?? '');

			if (messages.length < 50) {
				top = true;
			}

			await tick();
			scrollToBottom();
		} else {
			goto(resolve('/'));
		}
	};

	const channelEventHandler = async (event: Record<string, unknown>) => {
		if (event.channel_id === channel?.id) {
			const type = (event?.data as Record<string, unknown> | undefined)?.type ?? null;
			const data = ((event?.data as Record<string, unknown> | undefined)?.data ?? null) as ChannelMessage | null;

			if (type === 'message') {
				if ((data?.parent_id ?? null) === threadId) {
					if (messages) {
						messages = [data!, ...messages];

						if (typingUsers.find((u) => u.id === (event.user as { id: string }).id)) {
							typingUsers = typingUsers.filter((u) => u.id !== (event.user as { id: string }).id);
						}
					}
				}
			} else if (type === 'message:update') {
				if (messages && data) {
					const idx = messages.findIndex((message) => message.id === data.id);

					if (idx !== -1) {
						messages[idx] = data;
					}
				}
			} else if (type === 'message:delete') {
				if (messages && data) {
					messages = messages.filter((message) => message.id !== data.id);
				}
			} else if (typeof type === 'string' && type.includes('message:reaction')) {
				if (messages && data) {
					const idx = messages.findIndex((message) => message.id === data.id);
					if (idx !== -1) {
						messages[idx] = data;
					}
				}
			} else if (type === 'typing' && event.message_id === threadId) {
				const eventUser = event.user as { id: string; name: string };
				if (eventUser.id === get(user).id) {
					return;
				}

				typingUsers = data?.typing
					? [
							...typingUsers,
							...(typingUsers.find((u) => u.id === eventUser.id)
								? []
								: [
										{
											id: eventUser.id,
											name: eventUser.name
										}
									])
						]
					: typingUsers.filter((u) => u.id !== eventUser.id);

				if (typingUsersTimeout[eventUser.id]) {
					clearTimeout(typingUsersTimeout[eventUser.id]);
				}

				typingUsersTimeout[eventUser.id] = setTimeout(() => {
					typingUsers = typingUsers.filter((u) => u.id !== eventUser.id);
				}, 5000);
			}
		}
	};

	const submitHandler = async ({ content, data }: { content: string; data: Record<string, unknown> }) => {
		if (!content) {
			return;
		}

		await sendMessage('', channel!.id, {
			parent_id: threadId ?? undefined,
			content: content,
			data: data
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	};

	const onChange = async () => {
		get(socket)?.emit('channel-events', {
			channel_id: channel!.id,
			message_id: threadId,
			data: {
				type: 'typing',
				data: {
					typing: true
				}
			}
		});
	};

	onMount(() => {
		get(socket)?.on('channel-events', channelEventHandler);
	});

	onDestroy(() => {
		get(socket)?.off('channel-events', channelEventHandler);
	});

	$effect(() => {
		if (threadId) {
			initHandler();
		}
	});
</script>

{#if channel}
	<div class="flex flex-col w-full h-full bg-gray-50 dark:bg-gray-850">
		<div class="flex items-center justify-between px-3.5 pt-3">
			<div class=" font-medium text-lg">{$i18n.t('Thread')}</div>

			<div>
				<button
					class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 p-2"
					onclick={() => {
						onClose();
					}}
				>
					<XMark />
				</button>
			</div>
		</div>

		<div class=" max-h-full w-full overflow-y-auto pt-3" bind:this={messagesContainerElement}>
			<Messages
				id={threadId}
				{channel}
				messages={messages ?? undefined}
				{top}
				thread={true}
				onLoad={async () => {
					const newMessages = await getChannelThreadMessages(
						'',
						channel!.id,
						threadId ?? '',
						messages!.length
					);

					messages = [...messages!, ...newMessages];

					if (newMessages.length < 50) {
						top = true;
						return;
					}
				}}
			/>

			<div class=" pb-[1rem]">
				<MessageInput id={threadId} {typingUsers} {onChange} onSubmit={submitHandler} />
			</div>
		</div>
	</div>
{/if}
