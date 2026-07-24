<script lang="ts">
	/**
	 * Admin Groups Page
	 *
	 * Manages user groups for bulk permission assignment.
	 * Displays searchable group list, create-group modal, and
	 * default-permissions editor for the "user" role.
	 */
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	dayjs.extend(relativeTime);

	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import { user } from '$lib/stores';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import UsersSolid from '$lib/components/icons/UsersSolid.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import GroupModal from './Groups/EditGroupModal.svelte';
	import GroupItem from './Groups/GroupItem.svelte';
	import AddGroupModal from './Groups/AddGroupModal.svelte';
	import { createNewGroup, getGroups } from '$lib/apis/groups';
	import { getUserDefaultPermissions, updateUserDefaultPermissions } from '$lib/apis/users';
	import EmptyState from '$lib/components/common/EmptyState.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Group {
		id: string;
		name: string;
		description?: string;
		user_ids?: (string | number)[];
		permissions?: Record<string, unknown>;
	}

	let { users = [] } = $props();

	// --- State ---
	let loaded = $state(false);
	let groups = $state<Group[]>([]);
	let search = $state('');
	let showCreateGroupModal = $state(false);
	let showDefaultPermissionsModal = $state(false);
	let defaultPermissions = $state({
		workspace: {
			models: false,
			knowledge: false,
			prompts: false,
			tools: false
		},
		sharing: {
			public_models: false,
			public_knowledge: false,
			public_prompts: false,
			public_tools: false
		},
		chat: {
			controls: true,
			file_upload: true,
			delete: true,
			edit: true,
			temporary: true,
			temporary_enforced: true
		},
		features: {
			web_search: true,
			image_generation: true,
			code_interpreter: true
		}
	});

	/** Groups filtered by the current search query */
	let filteredGroups = $derived(
		groups.filter((user) => {
			if (search === '') {
				return true;
			} else {
				let name = user.name.toLowerCase();
				const query = search.toLowerCase();
				return name.includes(query);
			}
		})
	);

	/**
	 * Refresh the groups list from the backend.
	 */
	const setGroups = async () => {
		groups = (await getGroups('')) as Group[];
	};

	/**
	 * Create a new group and refresh the list.
	 * @param group - Partial group object with name/description
	 */
	const addGroupHandler = async (group) => {
		const res = await createNewGroup('', group).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('Group created successfully'));
			groups = (await getGroups('')) as Group[];
		}
	};

	/**
	 * Update default permissions for all users with the "user" role.
	 * @param group - Object with updated permissions
	 */
	const updateDefaultPermissionsHandler = async (group) => {
		const res = await updateUserDefaultPermissions('', group.permissions).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('Default permissions updated successfully'));
			defaultPermissions = await getUserDefaultPermissions('');
		}
	};

	onMount(async () => {
		if (get(user)?.role !== 'admin') {
			await goto(resolve('/'));
		} else {
			await setGroups();
			defaultPermissions = await getUserDefaultPermissions('');
		}
		loaded = true;
	});
</script>

{#if loaded}
	<AddGroupModal bind:show={showCreateGroupModal} onSubmit={addGroupHandler} />
	<InfoCallout
		>{$i18n.t(
			'Create user groups to assign permissions to many users at once. Default permissions below apply to every user with the "user" role.'
		)}</InfoCallout
	>

	<div class="mt-0.5 mb-2 gap-1 flex flex-row items-center justify-between">
		<div class="flex md:self-center text-lg font-medium px-0.5">
			{$i18n.t('Groups')}
			<div class="flex self-center w-[1px] h-6 mx-2.5 bg-gray-50 dark:bg-gray-850"></div>

			<span class="text-lg font-medium text-gray-500 dark:text-gray-300">{groups.length}</span>
		</div>

		<div class="flex gap-1">
			<div class=" flex w-full space-x-2">
				<div class="flex flex-1">
					<div class=" self-center ml-1 mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<input
						class=" w-full text-sm pr-4 py-1 rounded-r-xl outline-hidden bg-transparent"
						bind:value={search}
						placeholder={$i18n.t('Search')}
					/>
				</div>

				<div>
					<Tooltip content={$i18n.t('Create Group')}>
						<button
							class=" p-2 rounded-xl hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-850 transition font-medium text-sm flex items-center space-x-1"
							onclick={() => {
								showCreateGroupModal = !showCreateGroupModal;
							}}
						>
							<Plus className="size-3.5" />
						</button>
					</Tooltip>
				</div>
			</div>
		</div>
	</div>

	<div>
		{#if filteredGroups.length === 0}
			<EmptyState
				icon="groups"
				title={$i18n.t('Organize your users')}
				description={$i18n.t('Use groups to group your users and assign permissions.')}
				actionLabel={$i18n.t('Create Group')}
				actionHandler={() => {
					showCreateGroupModal = true;
				}}
			/>
		{:else}
			<div>
				<div class=" flex items-center gap-3 justify-between text-xs uppercase px-1 font-bold">
					<div class="w-full">Group</div>

					<div class="w-full">Users</div>

					<div class="w-full"></div>
				</div>

				<hr class="mt-1.5 border-gray-100 dark:border-gray-850" />

				{#each filteredGroups as group (group.id)}
					<div class="my-2">
						<GroupItem {group} {users} {setGroups} />
					</div>
				{/each}
			</div>
		{/if}

		<hr class="mb-2 border-gray-100 dark:border-gray-850" />

		<GroupModal
			bind:show={showDefaultPermissionsModal}
			tabs={['permissions']}
			bind:permissions={defaultPermissions}
			custom={false}
			onSubmit={updateDefaultPermissionsHandler}
		/>

		<button
			class="flex items-center justify-between rounded-lg w-full transition pt-1"
			onclick={() => {
				showDefaultPermissionsModal = true;
			}}
		>
			<div class="flex items-center gap-2.5">
				<div class="p-1.5 bg-black/5 dark:bg-white/10 rounded-full">
					<UsersSolid className="size-4" />
				</div>

				<div class="text-left">
					<div class=" text-sm font-medium">{$i18n.t('Default permissions')}</div>

					<div class="flex text-xs mt-0.5">
						{$i18n.t('applies to all users with the "user" role')}
					</div>
				</div>
			</div>

			<div>
				<ChevronRight strokeWidth="2.5" />
			</div>
		</button>
	</div>
{/if}
