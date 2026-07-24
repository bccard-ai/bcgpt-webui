<script lang="ts">
	/**
	 * Admin User List
	 *
	 * Paginated, searchable, sortable table of all user accounts.
	 * Supports role changes, account unlocking, bulk deletion, CSV export,
	 * and modals for add/edit/chats.
	 */

	import { APP_BASE_URL } from '$lib/constants';
	import { config, user } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	dayjs.extend(relativeTime);
	dayjs.extend(localizedFormat);

	import { toast } from 'svelte-sonner';

	import { updateUserRole, getUsers, deleteUserById } from '$lib/apis/users';
	import { unlockUserAccount, getUserLockoutStatuses } from '$lib/apis/auths';

	import Pagination from '$lib/components/common/Pagination.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import ChatBubbles from '$lib/components/icons/ChatBubbles.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import EditUserModal from '$lib/components/admin/Users/UserList/EditUserModal.svelte';
	import UserChatsModal from '$lib/components/admin/Users/UserList/UserChatsModal.svelte';
	import AddUserModal from '$lib/components/admin/Users/UserList/AddUserModal.svelte';

	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface ListUser {
		id: string;
		profile_image_url: string;
		name: string;
		email: string;
		password: string;
		role: string;
		last_active_at: number;
		created_at: number;
		oauth_sub?: string | null;
	}

	let { users = [] } = $props();

	// --- Search & selection ---
	let search = $state('');
	let selectedUser = $state<ListUser | null>(null);
	type LockoutStatuses = Record<string, { is_locked?: boolean }>;
	let lockoutStatuses = $state<LockoutStatuses>({});
	let selectedUserIds: string[] = $state([]);

	// --- Pagination ---
	let perPage = $state(20);
	let page = $state(1);

	// --- Modal visibility ---
	let showDeleteConfirmDialog = $state(false);
	let showAddUserModal = $state(false);
	let showUserChatsModal = $state(false);
	let showEditUserModal = $state(false);
	let showBulkDeleteConfirmDialog = $state(false);

	// --- Sorting ---
	let sortKey = $state('created_at');
	let sortOrder = $state('asc');

	/** Toggle selection of all filtered users */
	function toggleSelectAll() {
		if (isAllSelected) {
			selectedUserIds = [];
		} else {
			selectedUserIds = filteredUsers.map((u) => u.id);
		}
	}

	/** Toggle selection of a single user */
	function toggleSelectUser(id: string) {
		if (selectedUserIds.includes(id)) {
			selectedUserIds = selectedUserIds.filter((uid) => uid !== id);
		} else {
			selectedUserIds = [...selectedUserIds, id];
		}
	}

	/**
	 * Delete all selected users in sequence and refresh the list.
	 */
	const bulkDeleteHandler = async () => {
		let deleted = 0;
		for (const id of selectedUserIds) {
			const res = await deleteUserById('', id).catch(() => null);
			if (res) deleted++;
		}
		toast.success($i18n.t('{{count}} users deleted', { count: deleted }));
		selectedUserIds = [];
		users = await getUsers('');
	};

	/**
	 * Export the current user list as a CSV download.
	 */
	const exportCSV = () => {
		const headers = ['Name', 'Email', 'Role', 'Last Active', 'Created At', 'OAuth ID'];
		const rows = users.map((u) =>
			[
				`"${u.name}"`,
				u.email,
				u.role,
				dayjs(u.last_active_at * 1000).format('YYYY-MM-DD HH:mm'),
				dayjs(u.created_at * 1000).format('YYYY-MM-DD'),
				u.oauth_sub ?? ''
			].join(',')
		);
		const csv = [headers.join(','), ...rows].join('\n');
		const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `users-export-${Date.now()}.csv`;
		a.click();
		URL.revokeObjectURL(url);
	};

	/**
	 * Change a user's role and refresh the list.
	 * @param id - User ID
	 * @param role - New role value
	 */
	const updateRoleHandler = async (id, role) => {
		const res = await updateUserRole('', id, role).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			users = await getUsers('');
		}
	};

	/**
	 * Delete a single user by ID and refresh the list.
	 * @param id - User ID to delete
	 */
	const deleteUserHandler = async (id) => {
		const res = await deleteUserById('', id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			users = await getUsers('');
		}
	};

	/**
	 * Unlock a locked user account and refresh lockout statuses.
	 * @param id - User ID to unlock
	 */
	const unlockUserHandler = async (id) => {
		const res = await unlockUserAccount('', id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('Account unlocked successfully'));
			lockoutStatuses = (await getUserLockoutStatuses('')) as LockoutStatuses;
		}
	};

	/**
	 * Fetch lockout statuses for all users.
	 */
	const loadLockoutStatuses = async () => {
		lockoutStatuses = (await getUserLockoutStatuses('').catch(() => ({}))) as LockoutStatuses;
	};

	/**
	 * Set the sort key and toggle direction if the same key is clicked.
	 * @param key - Column key to sort by
	 */
	function setSortKey(key) {
		if (sortKey === key) {
			sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = key;
			sortOrder = 'asc';
		}
	}

	let filteredUsers = $derived(
		users
			.filter((user) => {
				if (search === '') {
					return true;
				} else {
					const name = user.name.toLowerCase();
					const email = user.email.toLowerCase();
					const query = search.toLowerCase();
					return name.includes(query) || email.includes(query);
				}
			})
			.sort((a, b) => {
				const av = (a as Record<string, string | number>)[sortKey];
				const bv = (b as Record<string, string | number>)[sortKey];
				if (av < bv) return sortOrder === 'asc' ? -1 : 1;
				if (av > bv) return sortOrder === 'asc' ? 1 : -1;
				return 0;
			})
			.slice((page - 1) * perPage, page * perPage)
	);

	/** Whether all filtered users are selected */
	let isAllSelected = $derived(
		filteredUsers.length > 0 && filteredUsers.every((u) => selectedUserIds.includes(u.id))
	);

	onMount(() => {
		loadLockoutStatuses();
	});
</script>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	onconfirm={() => {
		if (selectedUser) deleteUserHandler(selectedUser.id);
	}}
/>

<ConfirmDialog
	bind:show={showBulkDeleteConfirmDialog}
	onconfirm={() => {
		bulkDeleteHandler();
	}}
>
	<div class="text-sm text-gray-500">
		{$i18n.t('This will delete')}
		<span class="font-semibold">{selectedUserIds.length}</span>
		{$i18n.t('selected users. This action cannot be undone.')}
	</div>
</ConfirmDialog>

{#key selectedUser}
	{#if selectedUser && $user}
		<EditUserModal
			bind:show={showEditUserModal}
			{selectedUser}
			sessionUser={$user}
			onSave={async () => {
				users = await getUsers('');
			}}
		/>
	{/if}
{/key}

<AddUserModal
	bind:show={showAddUserModal}
	onSave={async () => {
		users = await getUsers('');
	}}
/>
{#if selectedUser}
	<UserChatsModal bind:show={showUserChatsModal} user={selectedUser} />
{/if}

<InfoCallout
	>{$i18n.t(
		'Manage every user account here: review members, change their role between admin, user, and pending, unlock locked accounts, and add or remove users.'
	)}</InfoCallout
>

<div class="mt-1 mb-3 gap-2 flex flex-row items-center justify-between">
	<div class="flex md:self-center text-lg font-medium px-0.5">
		<div class="flex-shrink-0">
			{$i18n.t('Users')}
		</div>
		<div class="flex self-center w-[1px] h-6 mx-2.5 bg-gray-50 dark:bg-gray-850"></div>

		{#if ($config?.license_metadata?.seats ?? null) !== null}
			{#if users.length > $config?.license_metadata?.seats}
				<span class="text-lg font-medium text-red-500"
					>{users.length} of {$config?.license_metadata?.seats}
					<span class="text-sm font-normal">available users</span></span
				>
			{:else}
				<span class="text-lg font-medium text-gray-500 dark:text-gray-300"
					>{users.length} of {$config?.license_metadata?.seats}
					<span class="text-sm font-normal">available users</span></span
				>
			{/if}
		{:else}
			<span class="text-lg font-medium text-gray-500 dark:text-gray-300">{users.length}</span>
		{/if}
	</div>

	<div class="flex gap-1">
		{#if selectedUserIds.length > 0}
			<div class="flex items-center gap-2">
				<span class="text-sm text-gray-500 dark:text-gray-400"
					>{selectedUserIds.length} selected</span
				>
				<Tooltip content={$i18n.t('Delete Selected')}>
					<button
						class="p-2 rounded-xl hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 transition text-sm flex items-center"
						onclick={() => {
							showBulkDeleteConfirmDialog = true;
						}}
						aria-label={$i18n.t('Delete Selected')}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke="currentColor"
							class="w-4 h-4"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
							/>
						</svg>
					</button>
				</Tooltip>
				<button
					class="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white px-2 py-1"
					onclick={() => (selectedUserIds = [])}>{$i18n.t('Clear')}</button
				>
			</div>
		{/if}
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
					class=" w-full text-sm pr-4 py-1.5 rounded-r-xl outline-hidden bg-transparent"
					bind:value={search}
					placeholder={$i18n.t('Search')}
				/>
			</div>

			<select
				class="text-xs rounded-lg border-none bg-gray-50 dark:bg-gray-850 text-gray-700 dark:text-gray-300 px-2 py-1 outline-none cursor-pointer"
				bind:value={perPage}
				onchange={() => {
					page = 1;
				}}
				aria-label="Users per page"
			>
				<option value={10}>10</option>
				<option value={20}>20</option>
				<option value={50}>50</option>
				<option value={100}>100</option>
			</select>

			<Tooltip content={$i18n.t('Export CSV')}>
				<button
					class="p-2 rounded-xl hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-850 transition text-sm flex items-center"
					onclick={exportCSV}
					aria-label={$i18n.t('Export CSV')}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="w-4 h-4"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
						/>
					</svg>
				</button>
			</Tooltip>

			<div>
				<Tooltip content={$i18n.t('Add User')}>
					<button
						class=" p-2 rounded-xl hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-850 transition font-medium text-sm flex items-center space-x-1"
						onclick={() => {
							showAddUserModal = !showAddUserModal;
						}}
					>
						<Plus className="size-3.5" />
					</button>
				</Tooltip>
			</div>
		</div>
	</div>
</div>

{#if filteredUsers.length === 0}
	{#if users.length === 0}
		<EmptyState
			icon="users"
			title={$i18n.t('No users yet')}
			description={$i18n.t('Add your first user to get started.')}
			actionLabel={$i18n.t('Add User')}
			actionHandler={() => {
				showAddUserModal = true;
			}}
		/>
	{:else}
		<EmptyState
			icon="users"
			title={$i18n.t('No matching users')}
			description={$i18n.t('Try adjusting your search terms.')}
		/>
	{/if}
{:else}
	<div class="md:hidden flex flex-col gap-3 pt-1">
		{#each filteredUsers as user (user.id)}
			<div
				class="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-100 dark:border-gray-850"
			>
				<div class="flex items-center justify-between mb-3">
					<div class="flex items-center gap-3">
						<input
							type="checkbox"
							checked={selectedUserIds.includes(user.id)}
							onchange={() => toggleSelectUser(user.id)}
							class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 cursor-pointer"
						/>
						<img
							class="rounded-full w-9 h-9 object-cover"
							src={user.profile_image_url.startsWith(APP_BASE_URL) ||
							user.profile_image_url.startsWith('https://www.gravatar.com/avatar/') ||
							user.profile_image_url.startsWith('data:')
								? user.profile_image_url
								: `/user.png`}
							alt="user"
						/>
						<div>
							<div class="text-sm font-medium text-gray-900 dark:text-white">{user.name}</div>
							<div class="text-xs text-gray-500">{user.email}</div>
						</div>
					</div>
					<Badge
						type={user.role === 'admin' ? 'info' : user.role === 'user' ? 'success' : 'muted'}
						content={$i18n.t(user.role)}
					/>
				</div>
				<div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
					<span>{dayjs(user.last_active_at * 1000).fromNow()}</span>
					<div class="flex gap-1">
						{#if lockoutStatuses[user.id]?.is_locked}
							<Badge type="error" content={$i18n.t('Locked')} />
						{/if}
						<Tooltip content={$i18n.t('Edit User')}>
							<button
								class="p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg"
								onclick={() => {
									showEditUserModal = true;
									selectedUser = user;
								}}
								aria-label={$i18n.t('Edit User')}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="1.5"
									stroke="currentColor"
									class="w-4 h-4"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
									/>
								</svg>
							</button>
						</Tooltip>
						{#if user.role !== 'admin'}
							<Tooltip content={$i18n.t('Delete User')}>
								<button
									class="p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 rounded-lg"
									onclick={() => {
										showDeleteConfirmDialog = true;
										selectedUser = user;
									}}
									aria-label={$i18n.t('Delete User')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="1.5"
										stroke="currentColor"
										class="w-4 h-4"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
										/>
									</svg>
								</button>
							</Tooltip>
						{/if}
					</div>
				</div>
			</div>
		{/each}
	</div>

	<div
		class="hidden md:block scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full rounded-sm pt-0.5"
	>
		<table
			aria-label="User list"
			class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto max-w-full rounded-sm"
		>
			<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-850 dark:text-gray-400">
				<tr class="">
					<th scope="col" class="px-4 py-2.5 w-10">
						<input
							type="checkbox"
							checked={isAllSelected}
							onchange={() => toggleSelectAll()}
							class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 cursor-pointer"
							aria-label="Select all users"
						/>
					</th>
					<th
						scope="col"
						aria-sort={sortKey === 'role'
							? sortOrder === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						class="px-4 py-2.5 cursor-pointer select-none"
						onclick={() => setSortKey('role')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('Role')}

							{#if sortKey === 'role'}
								<span class="font-normal"
									>{#if sortOrder === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>
					<th
						scope="col"
						aria-sort={sortKey === 'name'
							? sortOrder === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						class="px-4 py-2.5 cursor-pointer select-none"
						onclick={() => setSortKey('name')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('Name')}

							{#if sortKey === 'name'}
								<span class="font-normal"
									>{#if sortOrder === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>
					<th
						scope="col"
						aria-sort={sortKey === 'email'
							? sortOrder === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						class="px-4 py-2.5 cursor-pointer select-none"
						onclick={() => setSortKey('email')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('Email')}

							{#if sortKey === 'email'}
								<span class="font-normal"
									>{#if sortOrder === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>

					<th
						scope="col"
						aria-sort={sortKey === 'last_active_at'
							? sortOrder === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						class="px-4 py-2.5 cursor-pointer select-none"
						onclick={() => setSortKey('last_active_at')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('Last Active')}

							{#if sortKey === 'last_active_at'}
								<span class="font-normal"
									>{#if sortOrder === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>
					<th
						scope="col"
						aria-sort={sortKey === 'created_at'
							? sortOrder === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						class="px-4 py-2.5 cursor-pointer select-none"
						onclick={() => setSortKey('created_at')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('Created at')}
							{#if sortKey === 'created_at'}
								<span class="font-normal"
									>{#if sortOrder === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>

					<th
						scope="col"
						aria-sort={sortKey === 'oauth_sub'
							? sortOrder === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						class="px-4 py-2.5 cursor-pointer select-none"
						onclick={() => setSortKey('oauth_sub')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('OAuth ID')}

							{#if sortKey === 'oauth_sub'}
								<span class="font-normal"
									>{#if sortOrder === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>

					<th scope="col" class="px-4 py-2.5 text-right"></th>
				</tr>
			</thead>
			<tbody class="">
				{#each filteredUsers as user (user.id)}
					<tr class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs">
						<td class="px-4 py-3">
							<input
								type="checkbox"
								checked={selectedUserIds.includes(user.id)}
								onchange={() => toggleSelectUser(user.id)}
								class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 cursor-pointer"
								aria-label="Select {user.name}"
							/>
						</td>
						<td class="px-4 py-3 min-w-[7rem] w-28">
							<div class="flex flex-col gap-1">
								<button
									class=" translate-y-0.5"
									onclick={() => {
										if (user.role === 'user') {
											updateRoleHandler(user.id, 'admin');
										} else if (user.role === 'pending') {
											updateRoleHandler(user.id, 'user');
										} else {
											updateRoleHandler(user.id, 'pending');
										}
									}}
								>
									<Badge
										type={user.role === 'admin'
											? 'info'
											: user.role === 'user'
												? 'success'
												: 'muted'}
										content={$i18n.t(user.role)}
									/>
								</button>
								{#if lockoutStatuses[user.id]?.is_locked}
									<Badge type="error" content={$i18n.t('Locked')} />
								{/if}
							</div>
						</td>
						<td class="px-4 py-3 font-medium text-gray-900 dark:text-white w-max">
							<div class="flex flex-row w-max">
								<img
									class=" rounded-full w-7 h-7 object-cover mr-3"
									src={user.profile_image_url.startsWith(APP_BASE_URL) ||
									user.profile_image_url.startsWith('https://www.gravatar.com/avatar/') ||
									user.profile_image_url.startsWith('data:')
										? user.profile_image_url
										: `/user.png`}
									alt="user"
								/>

								<div class=" font-medium self-center">{user.name}</div>
							</div>
						</td>
						<td class=" px-4 py-3"> {user.email} </td>

						<td class=" px-4 py-3">
							{dayjs(user.last_active_at * 1000).fromNow()}
						</td>

						<td class=" px-4 py-3">
							{dayjs(user.created_at * 1000).format('LL')}
						</td>

						<td class=" px-4 py-3"> {user.oauth_sub ?? ''} </td>

						<td class="px-4 py-3 text-right">
							<div class="flex justify-end w-full">
								{#if $config.features.enable_admin_chat_access && user.role !== 'admin'}
									<Tooltip content={$i18n.t('Chats')}>
										<button
											class="self-center w-fit text-sm px-2 py-2 hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
											onclick={async () => {
												showUserChatsModal = !showUserChatsModal;
												selectedUser = user;
											}}
										>
											<ChatBubbles />
										</button>
									</Tooltip>
								{/if}

								{#if lockoutStatuses[user.id]?.is_locked}
									<Tooltip content={$i18n.t('Unlock Account')}>
										<button
											class="self-center w-fit text-sm px-2 py-2 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl text-red-500"
											onclick={async () => {
												await unlockUserHandler(user.id);
											}}
											aria-label={$i18n.t('Unlock Account')}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M13.5 10.5V6.75a4.5 4.5 0 1 1 9 0v3.75M3.75 21.75h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H3.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
												/>
											</svg>
										</button>
									</Tooltip>
								{/if}

								<Tooltip content={$i18n.t('Edit User')}>
									<button
										class="self-center w-fit text-sm px-2 py-2 hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
										onclick={async () => {
											showEditUserModal = !showEditUserModal;
											selectedUser = user;
										}}
										aria-label={$i18n.t('Edit User')}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="1.5"
											stroke="currentColor"
											class="w-4 h-4"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
											/>
										</svg>
									</button>
								</Tooltip>

								{#if user.role !== 'admin'}
									<Tooltip content={$i18n.t('Delete User')}>
										<button
											class="self-center w-fit text-sm px-2 py-2 hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
											onclick={async () => {
												showDeleteConfirmDialog = true;
												selectedUser = user;
											}}
											aria-label={$i18n.t('Delete User')}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="w-4 h-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
												/>
											</svg>
										</button>
									</Tooltip>
								{/if}
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

{#if filteredUsers.length > 0}
	<div class=" text-gray-500 text-xs mt-1.5 text-right">
		ⓘ {$i18n.t("Click on the user role button to change a user's role.")}
	</div>
{/if}

<Pagination bind:page count={users.length} {perPage} />
