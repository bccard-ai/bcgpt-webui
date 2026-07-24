<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';

	import {
		deleteSkillById,
		getSkills,
		importSkillFromUrl,
		setSkillFlags,
		skills,
		type Skill
	} from '$lib/apis/skills';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import ImportTrustDialog from '$lib/components/common/ImportTrustDialog.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let showImport = $state(false);

	const refresh = async () => skills.set(await getSkills(localStorage.token));

	const toggleActive = async (s: Skill) => {
		try {
			await setSkillFlags(localStorage.token, s.id, { is_active: !s.is_active });
			s.is_active = !s.is_active;
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const toggleGlobal = async (s: Skill) => {
		try {
			await setSkillFlags(localStorage.token, s.id, { is_global: !s.is_global });
			s.is_global = !s.is_global;
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const remove = async (s: Skill) => {
		try {
			await deleteSkillById(localStorage.token, s.id);
			toast.success($i18n.t('Skill deleted'));
			await refresh();
		} catch (e) {
			// Builtins return 403; surface the message.
			toast.error(`${e}`);
		}
	};

	const importUrl = async (url: string) => {
		try {
			await importSkillFromUrl(localStorage.token, url);
			toast.success($i18n.t('Skill imported'));
			await refresh();
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	let rows = $derived($skills ?? []);
</script>

<ImportTrustDialog bind:show={showImport} onconfirm={importUrl} />

<div class="mb-3 flex justify-between">
	<div class="flex gap-2">
		<button
			class="rounded-lg bg-gray-50 px-3 py-1.5 text-sm dark:bg-gray-850"
			onclick={() => goto(resolve('/admin/skill/edit'))}
		>
			+ {$i18n.t('Create Skill')}
		</button>
		<button
			class="rounded-lg bg-gray-50 px-3 py-1.5 text-sm dark:bg-gray-850"
			onclick={() => (showImport = true)}
		>
			{$i18n.t('Import from URL')}
		</button>
	</div>
</div>

{#if rows.length === 0}
	<EmptyState
		title={$i18n.t('No skills found')}
		description={$i18n.t('Create a skill or import one to get started.')}
	/>
{:else}
	<div class="flex flex-col gap-1">
		{#each rows as s (s.id)}
			<div class="flex items-center rounded-xl px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5">
				<div class="flex-1">
					<div class="flex items-center gap-1.5 font-semibold">
						{#if s.is_builtin}
							<span class="rounded-sm bg-blue-500/20 px-1 text-xs text-blue-700 dark:text-blue-300"
								>BUILTIN</span
							>
						{/if}
						{#if s.is_global}
							<span class="rounded-sm bg-gray-500/20 px-1 text-xs">GLOBAL</span>
						{/if}
						<span class="line-clamp-1">{s.name}</span>
					</div>
					<div class="line-clamp-1 text-xs text-gray-500">{s.description}</div>
				</div>

				<Tooltip content={$i18n.t('Edit')}>
					<button
						class="p-1.5 text-sm hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
						onclick={() => goto(resolve(`/admin/skill/edit?id=${encodeURIComponent(s.id)}`))}
					>
						<Pencil />
					</button>
				</Tooltip>

				<Tooltip content={s.is_global ? $i18n.t('Global') : $i18n.t('Local')}>
					<button class="px-2 text-xs" onclick={() => toggleGlobal(s)}>
						{s.is_global ? '🌐' : '🔒'}
					</button>
				</Tooltip>

				{#if !s.is_builtin}
					<Tooltip content={$i18n.t('Delete')}>
						<button
							class="p-1.5 text-sm text-red-500 hover:bg-black/5 dark:hover:bg-white/5 rounded-xl"
							onclick={() => remove(s)}
						>
							<GarbageBin />
						</button>
					</Tooltip>
				{/if}

				<div class="mx-1">
					<Tooltip content={s.is_active ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
						<Switch bind:state={s.is_active} onchange={() => toggleActive(s)} />
					</Tooltip>
				</div>
			</div>
		{/each}
	</div>
{/if}
