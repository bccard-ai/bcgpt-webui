<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { copyToClipboard, createMessagesList } from '$lib/utils';

	import {
		showOverview,
		showControls,
		showArtifacts,
		mobile,
		temporaryChatEnabled
	} from '$lib/stores';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tags from '$lib/components/chat/Tags.svelte';
	import Map from '$lib/components/icons/Map.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';
	import AdjustmentsHorizontal from '$lib/components/icons/AdjustmentsHorizontal.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import { getChatById } from '$lib/apis/chats';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface ChatData {
		id?: string;
		chat: {
			history: { currentId: string | null; [key: string]: unknown };
			title: string;
			[key: string]: unknown;
		};
		[key: string]: unknown;
	}

	interface Props {
		/** Whether sharing is enabled for this chat */
		shareEnabled?: boolean;
		/** Callback to open the share modal */
		shareHandler: () => void;
		/** Callback to open the download modal */
		downloadHandler: () => void;
		/** Current chat data object */
		chat: ChatData;
		/** Callback when the menu is closed */
		onClose?: () => void;
		/** Snippet for the trigger element */
		children?: import('svelte').Snippet;
	}

	let {
		shareEnabled: _shareEnabled = false,
		shareHandler,
		downloadHandler: _downloadHandler,
		chat,
		onClose = () => {},
		children
	}: Props = $props();

	const getChatAsText = async () => {
		const history = chat.chat.history;
		const messages = createMessagesList(history, history.currentId);
		const chatText = messages.reduce((a: string, message, _i: number, _arr: unknown[]) => {
			return `${a}### ${message.role.toUpperCase()}\n${message.content}\n\n`;
		}, '');

		return chatText.trim();
	};

	const downloadTxt = async () => {
		const chatText = await getChatAsText();

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

		const containerElement = document.getElementById('messages-container');

		if (containerElement) {
			try {
				const isDarkMode = document.documentElement.classList.contains('dark');

				const virtualWidth = 800;
				const clonedElement = containerElement.cloneNode(true);
				clonedElement.classList.add('text-black');
				clonedElement.classList.add('dark:text-white');
				clonedElement.style.width = `${virtualWidth}px`;
				clonedElement.style.height = 'auto';

				document.body.appendChild(clonedElement);

				const canvas = await html2canvas(clonedElement, {
					backgroundColor: isDarkMode ? '#000' : '#fff',
					useCORS: true,
					scale: 2,
					width: virtualWidth,
					windowWidth: virtualWidth
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
		if (chat.id) {
			let chatObj;

			if (chat.id === 'local' || get(temporaryChatEnabled)) {
				chatObj = chat;
			} else {
				chatObj = await getChatById('', chat.id);
			}

			let blob = new Blob([JSON.stringify([chatObj])], {
				type: 'application/json'
			});
			saveAs(blob, `chat-export-${Date.now()}.json`);
		}
	};
</script>

<Dropdown
	onchange={(state: boolean) => {
		if (state === false) {
			onClose();
		}
	}}
>
	{@render children?.()}

	{#snippet content()}
		<div>
			<DropdownMenu.Portal>
				<DropdownMenu.Content
					class="w-full max-w-[200px] rounded-xl px-1 py-1.5  z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					sideOffset={8}
					side="bottom"
					align="end"
				>
					{#if $mobile}
						<DropdownMenu.Item
							class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
							id="chat-controls-button"
							onclick={async () => {
								await showControls.set(true);
								await showOverview.set(false);
								await showArtifacts.set(false);
							}}
						>
							<AdjustmentsHorizontal className=" size-4" strokeWidth="0.5" />
							<div class="flex items-center">{$i18n.t('Controls')}</div>
						</DropdownMenu.Item>
					{/if}

					{#if !$temporaryChatEnabled}
						<DropdownMenu.Item
							class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
							id="chat-share-button"
							onclick={() => {
								shareHandler();
							}}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="currentColor"
								class="size-4"
							>
								<path
									fill-rule="evenodd"
									d="M15.75 4.5a3 3 0 1 1 .825 2.066l-8.421 4.679a3.002 3.002 0 0 1 0 1.51l8.421 4.679a3 3 0 1 1-.729 1.31l-8.421-4.678a3 3 0 1 1 0-4.132l8.421-4.679a3 3 0 0 1-.096-.755Z"
									clip-rule="evenodd"
								/>
							</svg>
							<div class="flex items-center">{$i18n.t('Share')}</div>
						</DropdownMenu.Item>
					{/if}

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						id="chat-overview-button"
						onclick={async () => {
							await showControls.set(true);
							await showOverview.set(true);
							await showArtifacts.set(false);
						}}
					>
						<Map className=" size-4" strokeWidth="1.5" />
						<div class="flex items-center">{$i18n.t('Overview')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						id="chat-overview-button"
						onclick={async () => {
							await showControls.set(true);
							await showArtifacts.set(true);
							await showOverview.set(false);
						}}
					>
						<Cube className=" size-4" strokeWidth="1.5" />
						<div class="flex items-center">{$i18n.t('Artifacts')}</div>
					</DropdownMenu.Item>

					<DropdownMenu.Sub>
						<DropdownMenu.SubTrigger
							class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="1.5"
								stroke="currentColor"
								class="size-4"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
								/>
							</svg>

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
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						id="chat-copy-button"
						onclick={async () => {
							const res = await copyToClipboard(await getChatAsText()).catch(() => {});

							if (res) {
								toast.success($i18n.t('Copied to clipboard'));
							}
						}}
					>
						<Clipboard className=" size-4" strokeWidth="1.5" />
						<div class="flex items-center">{$i18n.t('Copy')}</div>
					</DropdownMenu.Item>

					{#if !$temporaryChatEnabled}
						<hr class="border-gray-100 dark:border-gray-850 my-0.5" />

						<div class="flex p-1">
							<Tags chatId={chat.id} />
						</div>
					{/if}
				</DropdownMenu.Content>
			</DropdownMenu.Portal>
		</div>
	{/snippet}
</Dropdown>
