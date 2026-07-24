<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';
	import { resolve } from '$app/paths';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { page } from '$app/stores';
	import { mobile, showSidebar, user } from '$lib/stores';
	import { updateChannelById } from '$lib/apis/channels';

	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ChannelModal from './ChannelModal.svelte';

	type AccessControlValue = null | {
		read: { group_ids: string[]; user_ids: string[] };
		write: { group_ids: string[]; user_ids: string[] };
	};

	interface Channel {
		id: string;
		name?: string;
		[key: string]: unknown;
	}

	interface ChannelModalChannel {
		id: string;
		name: string;
		access_control: AccessControlValue;
	}

	interface Props {
		/** Callback invoked when channel data is updated */
		onUpdate?: (...args: unknown[]) => void;
		/** Additional CSS class names */
		className?: string;
		/** Channel data object */
		channel?: Channel;
	}

	let { onUpdate = () => {}, className = '', channel = {} as Channel }: Props = $props();

	let showEditChannelModal = $state(false);

	let itemElement;
</script>

<ChannelModal
	bind:show={showEditChannelModal}
	channel={channel as unknown as ChannelModalChannel}
	edit={true}
	{onUpdate}
	onSubmit={async ({ name, access_control }) => {
		const res = await updateChannelById('', channel.id, {
			name,
			access_control: access_control ?? undefined
		}).catch((error) => {
			toast.error(error.message);
		});

		if (res) {
			toast.success($i18n.t('Channel updated successfully'));
		}

		onUpdate();
	}}
/>

<div
	bind:this={itemElement}
	class=" w-full {className} rounded-lg flex relative group hover:bg-gray-100 dark:hover:bg-gray-900 {$page
		.url.pathname === `/channels/${channel.id}`
		? 'bg-gray-100 dark:bg-gray-900'
		: ''} px-2.5 py-1"
>
	<a
		class=" w-full flex justify-between"
		href={resolve(`/channels/${channel.id}`)}
		onclick={() => {
			if ($mobile) {
				showSidebar.set(false);
			}
		}}
		draggable="false"
	>
		<div class="flex items-center gap-1">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 16 16"
				fill="currentColor"
				class="size-5"
			>
				<path
					fill-rule="evenodd"
					d="M7.487 2.89a.75.75 0 1 0-1.474-.28l-.455 2.388H3.61a.75.75 0 0 0 0 1.5h1.663l-.571 2.998H2.75a.75.75 0 0 0 0 1.5h1.666l-.403 2.114a.75.75 0 0 0 1.474.28l.456-2.394h2.973l-.403 2.114a.75.75 0 0 0 1.474.28l.456-2.394h1.947a.75.75 0 0 0 0-1.5h-1.661l.57-2.998h1.95a.75.75 0 0 0 0-1.5h-1.664l.402-2.108a.75.75 0 0 0-1.474-.28l-.455 2.388H7.085l.402-2.108ZM6.8 6.498l-.571 2.998h2.973l.57-2.998H6.8Z"
					clip-rule="evenodd"
				/>
			</svg>

			<div class=" text-left self-center overflow-hidden w-full line-clamp-1">
				{channel.name}
			</div>
		</div>
	</a>

	{#if $user?.role === 'admin'}
		<button
			class="absolute z-10 right-2 invisible group-hover:visible self-center flex items-center dark:text-gray-300"
			onclick={(e: MouseEvent) => {
				e.stopPropagation();
				showEditChannelModal = true;
			}}
		>
			<span
				class="p-0.5 dark:hover:bg-gray-850 rounded-lg touch-auto"
				role="button"
				tabindex="0"
				onclick={(_e: MouseEvent) => {}}
				onkeydown={(e: KeyboardEvent) => {
					if (e.key === 'Enter' || e.key === ' ') {
						// no-op: activation handled via the parent button's onclick
					}
				}}
			>
				<Cog6 className="size-3.5" />
			</span>
		</button>
	{/if}
</div>
