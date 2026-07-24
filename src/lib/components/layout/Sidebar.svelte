<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';

	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import {
		user,
		chats,
		tags,
		showSidebar,
		mobile,
		showArchivedChats,
		pinnedChats,
		scrollPaginationEnabled,
		currentChatPage,
		temporaryChatEnabled,
		channels,
		socket,
		config,
		isApp
	} from '$lib/stores';
	import { onMount, getContext, tick, onDestroy } from 'svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import {
		getChatList,
		getAllTags,
		getChatListBySearchText,
		getPinnedChatList,
		toggleChatPinnedStatusById,
		getChatById,
		updateChatFolderIdById,
		importChat
	} from '$lib/apis/chats';
	import { createNewFolder, getFolders, updateFolderParentIdById } from '$lib/apis/folders';

	import ArchivedChatsModal from './Sidebar/ArchivedChatsModal.svelte';
	import UserMenu from './Sidebar/UserMenu.svelte';
	import ChatItem from './Sidebar/ChatItem.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Loader from '../common/Loader.svelte';
	import SearchInput from './Sidebar/SearchInput.svelte';
	import Folder from '../common/Folder.svelte';
	import Folders from './Sidebar/Folders.svelte';
	import { getChannels, createNewChannel } from '$lib/apis/channels';
	import ChannelModal from './Sidebar/ChannelModal.svelte';
	import ChannelItem from './Sidebar/ChannelItem.svelte';
	import PencilSquare from '../icons/PencilSquare.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface ChannelEntry {
		id: string;
		name?: string;
		[key: string]: unknown;
	}

	interface ChatEntry {
		id: string;
		title: string;
		time_range?: string;
		match_message_id?: string | null;
		match_role?: 'user' | 'assistant' | null;
		match_snippet?: string | null;
		[key: string]: unknown;
	}

	const channelEntries = $derived($channels as ChannelEntry[]);
	const pinnedChatEntries = $derived($pinnedChats as ChatEntry[]);

	let navElement = $state();
	let search = $state('');

	let shiftKey = $state(false);

	let selectedChatId = $state<string | null>(null);
	let showDropdown = $state(false);
	let showPinnedChat = $state(true);

	let showCreateChannel = $state(false);

	// Pagination variables
	let chatListLoading = $state(false);
	let allChatsLoaded = $state(false);
	let chatListLoadError = $state(false);
	let failedChatPage = $state<number | null>(null);
	let searchRequestEpoch = 0;

	let folders = $state({});
	let newFolderId = null;

	const initFolders = async () => {
		const folderList = await getFolders('').catch((error) => {
			toast.error(`${error}`);
			return [];
		});

		folders = {};

		// First pass: Initialize all folder entries
		for (const folder of folderList) {
			// Ensure folder is added to folders with its data
			folders[folder.id] = { ...(folders[folder.id] || {}), ...folder };

			if (newFolderId && folder.id === newFolderId) {
				folders[folder.id].new = true;
				newFolderId = null;
			}
		}

		// Second pass: Tie child folders to their parents
		for (const folder of folderList) {
			if (folder.parent_id) {
				// Ensure the parent folder is initialized if it doesn't exist
				if (!folders[folder.parent_id]) {
					folders[folder.parent_id] = {}; // Create a placeholder if not already present
				}

				// Initialize childrenIds array if it doesn't exist and add the current folder id
				folders[folder.parent_id].childrenIds = folders[folder.parent_id].childrenIds
					? [...folders[folder.parent_id].childrenIds, folder.id]
					: [folder.id];

				// Sort the children by updated_at field
				folders[folder.parent_id].childrenIds.sort((a, b) => {
					return folders[b].updated_at - folders[a].updated_at;
				});
			}
		}
	};

	const createFolder = async (name = 'Untitled') => {
		if (name === '') {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		const rootFolders = Object.values(folders).filter((folder) => folder.parent_id === null);
		if (rootFolders.find((folder) => folder.name.toLowerCase() === name.toLowerCase())) {
			// If a folder with the same name already exists, append a number to the name
			let i = 1;
			while (
				rootFolders.find((folder) => folder.name.toLowerCase() === `${name} ${i}`.toLowerCase())
			) {
				i++;
			}

			name = `${name} ${i}`;
		}

		// Add a dummy folder to the list to show the user that the folder is being created
		const tempId = uuidv4();
		folders = {
			...folders,
			tempId: {
				id: tempId,
				name: name,
				created_at: Date.now(),
				updated_at: Date.now()
			}
		};

		const res = await createNewFolder('', name).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			newFolderId = res.id;
			await initFolders();
		}
	};

	const initChannels = async () => {
		await channels.set(await getChannels(''));
	};

	const initChatList = async () => {
		// Reset pagination variables
		tags.set(await getAllTags(''));
		pinnedChats.set(await getPinnedChatList(''));
		initFolders();

		currentChatPage.set(1);
		allChatsLoaded = false;
		chatListLoading = true;
		chatListLoadError = false;
		failedChatPage = null;

		let chatList;
		try {
			if (search) {
				chatList = await getChatListBySearchText('', search, get(currentChatPage));
			} else {
				chatList = await getChatList('', get(currentChatPage));
			}
		} catch (_err) {
			chatListLoading = false;
			chatListLoadError = true;
			failedChatPage = 1;
			scrollPaginationEnabled.set(true);
			return;
		}

		chatList = chatList ?? [];
		await chats.set(chatList);
		chatListLoading = false;

		// If the first page returned no results, all chats are loaded
		if (chatList.length === 0) {
			allChatsLoaded = true;
		}

		// Enable pagination
		scrollPaginationEnabled.set(true);
	};

	const loadMoreChats = async (requestedPage: number = get(currentChatPage) + 1) => {
		chatListLoading = true;
		chatListLoadError = false;
		failedChatPage = null;

		let newChatList;

		try {
			if (search) {
				newChatList = await getChatListBySearchText('', search, requestedPage);
			} else {
				newChatList = await getChatList('', requestedPage);
			}
		} catch (_err) {
			chatListLoading = false;
			chatListLoadError = true;
			failedChatPage = requestedPage;
			return;
		}

		currentChatPage.set(requestedPage);
		// once the bottom of the list has been reached (no results) there is no need to continue querying
		allChatsLoaded = newChatList.length === 0;
		await chats.set([...(get(chats) ? get(chats) : []), ...newChatList]);

		chatListLoading = false;
	};

	let searchDebounceTimeout;

	const searchDebounceHandler = async () => {
		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
		}
		const requestEpoch = ++searchRequestEpoch;

		if (search === '') {
			chatListLoading = false;
			await initChatList();
			return;
		} else {
			const requestedSearch = search;
			searchDebounceTimeout = setTimeout(async () => {
				chats.set(null);
				chatListLoading = true;
				chatListLoadError = false;
				failedChatPage = null;
				allChatsLoaded = false;
				try {
					const results = await getChatListBySearchText('', requestedSearch);
					if (requestEpoch !== searchRequestEpoch || requestedSearch !== search) return;
					currentChatPage.set(1);
					await chats.set(results);
					allChatsLoaded = results.length === 0;

					if (results.length === 0) {
						tags.set(await getAllTags(''));
					}
				} catch (_err) {
					if (requestEpoch !== searchRequestEpoch || requestedSearch !== search) return;
					chats.set([]);
					chatListLoadError = true;
					failedChatPage = 1;
				} finally {
					if (requestEpoch === searchRequestEpoch) chatListLoading = false;
				}
			}, 1000);
		}
	};

	const retryChatList = async () => {
		if (chatListLoading) return;
		if (failedChatPage === 1) {
			if (search) await searchDebounceHandler();
			else await initChatList();
			return;
		}
		if (failedChatPage !== null) await loadMoreChats(failedChatPage);
	};

	const importChatHandler = async (items, pinned = false, folderId = null) => {
		for (const item of items) {
			if (item.chat) {
				await importChat('', item.chat, item?.meta ?? {}, pinned, folderId);
			}
		}

		initChatList();
	};

	const inputFilesHandler = async (files) => {
		for (const file of files) {
			const reader = new FileReader();
			reader.onload = async (e) => {
				const content = e.target?.result;

				try {
					const chatItems = JSON.parse(content);
					importChatHandler(chatItems);
				} catch {
					toast.error($i18n.t(`Invalid file format.`));
				}
			};

			reader.readAsText(file);
		}
	};

	const tagEventHandler = async (type, _tagName, _chatId) => {
		if (type === 'delete') {
			initChatList();
		} else if (type === 'add') {
			initChatList();
		}
	};

	let _draggedOver = false;

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();

		// Check if a file is being draggedOver.
		if (e.dataTransfer?.types?.includes('Files')) {
			_draggedOver = true;
		} else {
			_draggedOver = false;
		}
	};

	const onDragLeave = () => {
		_draggedOver = false;
	};

	const onDrop = async (e: DragEvent) => {
		e.preventDefault();

		// Perform file drop check and handle it accordingly
		if (e.dataTransfer?.files) {
			const inputFiles = Array.from(e.dataTransfer?.files);

			if (inputFiles && inputFiles.length > 0) {
				inputFilesHandler(inputFiles);
			}
		}

		_draggedOver = false;
	};

	let touchstart;
	let touchend;

	function checkDirection() {
		const screenWidth = window.innerWidth;
		const swipeDistance = Math.abs(touchend.screenX - touchstart.screenX);
		if (touchstart.clientX < 40 && swipeDistance >= screenWidth / 8) {
			if (touchend.screenX < touchstart.screenX) {
				showSidebar.set(false);
			}
			if (touchend.screenX > touchstart.screenX) {
				showSidebar.set(true);
			}
		}
	}

	const onTouchStart = (e: TouchEvent) => {
		touchstart = e.changedTouches[0];
	};

	const onTouchEnd = (e: TouchEvent) => {
		touchend = e.changedTouches[0];
		checkDirection();
	};

	const onKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'Shift') {
			shiftKey = true;
		}
	};

	const onKeyUp = (e: KeyboardEvent) => {
		if (e.key === 'Shift') {
			shiftKey = false;
		}
	};

	const onFocus = () => {};

	const onBlur = () => {
		shiftKey = false;
		selectedChatId = null;
	};

	onMount(async () => {
		showPinnedChat = localStorage?.showPinnedChat ? localStorage.showPinnedChat === 'true' : true;

		mobile.subscribe((value) => {
			if (get(showSidebar) && value) {
				showSidebar.set(false);
			}

			if (get(showSidebar) && !value) {
				const navElement = document.getElementsByTagName('nav')[0];
				if (navElement) {
					navElement.style['-webkit-app-region'] = 'drag';
				}
			}

			if (!get(showSidebar) && !value) {
				showSidebar.set(true);
			}
		});

		showSidebar.set(!get(mobile) ? localStorage.sidebar === 'true' : false);
		showSidebar.subscribe((value) => {
			localStorage.sidebar = value;

			// nav element is not available on the first render
			const navElement = document.getElementsByTagName('nav')[0];

			if (navElement) {
				if (get(mobile)) {
					if (!value) {
						navElement.style['-webkit-app-region'] = 'drag';
					} else {
						navElement.style['-webkit-app-region'] = 'no-drag';
					}
				} else {
					navElement.style['-webkit-app-region'] = 'drag';
				}
			}
		});

		await initChannels();
		await initChatList();

		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);

		window.addEventListener('touchstart', onTouchStart);
		window.addEventListener('touchend', onTouchEnd);

		window.addEventListener('focus', onFocus);
		window.addEventListener('blur-sm', onBlur);

		const dropZone = document.getElementById('sidebar');

		dropZone?.addEventListener('dragover', onDragOver);
		dropZone?.addEventListener('drop', onDrop);
		dropZone?.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		window.removeEventListener('keydown', onKeyDown);
		window.removeEventListener('keyup', onKeyUp);

		window.removeEventListener('touchstart', onTouchStart);
		window.removeEventListener('touchend', onTouchEnd);

		window.removeEventListener('focus', onFocus);
		window.removeEventListener('blur-sm', onBlur);

		const dropZone = document.getElementById('sidebar');

		dropZone?.removeEventListener('dragover', onDragOver);
		dropZone?.removeEventListener('drop', onDrop);
		dropZone?.removeEventListener('dragleave', onDragLeave);
	});
</script>

<ArchivedChatsModal
	bind:show={$showArchivedChats}
	onchange={async () => {
		await initChatList();
	}}
/>

<ChannelModal
	bind:show={showCreateChannel}
	onSubmit={async ({ name, access_control }) => {
		const res = await createNewChannel('', {
			name: name,
			access_control: access_control ?? undefined
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			$socket.emit('join-channels', { auth: { token: $user.token } });
			await initChannels();
			showCreateChannel = false;
		}
	}}
/>

<!-- svelte-ignore a11y_no_static_element_interactions -->

{#if $showSidebar}
	<div
		class=" {$isApp
			? ' ml-[4.5rem] md:ml-0'
			: ''} fixed md:hidden z-40 top-0 right-0 left-0 bottom-0 bg-black/60 w-full min-h-screen h-screen flex justify-center overflow-hidden overscroll-contain"
		onmousedown={() => {
			showSidebar.set(!$showSidebar);
		}}
	></div>
{/if}

<div
	bind:this={navElement}
	id="sidebar"
	class="h-screen max-h-[100dvh] min-h-screen select-none {$showSidebar
		? 'md:relative w-[260px] max-w-[260px]'
		: '-translate-x-[260px] w-[0px]'} {$isApp
		? `ml-[4.5rem] md:ml-0 `
		: 'transition-width duration-200 ease-in-out'}  shrink-0 bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-200 text-sm fixed z-50 top-0 left-0 overflow-x-hidden
        "
	data-state={$showSidebar}
>
	<div
		class="py-2 my-auto flex flex-col justify-between h-screen max-h-[100dvh] w-[260px] overflow-x-hidden z-50 {$showSidebar
			? ''
			: 'invisible'}"
	>
		<div class="px-1.5 flex justify-between space-x-1 text-gray-600 dark:text-gray-400">
			<button
				class=" cursor-pointer p-[7px] flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-900 transition"
				aria-label={$i18n.t('Toggle Sidebar')}
				onclick={() => {
					showSidebar.set(!$showSidebar);
				}}
			>
				<div class=" m-auto self-center">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="size-5"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12"
						/>
					</svg>
				</div>
			</button>

			<a
				id="sidebar-new-chat-button"
				class="flex justify-between items-center flex-1 rounded-lg px-2 py-1 h-full text-right hover:bg-gray-100 dark:hover:bg-gray-900 transition no-drag-region"
				href={resolve('/')}
				draggable="false"
				onclick={async () => {
					selectedChatId = null;
					await goto(resolve('/'));
					const newChatButton = document.getElementById('new-chat-button');
					setTimeout(() => {
						newChatButton?.click();
						if ($mobile) {
							showSidebar.set(false);
						}
					}, 0);
				}}
			>
				<div class="flex items-center">
					<div class="self-center mx-1.5">
						<img
							crossorigin="anonymous"
							src={$config?.logo_url || '/static/favicon.png'}
							class=" size-5 -translate-x-1.5 rounded-full"
							alt="logo"
						/>
					</div>
					<div class=" self-center font-medium text-sm text-gray-850 dark:text-white font-primary">
						{$i18n.t('New Chat')}
					</div>
				</div>

				<div>
					<PencilSquare className=" size-5" strokeWidth="2" />
				</div>
			</a>
		</div>

		<div class="relative {$temporaryChatEnabled ? 'opacity-20' : ''}">
			{#if $temporaryChatEnabled}
				<div class="absolute z-40 w-full h-full flex justify-center"></div>
			{/if}

			<SearchInput
				bind:value={search}
				onInput={searchDebounceHandler}
				placeholder={$i18n.t('Search')}
				showClearButton={true}
			/>
		</div>

		<div
			class="relative flex flex-col flex-1 overflow-y-auto overflow-x-hidden {$temporaryChatEnabled
				? 'opacity-20'
				: ''}"
		>
			{#if $config?.features?.enable_channels && ($user.role === 'admin' || $channels.length > 0) && !search}
				<Folder
					className="px-2 mt-0.5"
					name={$i18n.t('Channels')}
					dragAndDrop={false}
					onAdd={async () => {
						if ($user.role === 'admin') {
							await tick();

							setTimeout(() => {
								showCreateChannel = true;
							}, 0);
						}
					}}
					onAddLabel={$i18n.t('Create Channel')}
				>
					{#each channelEntries as channel (channel.id)}
						<ChannelItem
							{channel}
							onUpdate={async () => {
								await initChannels();
							}}
						/>
					{/each}
				</Folder>
			{/if}

			<Folder
				collapsible={!search}
				className="px-2 mt-0.5"
				name={$i18n.t('Chats')}
				onAdd={() => {
					createFolder();
				}}
				onAddLabel={$i18n.t('New Folder')}
				onImport={(e: unknown) => {
					importChatHandler((e as CustomEvent).detail);
				}}
				onDrop={async (e: unknown) => {
					const { type, id, item } = (e as CustomEvent).detail;

					if (type === 'chat') {
						let chat = await getChatById('', id).catch((_error) => {
							return null;
						});
						if (!chat && item) {
							chat = await importChat('', item.chat, item?.meta ?? {});
						}

						if (chat) {
							if (chat.folder_id) {
								await updateChatFolderIdById('', chat.id, null).catch((error) => {
									toast.error(`${error}`);
									return null;
								});
							}

							if (chat.pinned) {
								await toggleChatPinnedStatusById('', chat.id);
							}

							initChatList();
						}
					} else if (type === 'folder') {
						if (folders[id].parent_id === null) {
							return;
						}

						const res = await updateFolderParentIdById('', id, null).catch((error) => {
							toast.error(`${error}`);
							return null;
						});

						if (res) {
							await initFolders();
						}
					}
				}}
			>
				{#if $temporaryChatEnabled}
					<div class="absolute z-40 w-full h-full flex justify-center"></div>
				{/if}

				{#if !search && $pinnedChats.length > 0}
					<div class="flex flex-col space-y-1 rounded-xl">
						<Folder
							className=""
							bind:open={showPinnedChat}
							onchange={(e: unknown) => {
								localStorage.setItem('showPinnedChat', (e as CustomEvent).detail);
							}}
							onImport={(e: unknown) => {
								importChatHandler((e as CustomEvent).detail, true);
							}}
							onDrop={async (e: unknown) => {
								const { type, id, item } = (e as CustomEvent).detail;

								if (type === 'chat') {
									let chat = await getChatById('', id).catch((_error) => {
										return null;
									});
									if (!chat && item) {
										chat = await importChat('', item.chat, item?.meta ?? {});
									}

									if (chat) {
										if (chat.folder_id) {
											await updateChatFolderIdById('', chat.id, null).catch((error) => {
												toast.error(`${error}`);
												return null;
											});
										}

										if (!chat.pinned) {
											await toggleChatPinnedStatusById('', chat.id);
										}

										initChatList();
									}
								}
							}}
							name={$i18n.t('Pinned')}
						>
							<div
								class="ml-3 pl-1 mt-[1px] flex flex-col overflow-y-auto scrollbar-hidden border-s border-gray-100 dark:border-gray-900"
							>
								{#each pinnedChatEntries as chat (chat.id)}
									<ChatItem
										className=""
										id={chat.id}
										title={chat.title}
										{shiftKey}
										selected={selectedChatId === chat.id}
										onSelect={() => {
											selectedChatId = chat.id;
										}}
										onunselect={() => {
											selectedChatId = null;
										}}
										onchange={async () => {
											initChatList();
										}}
										ontag={(e: CustomEvent) => {
											const { type, name } = e.detail;
											tagEventHandler(type, name, chat.id);
										}}
									/>
								{/each}
							</div>
						</Folder>
					</div>
				{/if}

				{#if !search && folders}
					<Folders
						{folders}
						onimport={(e: unknown) => {
							const { folderId, items } = (e as CustomEvent).detail;
							importChatHandler(items, false, folderId);
						}}
						onupdate={async (_e) => {
							initChatList();
						}}
						onchange={async () => {
							initChatList();
						}}
					/>
				{/if}

				<div class=" flex-1 flex flex-col overflow-y-auto scrollbar-hidden">
					<div class="pt-1.5">
						{#if $chats}
							{#each $chats as chat, idx (chat.id)}
								{#if idx === 0 || (idx > 0 && chat.time_range !== $chats[idx - 1].time_range)}
									<div
										class="w-full pl-2.5 text-xs text-gray-500 dark:text-gray-500 font-medium {idx ===
										0
											? ''
											: 'pt-5'} pb-1.5"
									>
										{$i18n.t(chat.time_range)}
										<!-- localisation keys for time_range to be recognized from the i18next parser (so they don't get automatically removed):
							{$i18n.t('Today')}
							{$i18n.t('Yesterday')}
							{$i18n.t('Previous 7 days')}
							{$i18n.t('Previous 30 days')}
							{$i18n.t('January')}
							{$i18n.t('February')}
							{$i18n.t('March')}
							{$i18n.t('April')}
							{$i18n.t('May')}
							{$i18n.t('June')}
							{$i18n.t('July')}
							{$i18n.t('August')}
							{$i18n.t('September')}
							{$i18n.t('October')}
							{$i18n.t('November')}
							{$i18n.t('December')}
							-->
									</div>
								{/if}

								<ChatItem
									className=""
									id={chat.id}
									title={chat.title}
									matchMessageId={search ? chat.match_message_id : null}
									matchRole={search ? chat.match_role : null}
									matchSnippet={search ? chat.match_snippet : null}
									{shiftKey}
									selected={selectedChatId === chat.id}
									onSelect={() => {
										selectedChatId = chat.id;
									}}
									onunselect={() => {
										selectedChatId = null;
									}}
									onchange={async () => {
										initChatList();
									}}
									ontag={(e: CustomEvent) => {
										const { type, name } = e.detail;
										tagEventHandler(type, name, chat.id);
									}}
								/>
							{/each}

							{#if chatListLoadError}
								<div
									class="mx-2 mb-2 space-y-2 rounded-lg border border-gray-200 p-3 text-center text-xs text-gray-600 dark:border-gray-800 dark:text-gray-300"
									role="alert"
								>
									<p>{$i18n.t('Something went wrong :/')}</p>
									<button
										class="rounded-md border border-gray-300 px-3 py-1 font-medium hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
										onclick={retryChatList}
									>
										{$i18n.t('Retry')}
									</button>
								</div>
							{:else if $scrollPaginationEnabled && !allChatsLoaded}
								<Loader
									onVisible={() => {
										if (!chatListLoading) {
											loadMoreChats();
										}
									}}
								>
									<div
										class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2"
									>
										<Spinner className=" size-4" />
										<div class=" ">{$i18n.t('Loading...')}</div>
									</div>
								</Loader>
							{/if}
						{:else if $chats === null}
							<div class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2">
								<Spinner className=" size-4" />
								<div class=" ">{$i18n.t('Loading...')}</div>
							</div>
						{/if}
					</div>
				</div>
			</Folder>
		</div>

		<div class="px-2">
			<div class="flex flex-col font-primary">
				{#if $user !== undefined}
					<UserMenu
						role={$user.role}
						onshow={(e: CustomEvent) => {
							if (e.detail === 'archived-chat') {
								showArchivedChats.set(true);
							}
						}}
					>
						<button
							class=" flex items-center rounded-xl py-2.5 px-2.5 w-full hover:bg-gray-100 dark:hover:bg-gray-900 transition"
							onclick={() => {
								showDropdown = !showDropdown;
							}}
						>
							<div class=" self-center mr-3">
								<img
									src={$user.profile_image_url}
									class=" max-w-[30px] object-cover rounded-full"
									alt={$i18n.t('User profile')}
								/>
							</div>
							<div class=" self-center font-medium">{$user.name}</div>
						</button>
					</UserMenu>
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.scrollbar-hidden:active::-webkit-scrollbar-thumb,
	.scrollbar-hidden:focus::-webkit-scrollbar-thumb,
	.scrollbar-hidden:hover::-webkit-scrollbar-thumb {
		visibility: visible;
	}
	.scrollbar-hidden::-webkit-scrollbar-thumb {
		visibility: hidden;
	}
</style>
