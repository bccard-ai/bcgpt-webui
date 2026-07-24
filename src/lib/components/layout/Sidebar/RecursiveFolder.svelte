<script lang="ts">
	import { getContext, onMount, onDestroy, tick } from 'svelte';

	const i18n = getContext('i18n');
	import DOMPurify from 'dompurify';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import ChevronDown from '../../icons/ChevronDown.svelte';
	import ChevronRight from '../../icons/ChevronRight.svelte';
	import Collapsible from '../../common/Collapsible.svelte';
	import DragGhost from '$lib/components/common/DragGhost.svelte';

	import FolderOpen from '$lib/components/icons/FolderOpen.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import {
		deleteFolderById,
		updateFolderIsExpandedById,
		updateFolderNameById,
		updateFolderParentIdById
	} from '$lib/apis/folders';
	import { toast } from 'svelte-sonner';
	import {
		getChatById,
		getChatsByFolderId,
		importChat,
		updateChatFolderIdById
	} from '$lib/apis/chats';
	import ChatItem from './ChatItem.svelte';
	import RecursiveFolder from './RecursiveFolder.svelte';
	import FolderMenu from './Folders/FolderMenu.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	interface Props {
		/** Whether the folder is initially expanded */
		open?: boolean;
		/** Map of folder IDs to folder data objects */
		folders?: Record<string, unknown>;
		/** The ID of this folder */
		folderId?: string;
		/** Additional CSS class names */
		className?: string;
		/** Whether a parent folder is currently being dragged */
		parentDragged?: boolean;
		/** Callback invoked when folder structure changes */
		onUpdate?: (...args: unknown[]) => void;
		/** Callback invoked when the folder is opened/closed */
		onOpen?: (...args: unknown[]) => void;
		/** Callback invoked when items are imported into this folder */
		onImport?: (...args: unknown[]) => void;
		/** Callback invoked when chat data changes */
		onchange?: (...args: unknown[]) => void;
	}

	let {
		open = false,
		folders = {},
		folderId = '',
		className = '',
		parentDragged = false,
		onUpdate = () => {},
		onOpen = () => {},
		onImport = () => {},
		onchange = () => {}
	}: Props = $props();
	let folderElement;

	let edit = $state(false);

	let draggedOver = $state(false);
	let dragged = $state(false);

	let name = $state('');

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		if (dragged || parentDragged) {
			return;
		}
		draggedOver = true;
	};

	const onDrop = async (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		if (dragged || parentDragged) {
			return;
		}

		if (folderElement.contains(e.target)) {
			if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
				for (const item of Array.from(e.dataTransfer.items)) {
					if (item.kind === 'file') {
						const file = item.getAsFile();
						if (file && file.type === 'application/json') {
							const reader = new FileReader();
							reader.onload = async function (event) {
								try {
									const fileContent = JSON.parse(event.target?.result);
									open = true;
									onImport?.({
										folderId: folderId,
										items: fileContent
									});
								} catch (_error) {
									toast.error($i18n.t('Invalid file format.'));
								}
							};

							reader.readAsText(file);
						} else {
							toast.error($i18n.t('Only JSON file types are supported.'));
						}
					} else {
						const dataTransfer = e.dataTransfer.getData('text/plain');
						const data = JSON.parse(dataTransfer);

						const { type, id, item } = data;

						if (type === 'folder') {
							open = true;
							if (id === folderId) {
								return;
							}
							const res = await updateFolderParentIdById('', id, folderId).catch((error) => {
								toast.error(`${error}`);
								return null;
							});

							if (res) {
								onUpdate?.();
							}
						} else if (type === 'chat') {
							open = true;

							let chat = await getChatById('', id).catch(() => {
								return null;
							});
							if (!chat && item) {
								chat = await importChat('', item.chat, item?.meta ?? {});
							}

							const res = await updateChatFolderIdById('', chat.id, folderId).catch((error) => {
								toast.error(`${error}`);
								return null;
							});

							if (res) {
								onUpdate?.();
							}
						}
					}
				}
			}

			draggedOver = false;
		}
	};

	const onDragLeave = (e: DragEvent) => {
		e.preventDefault();
		if (dragged || parentDragged) {
			return;
		}

		draggedOver = false;
	};

	const dragImage = new Image();
	dragImage.src =
		'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

	let x = $state();
	let y = $state();

	const onDragStart = (event: DragEvent) => {
		event.stopPropagation();
		event.dataTransfer.setDragImage(dragImage, 0, 0);

		event.dataTransfer.setData(
			'text/plain',
			JSON.stringify({
				type: 'folder',
				id: folderId
			})
		);

		dragged = true;
		folderElement.style.opacity = '0.5';
	};

	const onDrag = (event: DragEvent) => {
		event.stopPropagation();

		x = event.clientX;
		y = event.clientY;
	};

	const onDragEnd = (event: DragEvent) => {
		event.stopPropagation();

		folderElement.style.opacity = '1';
		dragged = false;
	};

	onMount(async () => {
		open = folders[folderId].is_expanded;
		if (folderElement) {
			folderElement.addEventListener('dragover', onDragOver);
			folderElement.addEventListener('drop', onDrop);
			folderElement.addEventListener('dragleave', onDragLeave);

			folderElement.addEventListener('dragstart', onDragStart);
			folderElement.addEventListener('drag', onDrag);
			folderElement.addEventListener('dragend', onDragEnd);
		}

		if (folders[folderId]?.new) {
			delete folders[folderId].new;

			await tick();
			editHandler();
		}
	});

	onDestroy(() => {
		if (folderElement) {
			folderElement.removeEventListener('dragover', onDragOver);
			folderElement.removeEventListener('drop', onDrop);
			folderElement.removeEventListener('dragleave', onDragLeave);

			folderElement.removeEventListener('dragstart', onDragStart);
			folderElement.removeEventListener('drag', onDrag);
			folderElement.removeEventListener('dragend', onDragEnd);
		}
	});

	let showDeleteConfirm = $state(false);

	const deleteHandler = async () => {
		const res = await deleteFolderById('', folderId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Folder deleted successfully'));
			onUpdate?.();
		}
	};

	const nameUpdateHandler = async () => {
		if (name === '') {
			toast.error($i18n.t('Folder name cannot be empty'));
			return;
		}

		if (name === folders[folderId].name) {
			edit = false;
			return;
		}

		const currentName = folders[folderId].name;

		name = name.trim();
		folders[folderId].name = name;

		const res = await updateFolderNameById('', folderId, name).catch((error) => {
			toast.error(`${error}`);

			folders[folderId].name = currentName;
			return null;
		});

		if (res) {
			folders[folderId].name = name;
			toast.success($i18n.t('Folder name updated successfully'));
			onUpdate?.();
		}
	};

	const isExpandedUpdateHandler = async () => {
		await updateFolderIsExpandedById('', folderId, open).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	};

	let isExpandedUpdateTimeout;

	const isExpandedUpdateDebounceHandler = (_open: boolean) => {
		clearTimeout(isExpandedUpdateTimeout);
		isExpandedUpdateTimeout = setTimeout(() => {
			isExpandedUpdateHandler();
		}, 500);
	};

	$effect(() => {
		isExpandedUpdateDebounceHandler(open);
	});

	const editHandler = async () => {
		await tick();
		name = folders[folderId].name;

		edit = true;
		await tick();

		const input = document.getElementById(`folder-${folderId}-input`);

		if (input) {
			input.focus();
		}
	};

	const exportHandler = async () => {
		const chats = await getChatsByFolderId('', folderId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!chats) {
			return;
		}

		const blob = new Blob([JSON.stringify(chats)], {
			type: 'application/json'
		});

		saveAs(blob, `folder-${folders[folderId].name}-export-${Date.now()}.json`);
	};
</script>

<DeleteConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete folder?')}
	onconfirm={() => {
		deleteHandler();
	}}
>
	<div class=" text-sm text-gray-700 dark:text-gray-300 flex-1 line-clamp-3">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: DOMPurify-sanitized i18n string with interpolated folder name -->
		{@html DOMPurify.sanitize(
			$i18n.t('This will delete <strong>{{NAME}}</strong> and <strong>all its contents</strong>.', {
				NAME: folders[folderId].name
			})
		)}
	</div>
</DeleteConfirmDialog>

{#if dragged && x && y}
	<DragGhost {x} {y}>
		<div class=" bg-black/80 backdrop-blur-2xl px-2 py-1 rounded-lg w-fit max-w-40">
			<div class="flex items-center gap-1">
				<FolderOpen className="size-3.5" strokeWidth="2" />
				<div class=" text-xs text-white line-clamp-1">
					{folders[folderId].name}
				</div>
			</div>
		</div>
	</DragGhost>
{/if}

<div bind:this={folderElement} class="relative {className}" draggable="true">
	{#if draggedOver}
		<div
			class="absolute top-0 left-0 w-full h-full rounded-xs bg-gray-100/50 dark:bg-gray-700/20 bg-opacity-50 dark:bg-opacity-10 z-50 pointer-events-none touch-none"
		></div>
	{/if}

	<Collapsible
		bind:open
		className="w-full"
		buttonClassName="w-full"
		hide={(folders[folderId]?.childrenIds ?? []).length === 0 &&
			(folders[folderId].items?.chats ?? []).length === 0}
		onchange={(e: unknown) => {
			onOpen?.((e as CustomEvent).detail);
		}}
	>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="w-full group">
			<button
				id="folder-{folderId}-button"
				class="relative w-full py-1.5 px-2 rounded-md flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-500 font-medium hover:bg-gray-100 dark:hover:bg-gray-900 transition"
				ondblclick={() => {
					editHandler();
				}}
			>
				<div class="text-gray-300 dark:text-gray-600">
					{#if open}
						<ChevronDown className=" size-3" strokeWidth="2.5" />
					{:else}
						<ChevronRight className=" size-3" strokeWidth="2.5" />
					{/if}
				</div>

				<div class="translate-y-[0.5px] flex-1 justify-start text-start line-clamp-1">
					{#if edit}
						<input
							id="folder-{folderId}-input"
							type="text"
							bind:value={name}
							onfocus={(e: FocusEvent) => {
								e.target?.select();
							}}
							onblur={() => {
								nameUpdateHandler();
								edit = false;
							}}
							onclick={(e: MouseEvent) => {
								e.stopPropagation();
							}}
							onmousedown={(e: MouseEvent) => {
								e.stopPropagation();
							}}
							onkeydown={(e: KeyboardEvent) => {
								if (e.key === 'Enter') {
									nameUpdateHandler();
									edit = false;
								}
							}}
							class="w-full h-full bg-transparent text-gray-500 dark:text-gray-500 outline-hidden"
						/>
					{:else}
						{folders[folderId].name}
					{/if}
				</div>

				<div
					class="absolute z-10 right-2 invisible group-hover:visible self-center flex items-center dark:text-gray-300"
					onpointerup={(e: PointerEvent) => {
						e.stopPropagation();
					}}
				>
					<FolderMenu
						onrename={() => {
							setTimeout(() => {
								editHandler();
							}, 200);
						}}
						onDelete={() => {
							showDeleteConfirm = true;
						}}
						onexport={() => {
							exportHandler();
						}}
					>
						<button class="p-0.5 dark:hover:bg-gray-850 rounded-lg touch-auto" onclick={() => {}}>
							<EllipsisHorizontal className="size-4" strokeWidth="2.5" />
						</button>
					</FolderMenu>
				</div>
			</button>
		</div>

		<div slot="content" class="w-full">
			{#if (folders[folderId]?.childrenIds ?? []).length > 0 || (folders[folderId].items?.chats ?? []).length > 0}
				<div
					class="ml-3 pl-1 mt-[1px] flex flex-col overflow-y-auto scrollbar-hidden border-s border-gray-100 dark:border-gray-900"
				>
					{#if folders[folderId]?.childrenIds}
						{@const children = folders[folderId]?.childrenIds
							.map((id) => folders[id])
							.sort((a, b) =>
								a.name.localeCompare(b.name, undefined, {
									numeric: true,
									sensitivity: 'base'
								})
							)}

						{#each children as childFolder (`${folderId}-${childFolder.id}`)}
							<RecursiveFolder
								{folders}
								folderId={childFolder.id}
								parentDragged={dragged}
								onImport={(e: unknown) => {
									onImport?.((e as CustomEvent).detail);
								}}
								onUpdate={(e: CustomEvent) => {
									onUpdate?.(e.detail);
								}}
								onchange={(e: unknown) => {
									onchange?.((e as CustomEvent).detail);
								}}
							/>
						{/each}
					{/if}

					{#if folders[folderId].items?.chats}
						{#each folders[folderId].items.chats as chat (chat.id)}
							<ChatItem
								id={chat.id}
								title={chat.title}
								onchange={(e: unknown) => {
									onchange?.((e as CustomEvent).detail);
								}}
							/>
						{/each}
					{/if}
				</div>
			{/if}
		</div>
	</Collapsible>
</div>
