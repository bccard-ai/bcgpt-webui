<script lang="ts">
	import { get } from 'svelte/store';

	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, getContext, tick, onDestroy, untrack } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import {
		archiveChatById,
		cloneChatById,
		deleteChatById,
		getAllTags,
		getChatById,
		getChatList,
		getPinnedChatList,
		updateChatById,
		updateChatEntryInList
	} from '$lib/apis/chats';
	import {
		chatId,
		chatTitle as _chatTitle,
		chats,
		mobile,
		pinnedChats,
		showSidebar,
		currentChatPage,
		tags
	} from '$lib/stores';

	import ChatMenu from './ChatMenu.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import ShareChatModal from '$lib/components/chat/ShareChatModal.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import DragGhost from '$lib/components/common/DragGhost.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Additional CSS class names */
		className?: string;
		/** Chat ID */
		id: string;
		/** Chat title displayed in the list */
		title: string;
		/** Message hit used to focus the result after navigation */
		matchMessageId?: string | null;
		/** Role associated with the matching message */
		matchRole?: 'user' | 'assistant' | null;
		/** Plain-text context around the match */
		matchSnippet?: string | null;
		/** Whether this chat is currently selected (for bulk actions) */
		selected?: boolean;
		/** Whether the shift key is held (enables bulk action mode) */
		shiftKey?: boolean;
		/** Callback invoked when chat data changes */
		onchange?: (...args: unknown[]) => void;
		/** Callback invoked when the item is selected */
		onSelect?: (...args: unknown[]) => void;
		/** Callback invoked when the item is unselected */
		onUnselect?: (...args: unknown[]) => void;
		/** Callback invoked when a tag event occurs */
		onTag?: (...args: unknown[]) => void;
	}

	let {
		className = '',
		id,
		title,
		matchMessageId = null,
		matchRole = null,
		matchSnippet = null,
		selected = false,
		shiftKey = false,
		onchange = () => {},
		onSelect = () => {},
		onUnselect = () => {},
		onTag = () => {}
	}: Props = $props();

	let chat = $state(null);

	let mouseOver = $state(false);
	let draggable = $state(false);

	const loadChat = async () => {
		if (!chat) {
			draggable = false;
			chat = await getChatById('', id);
			draggable = true;
		}
	};

	let showShareChatModal = $state(false);
	let confirmEdit = $state(false);

	let chatTitle = $state(untrack(() => title));

	const editChatTitle = async (id, title) => {
		if (title === '') {
			toast.error($i18n.t('Title cannot be an empty string.'));
		} else {
			await updateChatById('', id, {
				title: title
			});

			if (id === get(chatId)) {
				_chatTitle.set(title);
			}

			chats.set(
				updateChatEntryInList(get(chats), id, { title: title, updated_at: Date.now() / 1000 })
			);
			const _pinned = get(pinnedChats);
			if (_pinned) {
				pinnedChats.set(
					updateChatEntryInList(_pinned, id, { title: title, updated_at: Date.now() / 1000 })
				);
			}
		}
	};

	const cloneChatHandler = async (id) => {
		const res = await cloneChatById(
			'',
			id,
			$i18n.t('Clone of {{TITLE}}', {
				TITLE: title
			})
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			goto(resolve(`/c/${res.id}`));

			currentChatPage.set(1);
			await chats.set(await getChatList('', get(currentChatPage)));
			await pinnedChats.set(await getPinnedChatList(''));
		}
	};

	const deleteChatHandler = async (id) => {
		const res = await deleteChatById('', id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			tags.set(await getAllTags(''));
			if (get(chatId) === id) {
				await goto(resolve('/'));

				await chatId.set('');
				await tick();
			}

			onchange?.();
		}
	};

	const archiveChatHandler = async (id) => {
		await archiveChatById('', id);
		onchange?.();
	};

	const focusEdit = async (node: HTMLInputElement) => {
		node.focus();
	};

	let itemElement = $state();

	let dragged = $state(false);
	let x = $state(0);
	let y = $state(0);

	const dragImage = new Image();
	dragImage.src =
		'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

	const onDragStart = (event: DragEvent) => {
		event.stopPropagation();

		event.dataTransfer.setDragImage(dragImage, 0, 0);

		event.dataTransfer.setData(
			'text/plain',
			JSON.stringify({
				type: 'chat',
				id: id,
				item: chat
			})
		);

		dragged = true;
		itemElement.style.opacity = '0.5';
	};

	const onDrag = (event: DragEvent) => {
		event.stopPropagation();

		x = event.clientX;
		y = event.clientY;
	};

	const onDragEnd = (event: DragEvent) => {
		event.stopPropagation();

		itemElement.style.opacity = '1';
		dragged = false;
	};

	onMount(() => {
		if (itemElement) {
			itemElement.addEventListener('dragstart', onDragStart);
			itemElement.addEventListener('drag', onDrag);
			itemElement.addEventListener('dragend', onDragEnd);
		}
	});

	onDestroy(() => {
		if (itemElement) {
			itemElement.removeEventListener('dragstart', onDragStart);
			itemElement.removeEventListener('drag', onDrag);
			itemElement.removeEventListener('dragend', onDragEnd);
		}
	});

	let showDeleteConfirm = $state(false);

	const chatTitleInputKeydownHandler = (e: KeyboardEvent) => {
		if (e.key === 'Enter') {
			e.preventDefault();
			editChatTitle(id, chatTitle);
			confirmEdit = false;
			chatTitle = '';
		} else if (e.key === 'Escape') {
			e.preventDefault();
			confirmEdit = false;
			chatTitle = '';
		}
	};

	$effect(() => {
		if (mouseOver) {
			loadChat();
		}
	});
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={id} />

<DeleteConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete chat?')}
	onconfirm={() => {
		deleteChatHandler(id);
	}}
>
	<div class=" text-sm text-gray-500 flex-1 line-clamp-3">
		{$i18n.t('This will delete')} <span class="  font-semibold">{title}</span>.
	</div>
</DeleteConfirmDialog>

{#if dragged && x && y}
	<DragGhost {x} {y}>
		<div class=" bg-black/80 backdrop-blur-2xl px-2 py-1 rounded-lg w-fit max-w-40">
			<div class="flex items-center gap-1">
				<Document className=" size-[18px]" strokeWidth="2" />
				<div class=" text-xs text-white line-clamp-1">
					{title}
				</div>
			</div>
		</div>
	</DragGhost>
{/if}

<div
	bind:this={itemElement}
	class=" w-full {className} relative group"
	draggable={draggable && !confirmEdit}
>
	{#if confirmEdit}
		<div
			class=" w-full flex justify-between rounded-lg px-[11px] py-[6px] {id === $chatId ||
			confirmEdit
				? 'bg-gray-200 dark:bg-gray-900'
				: selected
					? 'bg-gray-100 dark:bg-gray-950'
					: 'group-hover:bg-gray-100 dark:group-hover:bg-gray-950'}  whitespace-nowrap text-ellipsis"
		>
			<input
				use:focusEdit
				bind:value={chatTitle}
				id="chat-title-input-{id}"
				class=" bg-transparent w-full outline-hidden mr-10"
				onkeydown={chatTitleInputKeydownHandler}
			/>
		</div>
	{:else}
		<a
			class=" w-full flex justify-between rounded-lg px-[11px] py-[6px] {id === $chatId ||
			confirmEdit
				? 'bg-gray-200 dark:bg-gray-900'
				: selected
					? 'bg-gray-100 dark:bg-gray-950'
					: ' group-hover:bg-gray-100 dark:group-hover:bg-gray-950'}  whitespace-nowrap text-ellipsis"
			href={resolve(
				`/c/${id}${matchMessageId ? `?message=${encodeURIComponent(matchMessageId)}` : ''}`
			)}
			onclick={() => {
				onSelect?.();

				if ($mobile) {
					showSidebar.set(false);
				}
			}}
			ondblclick={() => {
				chatTitle = title;
				confirmEdit = true;
			}}
			onmouseenter={(_e: MouseEvent) => {
				mouseOver = true;
			}}
			onmouseleave={(_e: MouseEvent) => {
				mouseOver = false;
			}}
			onfocus={(_e: FocusEvent) => {}}
			draggable="false"
		>
			<div class="flex min-w-0 flex-1 flex-col self-center">
				<div dir="auto" class="h-[20px] w-full overflow-hidden text-left">
					{title}
				</div>
				{#if matchSnippet}
					<div
						dir="auto"
						class="truncate pr-5 text-left text-[11px] leading-4 text-gray-500 dark:text-gray-400"
						title={matchSnippet}
					>
						<span class="sr-only">
							{matchRole === 'user' ? $i18n.t('You') : $i18n.t('Assistant')}:
						</span>
						{matchSnippet}
					</div>
				{/if}
			</div>
		</a>
	{/if}

	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="
        {id === $chatId || confirmEdit
			? 'from-gray-200 dark:from-gray-900'
			: selected
				? 'from-gray-100 dark:from-gray-950'
				: 'invisible group-hover:visible from-gray-100 dark:from-gray-950'}
            absolute {className === 'pr-2'
			? 'right-[8px]'
			: 'right-0'}  top-[4px] py-1 pr-0.5 mr-1.5 pl-5 bg-linear-to-l from-80%

              to-transparent"
		onmouseenter={(_e: MouseEvent) => {
			mouseOver = true;
		}}
		onmouseleave={(_e: MouseEvent) => {
			mouseOver = false;
		}}
	>
		{#if confirmEdit}
			<div
				class="flex self-center items-center space-x-1.5 z-10 translate-y-[0.5px] -translate-x-[0.5px]"
			>
				<Tooltip content={$i18n.t('Confirm')}>
					<button
						class=" self-center dark:hover:text-white transition"
						onclick={() => {
							editChatTitle(id, chatTitle);
							confirmEdit = false;
							chatTitle = '';
						}}
					>
						<Check className=" size-3.5" strokeWidth="2.5" />
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('Cancel')}>
					<button
						class=" self-center dark:hover:text-white transition"
						onclick={() => {
							confirmEdit = false;
							chatTitle = '';
						}}
					>
						<XMark strokeWidth="2.5" />
					</button>
				</Tooltip>
			</div>
		{:else if shiftKey && mouseOver}
			<div class=" flex items-center self-center space-x-1.5">
				<Tooltip content={$i18n.t('Archive')} className="flex items-center">
					<button
						class=" self-center dark:hover:text-white transition"
						onclick={() => {
							archiveChatHandler(id);
						}}
						type="button"
					>
						<ArchiveBox className="size-4  translate-y-[0.5px]" strokeWidth="2" />
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('Delete')}>
					<button
						class=" self-center dark:hover:text-white transition"
						onclick={() => {
							deleteChatHandler(id);
						}}
						type="button"
					>
						<GarbageBin strokeWidth="2" />
					</button>
				</Tooltip>
			</div>
		{:else}
			<div class="flex self-center space-x-1 z-10">
				<ChatMenu
					chatId={id}
					cloneChatHandler={() => {
						cloneChatHandler(id);
					}}
					shareHandler={() => {
						showShareChatModal = true;
					}}
					archiveChatHandler={() => {
						archiveChatHandler(id);
					}}
					renameHandler={async () => {
						chatTitle = title;
						confirmEdit = true;

						await tick();
						const input = document.getElementById(`chat-title-input-${id}`);
						if (input) {
							input.focus();
						}
					}}
					deleteHandler={() => {
						showDeleteConfirm = true;
					}}
					onClose={() => {
						onUnselect?.();
					}}
					onchange={async () => {
						onchange?.();
					}}
					ontag={(e: CustomEvent) => {
						onTag?.(e.detail);
					}}
				>
					<button
						aria-label={$i18n.t('Chat Menu')}
						class=" self-center dark:hover:text-white transition"
						onclick={() => {
							onSelect?.();
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M2 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM6.5 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z"
							/>
						</svg>
					</button>
				</ChatMenu>

				{#if id === $chatId}
					<!-- Shortcut support using "delete-chat-button" id -->
					<button
						id="delete-chat-button"
						class="hidden"
						aria-label={$i18n.t('Delete Chat')}
						onclick={() => {
							showDeleteConfirm = true;
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M2 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM6.5 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z"
							/>
						</svg>
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>
