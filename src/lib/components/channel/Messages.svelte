<script lang="ts">
	import { toast } from 'svelte-sonner';

	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import isToday from 'dayjs/plugin/isToday';
	import isYesterday from 'dayjs/plugin/isYesterday';

	dayjs.extend(relativeTime);
	dayjs.extend(isToday);
	dayjs.extend(isYesterday);
	import { tick, getContext } from 'svelte';

	import { settings, user } from '$lib/stores';

	import Message from './Messages/Message.svelte';
	import Loader from '../common/Loader.svelte';
	import Spinner from '../common/Spinner.svelte';
	import { addReaction, deleteMessage, removeReaction, updateMessage } from '$lib/apis/channels';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

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

	interface Channel {
		name: string;
		created_at: number;
		[key: string]: unknown;
	}

	/**
	 * Renders a scrollable, paginated list of channel messages with support for
	 * reactions, editing, deletion, threading, and infinite scroll loading.
	 *
	 * @example
	 * ```svelte
	 * <Messages
	 *   channel={channelData}
	 *   messages={messageList}
	 *   top={false}
	 *   thread={false}
	 *   onLoad={loadMoreMessages}
	 *   onThread={(id) => openThread(id)}
	 * />
	 * ```
	 *
	 * @param id - Optional identifier for the message list context.
	 * @param channel - The channel object for header display.
	 * @param messages - Array of channel messages to render.
	 * @param top - Whether all historical messages have been loaded.
	 * @param thread - Whether this is a thread view.
	 * @param onLoad - Callback to load more messages (pagination).
	 * @param onThread - Callback when a user opens a thread on a message.
	 */
	interface Props {
		id?: string | null;
		channel?: Channel | null;
		messages?: ChannelMessage[];
		top?: boolean;
		thread?: boolean;
		onLoad?: () => unknown;
		onThread?: (id: string) => void;
	}

	let {
		id = null,
		channel = null,
		messages = [],
		top = false,
		thread = false,
		onLoad = () => {},
		onThread = () => {}
	}: Props = $props();

	let messagesLoading = $state(false);

	const loadMoreMessages = async () => {
		const element = document.getElementById('messages-container');
		element!.scrollTop = element!.scrollTop + 100;

		messagesLoading = true;

		await onLoad();

		await tick();
		messagesLoading = false;
	};
</script>

{#if messages}
	{@const messageList = messages.slice().reverse()}
	<div>
		{#if !top}
			<Loader
				onVisible={() => {
					if (!messagesLoading) {
						loadMoreMessages();
					}
				}}
			>
				<div class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2">
					<Spinner className=" size-4" />
					<div class=" ">{$i18n.t('Loading...')}</div>
				</div>
			</Loader>
		{:else if !thread}
			<div
				class="px-5
			
			{($settings?.widescreenMode ?? null) ? 'max-w-full' : 'max-w-5xl'} mx-auto"
			>
				{#if channel}
					<div class="flex flex-col gap-1.5 pb-5 pt-10">
						<div class="text-2xl font-medium capitalize">{channel.name}</div>

						<div class=" text-gray-500">
							{$i18n.t(
								'This channel was created on {{createdAt}}. This is the very beginning of the {{channelName}} channel.',
								{
									createdAt: dayjs(channel.created_at / 1000000).format('MMMM D, YYYY'),
									channelName: channel.name
								}
							)}
						</div>
					</div>
				{:else}
					<div class="flex justify-center text-xs items-center gap-2 py-5">
						<div class=" ">{$i18n.t('Start of the channel')}</div>
					</div>
				{/if}

				{#if messageList.length > 0}
					<hr class=" border-gray-50 dark:border-gray-700/20 py-2.5 w-full" />
				{/if}
			</div>
		{/if}

		{#each messageList as message, messageIdx (id ? `${id}-${message.id}` : message.id)}
			<Message
				{message}
				{thread}
				showUserProfile={messageIdx === 0 ||
					messageList.at(messageIdx - 1)?.user_id !== message.user_id}
				onDelete={() => {
					messages = messages.filter((m) => m.id !== message.id);

					deleteMessage('', message.channel_id, message.id).catch((error) => {
						toast.error(`${error}`);
						return null;
					});
				}}
				onEdit={(content: string) => {
					messages = messages.map((m) => {
						if (m.id === message.id) {
							m.content = content;
						}
						return m;
					});

					updateMessage('', message.channel_id, message.id, {
						content: content
					}).catch((error) => {
						toast.error(`${error}`);
						return null;
					});
				}}
				onThread={(id: string) => {
					onThread(id);
				}}
				onReaction={(name: string) => {
					if (
						(message?.reactions ?? [])
							.find((reaction) => reaction.name === name)
							?.user_ids?.includes($user.id) ??
						false
					) {
						messages = messages.map((m) => {
							if (m.id === message.id) {
								const reaction = m.reactions.find((reaction) => reaction.name === name);

								if (reaction) {
									reaction.user_ids = reaction.user_ids.filter((id) => id !== $user.id);
									reaction.count = reaction.user_ids.length;

									if (reaction.count === 0) {
										m.reactions = m.reactions.filter((r) => r.name !== name);
									}
								}
							}
							return m;
						});

						removeReaction('', message.channel_id, message.id, name).catch((error) => {
							toast.error(`${error}`);
							return null;
						});
					} else {
						messages = messages.map((m) => {
							if (m.id === message.id) {
								if (m.reactions) {
									const reaction = m.reactions.find((reaction) => reaction.name === name);

									if (reaction) {
										reaction.user_ids.push($user.id);
										reaction.count = reaction.user_ids.length;
									} else {
										m.reactions.push({
											name: name,
											user_ids: [$user.id],
											count: 1
										});
									}
								}
							}
							return m;
						});

						addReaction('', message.channel_id, message.id, name).catch((error) => {
							toast.error(`${error}`);
							return null;
						});
					}
				}}
			/>
		{/each}

		<div class="pb-6"></div>
	</div>
{/if}
