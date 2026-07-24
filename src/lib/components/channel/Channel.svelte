<script lang="ts">
	import { get } from 'svelte/store';

	import { toast } from 'svelte-sonner';
	import { Pane, PaneGroup, PaneResizer } from 'paneforge';

	import { onDestroy, onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import { chatId, showSidebar, socket, user } from '$lib/stores';
	import { getChannelById, getChannelMessages, sendMessage } from '$lib/apis/channels';

	import Messages from './Messages.svelte';
	import MessageInput from './MessageInput.svelte';
	import Navbar from './Navbar.svelte';
	import Drawer from '../common/Drawer.svelte';
	import EllipsisVertical from '../icons/EllipsisVertical.svelte';
	import Thread from './Thread.svelte';

	/**
	 * Main channel view component that handles real-time messaging,
	 * typing indicators, thread management, and responsive layout.
	 *
	 * @example
	 * ```svelte
	 * <Channel id="channel-123" />
	 * ```
	 *
	 * @param id - The channel ID to load and display.
	 */
	interface Props {
		id?: string;
	}

	interface Channel {
		id: string;
		name: string;
		created_at: number;
		[key: string]: unknown;
	}

	interface Reaction {
		name: string;
		user_ids: string[];
		count: number;
	}

	interface ChannelMessage {
		id: string;
		user_id: string;
		channel_id: string;
		content: string;
		reactions: Reaction[];
		[key: string]: unknown;
	}

	interface TypingUser {
		id: string;
		name: string;
	}

	let { id = '' }: Props = $props();

	let scrollEnd = $state(true);
	let messagesContainerElement = $state<HTMLElement | null>(null);

	let top = $state(false);

	let channel = $state<Channel | null>(null);
	let messages = $state<ChannelMessage[] | null>(null);

	let threadId = $state<string | null>(null);

	let typingUsers = $state<TypingUser[]>([]);
	let typingUsersTimeout: Record<string, ReturnType<typeof setTimeout>> = {};

	const scrollToBottom = () => {
		if (messagesContainerElement) {
			messagesContainerElement.scrollTop = messagesContainerElement.scrollHeight;
		}
	};

	const initHandler = async () => {
		top = false;
		messages = null;
		channel = null;
		threadId = null;

		typingUsers = [];
		typingUsersTimeout = {};

		channel = (await getChannelById('', id).catch((_error) => {
			return null;
		})) as Channel | null;

		if (channel) {
			messages = (await getChannelMessages('', id, 0)) as ChannelMessage[];

			if (messages) {
				scrollToBottom();

				if (messages.length < 50) {
					top = true;
				}
			}
		} else {
			goto(resolve('/'));
		}
	};

	const channelEventHandler = async (event: {
		channel_id: string;
		message_id?: string | null;
		user: { id: string; name: string };
		data?: { type?: string | null; data?: Record<string, unknown> | null };
	}) => {
		if (event.channel_id === id) {
			const type = event?.data?.type ?? null;
			const data = (event?.data?.data ?? null) as ChannelMessage | null;

			if (type === 'message') {
				if ((data?.parent_id ?? null) === null && data) {
					messages = [data, ...(messages ?? [])];

					if (typingUsers.find((u) => u.id === event.user.id)) {
						typingUsers = typingUsers.filter((u) => u.id !== event.user.id);
					}

					await tick();
					if (scrollEnd) {
						scrollToBottom();
					}
				}
			} else if (type === 'message:update') {
				const idx = (messages ?? []).findIndex((message) => message.id === data?.id);

				if (idx !== -1 && messages && data) {
					messages[idx] = data;
				}
			} else if (type === 'message:delete') {
				messages = (messages ?? []).filter((message) => message.id !== data?.id);
			} else if (type === 'message:reply') {
				const idx = (messages ?? []).findIndex((message) => message.id === data?.id);

				if (idx !== -1 && messages && data) {
					messages[idx] = data;
				}
			} else if (type?.includes('message:reaction')) {
				const idx = (messages ?? []).findIndex((message) => message.id === data?.id);
				if (idx !== -1 && messages && data) {
					messages[idx] = data;
				}
			} else if (type === 'typing' && event.message_id === null) {
				if (event.user.id === get(user).id) {
					return;
				}

				typingUsers = data?.typing
					? [
							...typingUsers,
							...(typingUsers.find((u) => u.id === event.user.id)
								? []
								: [
										{
											id: event.user.id,
											name: event.user.name
										}
									])
						]
					: typingUsers.filter((u) => u.id !== event.user.id);

				if (typingUsersTimeout[event.user.id]) {
					clearTimeout(typingUsersTimeout[event.user.id]);
				}

				typingUsersTimeout[event.user.id] = setTimeout(() => {
					typingUsers = typingUsers.filter((u) => u.id !== event.user.id);
				}, 5000);
			}
		}
	};

	const submitHandler = async ({ content, data }: { content: string; data: Record<string, unknown> }) => {
		if (!content && (data?.files ?? []).length === 0) {
			return;
		}

		const res = await sendMessage('', id, { content: content, data: data }).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			messagesContainerElement!.scrollTop = messagesContainerElement!.scrollHeight;
		}
	};

	const onChange = async () => {
		get(socket)?.emit('channel-events', {
			channel_id: id,
			message_id: null,
			data: {
				type: 'typing',
				data: {
					typing: true
				}
			}
		});
	};

	let mediaQuery: MediaQueryList | undefined;
	let largeScreen = $state(false);

	onMount(() => {
		if (get(chatId)) {
			chatId.set('');
		}

		get(socket)?.on('channel-events', channelEventHandler);

		mediaQuery = window.matchMedia('(min-width: 1024px)');

		const handleMediaQuery = async (e: MediaQueryListEvent) => {
			if (e.matches) {
				largeScreen = true;
			} else {
				largeScreen = false;
			}
		};

		mediaQuery.addEventListener('change', handleMediaQuery);
		handleMediaQuery(mediaQuery);
	});

	onDestroy(() => {
		get(socket)?.off('channel-events', channelEventHandler);
	});

	$effect(() => {
		if (id) {
			initHandler();
		}
	});
</script>

<svelte:head>
	<title>#{channel?.name ?? 'Channel'} | BCGPT</title>
</svelte:head>

<div
	class="h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-260px)]'
		: ''} w-full max-w-full flex flex-col"
	id="channel-container"
>
	<PaneGroup direction="horizontal" class="w-full h-full">
		<Pane defaultSize={50} minSize={50} class="h-full flex flex-col w-full relative">
			<Navbar {channel} />

			<div class="flex-1 overflow-y-auto">
				{#if channel}
					<div
						class=" pb-2.5 max-w-full z-10 scrollbar-hidden w-full h-full pt-6 flex-1 flex flex-col-reverse overflow-auto"
						id="messages-container"
						bind:this={messagesContainerElement}
						onscroll={(_e: Event) => {
							scrollEnd = Math.abs(messagesContainerElement!.scrollTop) <= 50;
						}}
					>
						{#key id}
							<Messages
								{channel}
								messages={messages ?? undefined}
								{top}
								onThread={(id: string) => {
									threadId = id;
								}}
								onLoad={async () => {
									const newMessages = (await getChannelMessages(
										'',
										id,
										messages?.length ?? 0
									)) as ChannelMessage[];

									messages = [...(messages ?? []), ...newMessages];

									if (newMessages.length < 50) {
										top = true;
										return;
									}
								}}
							/>
						{/key}
					</div>
				{/if}
			</div>

			<div class=" pb-[1rem]">
				<MessageInput
					id="root"
					{typingUsers}
					{onChange}
					onSubmit={submitHandler}
					{scrollToBottom}
					{scrollEnd}
				/>
			</div>
		</Pane>

		{#if !largeScreen}
			{#if threadId !== null}
				<Drawer
					show={threadId !== null}
					onClose={() => {
						threadId = null;
					}}
				>
					<div class=" {threadId !== null ? ' h-screen  w-full' : 'px-6 py-4'} h-full">
						<Thread
							{threadId}
							{channel}
							onClose={() => {
								threadId = null;
							}}
						/>
					</div>
				</Drawer>
			{/if}
		{:else if threadId !== null}
			<PaneResizer
				class="relative flex w-[3px] items-center justify-center bg-background group bg-gray-50 dark:bg-gray-850"
			>
				<div class="z-10 flex h-7 w-5 items-center justify-center rounded-xs">
					<EllipsisVertical className="size-4 invisible group-hover:visible" />
				</div>
			</PaneResizer>

			<Pane defaultSize={50} minSize={30} class="h-full w-full">
				<div class="h-full w-full shadow-xl">
					<Thread
						{threadId}
						{channel}
						onClose={() => {
							threadId = null;
						}}
					/>
				</div>
			</Pane>
		{/if}
	</PaneGroup>
</div>
