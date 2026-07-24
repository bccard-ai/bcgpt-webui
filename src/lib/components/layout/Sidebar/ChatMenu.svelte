<script lang="ts">
	import { get } from 'svelte/store';
	import { getContext } from 'svelte';

	import { DropdownMenu } from 'bits-ui';
	import { toast } from 'svelte-sonner';

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Tags from '$lib/components/chat/Tags.svelte';
	import Share from '$lib/components/icons/Share.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';
	import Bookmark from '$lib/components/icons/Bookmark.svelte';
	import BookmarkSlash from '$lib/components/icons/BookmarkSlash.svelte';
	import {
		getChatById,
		getChatPinnedStatusById,
		toggleChatPinnedStatusById
	} from '$lib/apis/chats';
	import { theme } from '$lib/stores';
	import { createMessagesList } from '$lib/utils';
	import Download from '$lib/components/icons/Download.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Callback to open the share modal */
		shareHandler: () => void;
		/** Callback to clone the chat */
		cloneChatHandler: () => void;
		/** Callback to archive the chat */
		archiveChatHandler: () => void;
		/** Callback to start renaming the chat */
		renameHandler: () => void;
		/** Callback to delete the chat */
		deleteHandler: () => void;
		/** Callback when the menu is closed */
		onClose: () => void;
		/** The chat ID for API calls */
		chatId?: string;
		/** Snippet for the trigger element */
		children?: import('svelte').Snippet;
		/** Callback invoked when chat data changes (e.g., pin toggle) */
		onchange?: (...args: unknown[]) => void;
		/** Callback invoked when a tag is added or removed */
		ontag?: (payload: { type: 'add' | 'delete'; name: string }) => void;
	}

	let {
		shareHandler,
		cloneChatHandler,
		archiveChatHandler,
		renameHandler,
		deleteHandler,
		onClose,
		chatId = '',
		children,
		onchange = () => {},
		ontag = () => {}
	}: Props = $props();

	let show = $state(false);
	let pinned = $state(false);

	const pinHandler = async () => {
		await toggleChatPinnedStatusById('', chatId);
		onchange?.();
	};

	const checkPinned = async () => {
		pinned = await getChatPinnedStatusById('', chatId);
	};

	const getChatAsText = async (chat) => {
		const history = chat.chat.history;
		const messages = createMessagesList(history, history.currentId);
		const chatText = messages.reduce((a, message) => {
			return `${a}### ${message.role.toUpperCase()}\n${message.content}\n\n`;
		}, '');

		return chatText.trim();
	};

	const downloadTxt = async () => {
		const chat = await getChatById('', chatId);
		if (!chat) {
			return;
		}

		const chatText = await getChatAsText(chat);
		let blob = new Blob([chatText], {
			type: 'text/plain'
		});

		saveAs(blob, `chat-${chat.chat.title}.txt`);
	};

	const downloadPdf = async () => {
		const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
			import('jspdf'),
			import('html2canvas-pro')
		]);

		const chat = await getChatById('', chatId);

		const containerElement = document.getElementById('messages-container');

		if (containerElement) {
			try {
				const isDarkMode = get(theme).includes('dark');

				const virtualWidth = 1024;
				const virtualHeight = 1400;

				const clonedElement = containerElement.cloneNode(true);
				clonedElement.style.width = `${virtualWidth}px`;
				clonedElement.style.height = 'auto';

				document.body.appendChild(clonedElement);

				const canvas = await html2canvas(clonedElement, {
					backgroundColor: isDarkMode ? '#000' : '#fff',
					useCORS: true,
					scale: 2,
					width: virtualWidth,
					windowWidth: virtualWidth,
					windowHeight: virtualHeight
				});

				document.body.removeChild(clonedElement);

				const imgData = canvas.toDataURL('image/png');

				const pdf = new jsPDF('p', 'mm', 'a4');
				const imgWidth = 210;
				const pageHeight = 297;

				const imgHeight = (canvas.height * imgWidth) / canvas.width;
				let heightLeft = imgHeight;
				let position = 0;

				if (isDarkMode) {
					pdf.setFillColor(0, 0, 0);
					pdf.rect(0, 0, imgWidth, pageHeight, 'F');
				}

				pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
				heightLeft -= pageHeight;

				while (heightLeft > 0) {
					position -= pageHeight;
					pdf.addPage();

					if (isDarkMode) {
						pdf.setFillColor(0, 0, 0);
						pdf.rect(0, 0, imgWidth, pageHeight, 'F');
					}

					pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
					heightLeft -= pageHeight;
				}

				pdf.save(`chat-${chat.chat.title}.pdf`);
			} catch (_error) {
				toast.error($i18n.t('Failed to generate PDF'));
			}
		}
	};

	const downloadJSONExport = async () => {
		const chat = await getChatById('', chatId);

		if (chat) {
			let blob = new Blob([JSON.stringify([chat])], {
				type: 'application/json'
			});
			saveAs(blob, `chat-export-${Date.now()}.json`);
		}
	};

	$effect(() => {
		if (show) {
			checkPinned();
		}
	});
</script>

<Dropdown
	bind:show
	onchange={(state: boolean) => {
		if ((state as unknown as CustomEvent).detail === false) {
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('More')}>
		{@render children?.()}
	</Tooltip>

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-[200px] rounded-xl px-1 py-1.5 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					sideOffset={-2}
					side="bottom"
					align="start"
				>
					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							pinHandler();
						}}
					>
						{#if pinned}
							<BookmarkSlash strokeWidth="2" />
							<div class="flex items-center">{$i18n.t('Unpin')}</div>
						{:else}
							<Bookmark strokeWidth="2" />
							<div class="flex items-center">{$i18n.t('Pin')}</div>
						{/if}
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							renameHandler();
						}}
					>
						<Pencil strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Rename')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							cloneChatHandler();
						}}
					>
						<DocumentDuplicate strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Clone')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							archiveChatHandler();
						}}
					>
						<ArchiveBox strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Archive')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800  rounded-md"
						onclick={() => {
							shareHandler();
						}}
					>
						<Share />
						<div class="flex items-center">{$i18n.t('Share')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Sub>
						<DropdownMenu.SubTrigger
							class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						>
							<Download strokeWidth="2" />

							<div class="flex items-center">{$i18n.t('Download')}</div>
						</DropdownMenu.SubTrigger>
						<DropdownMenu.SubContent
							class="w-full rounded-xl px-1 py-1.5 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
							sideOffset={8}
						>
							<DropdownMenu.Item
								class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								onclick={() => {
									downloadJSONExport();
								}}
							>
								<div class="flex items-center line-clamp-1">{$i18n.t('Export chat (.json)')}</div>
							</DropdownMenu.Item>
							<DropdownMenu.Item
								class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								onclick={() => {
									downloadTxt();
								}}
							>
								<div class="flex items-center line-clamp-1">{$i18n.t('Plain text (.txt)')}</div>
							</DropdownMenu.Item>

							<DropdownMenu.Item
								class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
								onclick={() => {
									downloadPdf();
								}}
							>
								<div class="flex items-center line-clamp-1">{$i18n.t('PDF document (.pdf)')}</div>
							</DropdownMenu.Item>
						</DropdownMenu.SubContent>
					</DropdownMenu.Sub>
					<DropdownMenu.Item
						class="flex  gap-2  items-center px-3 py-1.5 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						onclick={() => {
							deleteHandler();
						}}
					>
						<GarbageBin strokeWidth="2" />
						<div class="flex items-center">{$i18n.t('Delete')}</div>
					</DropdownMenu.Item>

					<hr class="border-gray-100 dark:border-gray-850 my-0.5" />

					<div class="flex p-1">
						<Tags
							{chatId}
							onAdd={(e: CustomEvent) => {
								ontag?.({
									type: 'add',
									name: e.detail.name
								});

								show = false;
							}}
							onDelete={(e: CustomEvent) => {
								ontag?.({
									type: 'delete',
									name: e.detail.name
								});

								show = false;
							}}
							onClose={() => {
								show = false;
								onClose();
							}}
						/>
					</div>
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
