<script lang="ts">
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';

	import { config, settings, user } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { updateUserInfo } from '$lib/apis/users';
	import { getUserPosition } from '$lib/utils';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		saveSettings: (settings: Record<string, unknown>) => void;

		onSave?: (...args: unknown[]) => void;
	}

	let { saveSettings, onSave = () => {} }: Props = $props();

	let backgroundImageUrl = $state(null);
	let inputFiles = $state(null);
	let filesInputElement = $state();

	// Addons
	let titleAutoGenerate = $state(true);
	let autoTags = $state(true);

	let responseAutoCopy = $state(false);
	let widescreenMode = $state(false);
	let splitLargeChunks = $state(false);
	let scrollOnBranchChange = $state(true);
	let userLocation = $state(false);

	// Interface
	let defaultModelId = '';
	let showUsername = $state(false);
	let notificationSound = $state(true);

	let richTextInput = $state(true);
	let promptAutocomplete = $state(false);

	let largeTextAsFile = $state(false);

	let landingPageMode = $state('');
	let chatBubble = $state(true);
	let chatDirection: 'LTR' | 'RTL' = $state('LTR');
	let ctrlEnterToSend = $state(false);

	let collapseCodeBlocks = $state(false);
	let expandDetails = $state(false);

	let imageCompression = $state(false);
	let imageCompressionSize = $state({
		width: '',
		height: ''
	});

	// Admin - Show Update Available Toast
	let showUpdateToast = $state(true);
	let showChangelog = $state(true);

	let showEmojiInCall = $state(false);
	let voiceInterruption = $state(false);
	let hapticFeedback = $state(false);

	let webSearch = $state(null);

	const toggleExpandDetails = () => {
		expandDetails = !expandDetails;
		saveSettings({ expandDetails });
	};

	const toggleCollapseCodeBlocks = () => {
		collapseCodeBlocks = !collapseCodeBlocks;
		saveSettings({ collapseCodeBlocks });
	};

	const _toggleSplitLargeChunks = async () => {
		splitLargeChunks = !splitLargeChunks;
		saveSettings({ splitLargeChunks: splitLargeChunks });
	};

	const togglePromptAutocomplete = async () => {
		promptAutocomplete = !promptAutocomplete;
		saveSettings({ promptAutocomplete: promptAutocomplete });
	};

	const togglesScrollOnBranchChange = async () => {
		scrollOnBranchChange = !scrollOnBranchChange;
		saveSettings({ scrollOnBranchChange: scrollOnBranchChange });
	};

	const toggleWidescreenMode = async () => {
		widescreenMode = !widescreenMode;
		saveSettings({ widescreenMode: widescreenMode });
	};

	const toggleChatBubble = async () => {
		chatBubble = !chatBubble;
		saveSettings({ chatBubble: chatBubble });
	};

	const toggleLandingPageMode = async () => {
		landingPageMode = landingPageMode === '' ? 'chat' : '';
		saveSettings({ landingPageMode: landingPageMode });
	};

	const toggleShowUpdateToast = async () => {
		showUpdateToast = !showUpdateToast;
		saveSettings({ showUpdateToast: showUpdateToast });
	};

	const toggleNotificationSound = async () => {
		notificationSound = !notificationSound;
		saveSettings({ notificationSound: notificationSound });
	};

	const toggleShowChangelog = async () => {
		showChangelog = !showChangelog;
		saveSettings({ showChangelog: showChangelog });
	};

	const toggleShowUsername = async () => {
		showUsername = !showUsername;
		saveSettings({ showUsername: showUsername });
	};

	const toggleEmojiInCall = async () => {
		showEmojiInCall = !showEmojiInCall;
		saveSettings({ showEmojiInCall: showEmojiInCall });
	};

	const toggleVoiceInterruption = async () => {
		voiceInterruption = !voiceInterruption;
		saveSettings({ voiceInterruption: voiceInterruption });
	};

	const toggleImageCompression = async () => {
		imageCompression = !imageCompression;
		saveSettings({ imageCompression });
	};

	const toggleHapticFeedback = async () => {
		hapticFeedback = !hapticFeedback;
		saveSettings({ hapticFeedback: hapticFeedback });
	};

	const toggleUserLocation = async () => {
		userLocation = !userLocation;

		if (userLocation) {
			const position = await getUserPosition().catch((error) => {
				toast.error(error.message);
				return null;
			});

			if (position) {
				await updateUserInfo('', { location: position });
				toast.success($i18n.t('User location successfully retrieved.'));
			} else {
				userLocation = false;
			}
		}

		saveSettings({ userLocation });
	};

	const toggleTitleAutoGenerate = async () => {
		titleAutoGenerate = !titleAutoGenerate;
		saveSettings({
			title: {
				...get(settings).title,
				auto: titleAutoGenerate
			}
		});
	};

	const toggleAutoTags = async () => {
		autoTags = !autoTags;
		saveSettings({ autoTags });
	};

	const toggleRichTextInput = async () => {
		richTextInput = !richTextInput;
		saveSettings({ richTextInput });
	};

	const toggleLargeTextAsFile = async () => {
		largeTextAsFile = !largeTextAsFile;
		saveSettings({ largeTextAsFile });
	};

	const toggleResponseAutoCopy = async () => {
		const permission = await navigator.clipboard
			.readText()
			.then(() => 'granted')
			.catch(() => '');

		if (permission === 'granted') {
			responseAutoCopy = !responseAutoCopy;
			saveSettings({ responseAutoCopy: responseAutoCopy });
		} else {
			toast.error(
				$i18n.t(
					'Clipboard write permission denied. Please check your browser settings to grant the necessary access.'
				)
			);
		}
	};

	const toggleChangeChatDirection = async () => {
		chatDirection = chatDirection === 'LTR' ? 'RTL' : 'LTR';
		saveSettings({ chatDirection });
	};

	const toggleCtrlEnterToSend = async () => {
		ctrlEnterToSend = !ctrlEnterToSend;
		saveSettings({ ctrlEnterToSend });
	};

	const updateInterfaceHandler = async () => {
		saveSettings({
			models: [defaultModelId],
			imageCompressionSize: imageCompressionSize
		});
	};

	const toggleWebSearch = async () => {
		webSearch = webSearch === null ? 'always' : null;
		saveSettings({ webSearch: webSearch });
	};

	onMount(async () => {
		titleAutoGenerate = get(settings)?.title?.auto ?? true;
		autoTags = get(settings).autoTags ?? true;

		responseAutoCopy = get(settings).responseAutoCopy ?? false;

		showUsername = get(settings).showUsername ?? false;
		showUpdateToast = get(settings).showUpdateToast ?? true;
		showChangelog = get(settings).showChangelog ?? true;

		showEmojiInCall = get(settings).showEmojiInCall ?? false;
		voiceInterruption = get(settings).voiceInterruption ?? false;

		richTextInput = get(settings).richTextInput ?? true;
		promptAutocomplete = get(settings).promptAutocomplete ?? false;
		largeTextAsFile = get(settings).largeTextAsFile ?? false;

		collapseCodeBlocks = get(settings).collapseCodeBlocks ?? false;
		expandDetails = get(settings).expandDetails ?? false;

		landingPageMode = get(settings).landingPageMode ?? '';
		chatBubble = get(settings).chatBubble ?? true;
		widescreenMode = get(settings).widescreenMode ?? false;
		splitLargeChunks = get(settings).splitLargeChunks ?? false;
		scrollOnBranchChange = get(settings).scrollOnBranchChange ?? true;
		chatDirection = get(settings).chatDirection ?? 'LTR';
		userLocation = get(settings).userLocation ?? false;

		notificationSound = get(settings).notificationSound ?? true;

		hapticFeedback = get(settings).hapticFeedback ?? false;
		ctrlEnterToSend = get(settings).ctrlEnterToSend ?? false;

		imageCompression = get(settings).imageCompression ?? false;
		imageCompressionSize = get(settings).imageCompressionSize ?? { width: '', height: '' };

		defaultModelId = get(settings)?.models?.at(0) ?? '';
		if (get(config)?.default_models) {
			defaultModelId = get(config).default_models.split(',')[0];
		}

		backgroundImageUrl = get(settings).backgroundImageUrl ?? null;
		webSearch = get(settings).webSearch ?? null;
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(() => {
		updateInterfaceHandler();
		onSave?.();
	})}
>
	<input
		bind:this={filesInputElement}
		bind:files={inputFiles}
		type="file"
		hidden
		accept="image/*"
		onchange={() => {
			let reader = new FileReader();
			reader.onload = (event) => {
				let originalImageUrl = `${event.target?.result}`;

				backgroundImageUrl = originalImageUrl;
				saveSettings({ backgroundImageUrl });
			};

			if (
				inputFiles &&
				inputFiles.length > 0 &&
				['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(inputFiles[0]['type'])
			) {
				reader.readAsDataURL(inputFiles[0]);
			} else {
				inputFiles = null;
			}
		}}
	/>

	<div class=" space-y-3 overflow-y-scroll max-h-[28rem] lg:max-h-full">
		<div>
			<div class=" mb-1.5 text-sm font-medium">{$i18n.t('UI')}</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Landing Page Mode')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleLandingPageMode();
						}}
						type="button"
					>
						{#if landingPageMode === ''}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Chat')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Chat Bubble UI')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleChatBubble();
						}}
						type="button"
					>
						{#if chatBubble === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			{#if !$settings.chatBubble}
				<div>
					<div
						class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
					>
						<div class=" self-center text-xs">
							{$i18n.t('Display the username instead of You in the Chat')}
						</div>

						<button
							class="p-1 px-3 text-xs flex rounded-sm transition"
							onclick={() => {
								toggleShowUsername();
							}}
							type="button"
						>
							{#if showUsername === true}
								<span class="ml-2 self-center">{$i18n.t('On')}</span>
							{:else}
								<span class="ml-2 self-center">{$i18n.t('Off')}</span>
							{/if}
						</button>
					</div>
				</div>
			{/if}

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Widescreen Mode')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleWidescreenMode();
						}}
						type="button"
					>
						{#if widescreenMode === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Chat direction')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={toggleChangeChatDirection}
						type="button"
					>
						{#if chatDirection === 'LTR'}
							<span class="ml-2 self-center">{$i18n.t('LTR')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('RTL')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Notification Sound')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleNotificationSound();
						}}
						type="button"
					>
						{#if notificationSound === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			{#if $user.role === 'admin'}
				<div>
					<div
						class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
					>
						<div class=" self-center text-xs">
							{$i18n.t('Toast notifications for new updates')}
						</div>

						<button
							class="p-1 px-3 text-xs flex rounded-sm transition"
							onclick={() => {
								toggleShowUpdateToast();
							}}
							type="button"
						>
							{#if showUpdateToast === true}
								<span class="ml-2 self-center">{$i18n.t('On')}</span>
							{:else}
								<span class="ml-2 self-center">{$i18n.t('Off')}</span>
							{/if}
						</button>
					</div>
				</div>

				<div>
					<div
						class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
					>
						<div class=" self-center text-xs">
							{$i18n.t(`Show "What's New" modal on login`)}
						</div>

						<button
							class="p-1 px-3 text-xs flex rounded-sm transition"
							onclick={() => {
								toggleShowChangelog();
							}}
							type="button"
						>
							{#if showChangelog === true}
								<span class="ml-2 self-center">{$i18n.t('On')}</span>
							{:else}
								<span class="ml-2 self-center">{$i18n.t('Off')}</span>
							{/if}
						</button>
					</div>
				</div>
			{/if}

			<div class=" my-1.5 text-sm font-medium">{$i18n.t('Chat')}</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Title Auto-Generation')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleTitleAutoGenerate();
						}}
						type="button"
					>
						{#if titleAutoGenerate === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Chat Tags Auto-Generation')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleAutoTags();
						}}
						type="button"
					>
						{#if autoTags === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Auto-Copy Response to Clipboard')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleResponseAutoCopy();
						}}
						type="button"
					>
						{#if responseAutoCopy === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Rich Text Input for Chat')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleRichTextInput();
						}}
						type="button"
					>
						{#if richTextInput === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			{#if $config?.features?.enable_autocomplete_generation && richTextInput}
				<div>
					<div
						class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
					>
						<div class=" self-center text-xs">
							{$i18n.t('Prompt Autocompletion')}
						</div>

						<button
							class="p-1 px-3 text-xs flex rounded-sm transition"
							onclick={() => {
								togglePromptAutocomplete();
							}}
							type="button"
						>
							{#if promptAutocomplete === true}
								<span class="ml-2 self-center">{$i18n.t('On')}</span>
							{:else}
								<span class="ml-2 self-center">{$i18n.t('Off')}</span>
							{/if}
						</button>
					</div>
				</div>
			{/if}

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Paste Large Text as File')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleLargeTextAsFile();
						}}
						type="button"
					>
						{#if largeTextAsFile === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Always Collapse Code Blocks')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleCollapseCodeBlocks();
						}}
						type="button"
					>
						{#if collapseCodeBlocks === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Always Expand Details')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleExpandDetails();
						}}
						type="button"
					>
						{#if expandDetails === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Chat Background Image')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							if (backgroundImageUrl !== null) {
								backgroundImageUrl = null;
								saveSettings({ backgroundImageUrl });
							} else {
								filesInputElement.click();
							}
						}}
						type="button"
					>
						{#if backgroundImageUrl !== null}
							<span class="ml-2 self-center">{$i18n.t('Reset')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Upload')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Allow User Location')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleUserLocation();
						}}
						type="button"
					>
						{#if userLocation === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Haptic Feedback')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleHapticFeedback();
						}}
						type="button"
					>
						{#if hapticFeedback === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<!-- <div>
				<div class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed">
					<div class=" self-center text-xs">
						{$i18n.t('Fluidly stream large external response chunks')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleSplitLargeChunks();
						}}
						type="button"
					>
						{#if splitLargeChunks === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div> -->

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Enter Key Behavior')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded transition"
						onclick={() => {
							toggleCtrlEnterToSend();
						}}
						type="button"
					>
						{#if ctrlEnterToSend === true}
							<span class="ml-2 self-center">{$i18n.t('Ctrl+Enter to Send')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Enter to Send')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">
						{$i18n.t('Scroll to bottom when switching between branches')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							togglesScrollOnBranchChange();
						}}
						type="button"
					>
						{#if scrollOnBranchChange === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Web Search in Chat')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleWebSearch();
						}}
						type="button"
					>
						{#if webSearch === 'always'}
							<span class="ml-2 self-center">{$i18n.t('Always')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div class=" my-1.5 text-sm font-medium">{$i18n.t('Voice')}</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Allow Voice Interruption in Call')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleVoiceInterruption();
						}}
						type="button"
					>
						{#if voiceInterruption === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Display Emoji in Call')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleEmojiInCall();
						}}
						type="button"
					>
						{#if showEmojiInCall === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			<div class=" my-1.5 text-sm font-medium">{$i18n.t('File')}</div>

			<div>
				<div
					class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-xs">{$i18n.t('Image Compression')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleImageCompression();
						}}
						type="button"
					>
						{#if imageCompression === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>

			{#if imageCompression}
				<div>
					<div class=" py-0.5 flex w-full justify-between text-xs">
						<div class=" self-center text-xs">{$i18n.t('Image Max Compression Size')}</div>

						<div>
							<input
								bind:value={imageCompressionSize.width}
								type="number"
								class="w-20 bg-transparent outline-hidden text-center"
								min="0"
								placeholder={$i18n.t('Width')}
							/>x
							<input
								bind:value={imageCompressionSize.height}
								type="number"
								class="w-20 bg-transparent outline-hidden text-center"
								min="0"
								placeholder={$i18n.t('Height')}
							/>
						</div>
					</div>
				</div>
			{/if}
		</div>
	</div>

	<div class="flex justify-end text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
