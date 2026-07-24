<script lang="ts">
	import { getContext, onMount } from 'svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { getGroups } from '$lib/apis/groups';
	import Badge from '$lib/components/common/Badge.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface AccessControlEntry {
		group_ids: string[];
		user_ids: string[];
	}

	interface AccessControlValue {
		read: AccessControlEntry;
		write: AccessControlEntry;
	}

	interface Group {
		id: string;
		name: string;
	}

	interface Props {
		/** Callback fired when access control value changes */
		onchange?: (value: AccessControlValue | null) => void;
		/** Which access roles to enable (e.g. ['read', 'write']) */
		accessRoles?: string[];
		/** Access control configuration (two-way bindable) */
		accessControl?: AccessControlValue | null;
		/** Whether public visibility is allowed */
		allowPublic?: boolean;
	}

	let {
		onchange = () => {},
		accessRoles = ['read'],
		accessControl = $bindable(null),
		allowPublic = true
	}: Props = $props();

	let selectedGroupId = $state('');
	let groups = $state<Group[]>([]);

	onMount(async () => {
		groups = (await getGroups('')) as Group[];

		if (accessControl === null) {
			if (allowPublic) {
				accessControl = null;
			} else {
				accessControl = {
					read: {
						group_ids: [],
						user_ids: []
					},
					write: {
						group_ids: [],
						user_ids: []
					}
				};
				onchange(accessControl);
			}
		} else {
			accessControl = {
				read: {
					group_ids: accessControl?.read?.group_ids ?? [],
					user_ids: accessControl?.read?.user_ids ?? []
				},
				write: {
					group_ids: accessControl?.write?.group_ids ?? [],
					user_ids: accessControl?.write?.user_ids ?? []
				}
			};
		}
	});

	const onSelectGroup = () => {
		if (selectedGroupId !== '' && accessControl !== null) {
			accessControl.read.group_ids = [...accessControl.read.group_ids, selectedGroupId];

			selectedGroupId = '';
		}
	};

	$effect(() => {
		if (!allowPublic && accessControl === null) {
			accessControl = {
				read: {
					group_ids: [],
					user_ids: []
				},
				write: {
					group_ids: [],
					user_ids: []
				}
			};
			onchange(accessControl);
		}
	});

	$effect(() => {
		onchange(accessControl);
	});

	$effect(() => {
		if (selectedGroupId) {
			onSelectGroup();
		}
	});
</script>

<div class="flex flex-col gap-1.5">
	<div class="flex items-center gap-2">
		{#if accessControl !== null}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="1.5"
				stroke="currentColor"
				class="w-4 h-4 shrink-0 text-gray-400"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
				/>
			</svg>
		{:else}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="1.5"
				stroke="currentColor"
				class="w-4 h-4 shrink-0 text-gray-400"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M6.115 5.19l.319 1.913A6 6 0 008.11 10.36L9.75 12l-.387.775c-.217.433-.132.956.21 1.298l1.348 1.348c.21.21.329.497.329.795v1.089c0 .426.24.815.622 1.006l.153.076c.433.217.956.132 1.298-.21l.723-.723a8.7 8.7 0 002.288-4.042 1.087 1.087 0 00-.358-1.099l-1.33-1.108c-.251-.21-.582-.299-.905-.245l-1.17.195a1.125 1.125 0 01-.98-.314l-.295-.295a1.125 1.125 0 010-1.591l.13-.132a1.125 1.125 0 011.3-.21l.603.302a.809.809 0 001.086-1.086L14.25 7.5l1.256-.837a4.5 4.5 0 001.528-1.732l.146-.292M6.115 5.19A9 9 0 1017.18 4.64M6.115 5.19A8.965 8.965 0 0112 3c1.929 0 3.716.607 5.18 1.64"
				/>
			</svg>
		{/if}

		<span class="text-xs font-medium text-gray-500">{$i18n.t('Visibility')}</span>

		<select
			class="outline-hidden bg-transparent text-xs font-medium rounded-lg pr-6 max-w-full"
			value={accessControl !== null ? 'private' : 'public'}
			onchange={(e: CustomEvent) => {
				if (e.target?.value === 'public') {
					accessControl = null;
				} else {
					accessControl = {
						read: {
							group_ids: [],
							user_ids: []
						},
						write: {
							group_ids: [],
							user_ids: []
						}
					};
				}
			}}
		>
			<option class="text-gray-700" value="private" selected>{$i18n.t('Private')}</option>
			{#if allowPublic}
				<option class="text-gray-700" value="public" selected>{$i18n.t('Public')}</option>
			{/if}
		</select>
	</div>

	{#if accessControl !== null}
		{@const accessGroups = groups.filter((group) =>
			accessControl?.read.group_ids.includes(group.id)
		)}
		<div class="flex flex-wrap items-center gap-1.5 pl-6">
			<select
				class="outline-hidden bg-transparent text-xs rounded-lg pr-6 max-w-full
				{selectedGroupId ? '' : 'text-gray-500'}"
				bind:value={selectedGroupId}
			>
				<option class="text-gray-700" value="" disabled selected>{$i18n.t('Select a group')}</option
				>
				{#each groups.filter((group) => !accessControl?.read.group_ids.includes(group.id)) as group (group.id)}
					<option class="text-gray-700" value={group.id}>{group.name}</option>
				{/each}
			</select>

			{#each accessGroups as group (group.id)}
				<span
					class="inline-flex items-center gap-1 rounded-full bg-gray-100 dark:bg-white/10 text-xs font-medium px-2 py-0.5"
				>
					<button
						class="hover:opacity-70 transition"
						type="button"
						onclick={() => {
							if (accessControl !== null && accessRoles.includes('write')) {
								if (accessControl.write.group_ids.includes(group.id)) {
									accessControl.write.group_ids = accessControl.write.group_ids.filter(
										(group_id) => group_id !== group.id
									);
								} else {
									accessControl.write.group_ids = [...accessControl.write.group_ids, group.id];
								}
							}
						}}
					>
						{#if accessControl.write.group_ids.includes(group.id)}
							<Badge type="success" content={$i18n.t('Write')} />
						{:else}
							<Badge type="info" content={$i18n.t('Read')} />
						{/if}
					</button>

					<span class="text-gray-700 dark:text-gray-300">{group.name}</span>

					<button
						class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
						type="button"
						aria-label={$i18n.t('Remove')}
						onclick={() => {
							if (accessControl !== null) {
								accessControl.read.group_ids = accessControl.read.group_ids.filter(
									(id) => id !== group.id
								);
							}
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="2"
							stroke="currentColor"
							class="w-3 h-3"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</span>
			{/each}
		</div>
	{/if}
</div>
