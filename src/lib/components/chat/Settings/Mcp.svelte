<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { settings } from '$lib/stores';
	import { getEffectiveMcpServers, type McpServer } from '$lib/apis/mcp';
	import ImportTrustDialog from '$lib/components/common/ImportTrustDialog.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let {
		saveSettings = (_u: Record<string, unknown>) => {}
	}: { saveSettings?: (u: Record<string, unknown>) => void } = $props();

	let catalog = $state<McpServer[]>([]);
	let showImport = $state(false);

	onMount(async () => {
		try {
			catalog = await getEffectiveMcpServers(localStorage.token);
		} catch (_e) {
			catalog = [];
		}
	});

	const myServers = $derived(
		((($settings?.ui as Record<string, unknown> | undefined)?.mcpServers as McpServer[]) ??
			[]) as McpServer[]
	);

	const remove = (id: string) => {
		const next = myServers.filter((s) => s.id !== id);
		const ui = (($settings?.ui as Record<string, unknown>) ?? {}) as Record<string, unknown>;
		saveSettings({ ui: { ...ui, mcpServers: next } });
	};

	const importUrl = (url: string) => {
		// Register a user-owned server by URL (backend re-validates allow-host).
		const id = 'user-' + Math.random().toString(36).slice(2, 8);
		const next: McpServer[] = [
			...myServers,
			{ id, name: url, url, enabled: true, allow_user_override: true }
		];
		const ui = (($settings?.ui as Record<string, unknown>) ?? {}) as Record<string, unknown>;
		saveSettings({ ui: { ...ui, mcpServers: next } });
	};
</script>

<div class="flex flex-col gap-3">
	<div class="flex justify-between">
		<div class="text-sm font-medium">{$i18n.t('Your MCP servers')}</div>
		<button
			class="rounded bg-gray-50 px-2 py-1 text-xs dark:bg-gray-850"
			onclick={() => (showImport = true)}
		>
			{$i18n.t('Add server URL')}
		</button>
	</div>
	<div class="flex flex-col gap-1.5 text-sm">
		{#each myServers as s (s.id)}
			<div class="flex items-center justify-between rounded bg-gray-50 px-2 py-1 dark:bg-gray-850">
				<span class="flex-1 truncate">{s.name}</span>
				<button class="text-red-500" onclick={() => remove(s.id)}>×</button>
			</div>
		{:else}
			<div class="text-gray-500">
				{$i18n.t('No personal MCP servers. Admin catalog')}: {catalog.length}
			</div>
		{/each}
	</div>
</div>

<ImportTrustDialog bind:show={showImport} onconfirm={importUrl} />
