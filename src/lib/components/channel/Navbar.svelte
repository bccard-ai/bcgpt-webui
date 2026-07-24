<script lang="ts">
	import { getContext } from 'svelte';

	import { showArchivedChats, showSidebar, user } from '$lib/stores';

	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import MenuLines from '../icons/MenuLines.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Channel {
		name: string;
		[key: string]: unknown;
	}

	/**
	 * Navigation bar for the channel view. Displays the channel name,
	 * sidebar toggle button, and user menu.
	 *
	 * @example
	 * ```svelte
	 * <Navbar channel={channelData} />
	 * ```
	 *
	 * @param channel - The channel object to display the name for.
	 */
	interface Props {
		channel?: Channel | null;
	}

	let { channel = null }: Props = $props();
</script>

<nav class="sticky top-0 z-30 w-full px-1.5 py-1.5 -mb-8 flex items-center drag-region">
	<div
		class=" bg-linear-to-b via-50% from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pointer-events-none absolute inset-0 -bottom-7 z-[-1]"
	></div>

	<div class=" flex max-w-full w-full mx-auto px-1 pt-0.5 bg-transparent">
		<div class="flex items-center w-full max-w-full">
			<div
				class="{$showSidebar
					? 'md:hidden'
					: ''} mr-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
			>
				<button
					id="sidebar-toggle-button"
					class="cursor-pointer px-2 py-2 flex rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
					onclick={() => {
						showSidebar.set(!$showSidebar);
					}}
					aria-label={$i18n.t('Toggle Sidebar')}
				>
					<div class=" m-auto self-center">
						<MenuLines />
					</div>
				</button>
			</div>

			<div
				class="flex-1 overflow-hidden max-w-full py-0.5
			{$showSidebar ? 'ml-1' : ''}
			"
			>
				{#if channel}
					<div class="line-clamp-1 capitalize font-medium font-primary text-lg">
						{channel.name}
					</div>
				{/if}
			</div>

			<div class="self-start flex flex-none items-center text-gray-600 dark:text-gray-400">
				{#if $user !== undefined}
					<UserMenu
						className="max-w-[200px]"
						role={$user.role}
						onshow={(e: CustomEvent) => {
							if (e.detail === 'archived-chat') {
								showArchivedChats.set(true);
							}
						}}
					>
						<button
							class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							aria-label={$i18n.t('User Menu')}
						>
							<div class=" self-center">
								<img
									src={$user.profile_image_url}
									class="size-6 object-cover rounded-full"
									alt={$i18n.t('User profile')}
									draggable="false"
								/>
							</div>
						</button>
					</UserMenu>
				{/if}
			</div>
		</div>
	</div>
</nav>
