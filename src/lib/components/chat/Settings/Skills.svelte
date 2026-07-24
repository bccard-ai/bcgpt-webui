<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { settings, user } from '$lib/stores';
	import { getSkills, importSkillFromUrl, type Skill } from '$lib/apis/skills';
	import ImportTrustDialog from '$lib/components/common/ImportTrustDialog.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let {
		saveSettings = (_u: Record<string, unknown>) => {}
	}: { saveSettings?: (u: Record<string, unknown>) => void } = $props();

	let catalog = $state<Skill[]>([]);
	let showImport = $state(false);

	onMount(async () => {
		try {
			catalog = await getSkills(localStorage.token);
		} catch (_e) {
			catalog = [];
		}
	});

	const enabledIds = $derived(
		((
			($settings?.ui as Record<string, unknown> | undefined)?.skills as
				| Record<string, unknown>
				| undefined
		)?.enabled as string[] | undefined) ?? []
	);

	const isVisible = (s: Skill) => s.is_global || s.user_id === $user?.id;
	const isEnabled = (id: string) => enabledIds.includes(id);

	const toggle = (s: Skill) => {
		const next = isEnabled(s.id) ? enabledIds.filter((id) => id !== s.id) : [...enabledIds, s.id];
		const ui = (($settings?.ui as Record<string, unknown>) ?? {}) as Record<string, unknown>;
		saveSettings({ ui: { ...ui, skills: { enabled: next } } });
	};

	const importUrl = async (url: string) => {
		try {
			await importSkillFromUrl(localStorage.token, url);
			catalog = await getSkills(localStorage.token);
		} catch (e) {
			console.error(e);
		}
	};
</script>

<div class="flex flex-col gap-3">
	<div class="flex justify-between">
		<div class="text-sm font-medium">{$i18n.t('Active skills')}</div>
		<button
			class="rounded bg-gray-50 px-2 py-1 text-xs dark:bg-gray-850"
			onclick={() => (showImport = true)}
		>
			{$i18n.t('Import from URL')}
		</button>
	</div>

	<div class="flex flex-col gap-1.5 text-sm">
		{#each catalog.filter(isVisible) as s (s.id)}
			<label class="flex items-center gap-2">
				<input type="checkbox" checked={isEnabled(s.id)} onchange={() => toggle(s)} />
				<span>
					<span class="font-medium">{s.name}</span>
					<span class="text-gray-500">— {s.description}</span>
				</span>
			</label>
		{:else}
			<div class="text-gray-500">{$i18n.t('No skills found')}</div>
		{/each}
	</div>
</div>

<ImportTrustDialog bind:show={showImport} onconfirm={importUrl} />
