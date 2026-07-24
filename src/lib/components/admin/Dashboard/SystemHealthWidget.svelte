<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import DashboardWidget from './DashboardWidget.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import { appClient } from '$lib/apis/client';
	import { getBackendConfig, getVersionUpdates } from '$lib/apis';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let checks = $state<Record<string, string>>({});
	let version = $state('');
	let latest = $state<string | null>(null);
	let loaded = $state(false);

	const up = (v: string | undefined) =>
		typeof v === 'string' && v.length > 0 && !v.startsWith('error');

	async function load() {
		loading = true;
		error = null;
		try {
			const [rz, cfg, upd] = await Promise.all([
				appClient.get<Record<string, string>>('/readyz').catch(() => null),
				getBackendConfig().catch(() => null),
				getVersionUpdates(getToken()).catch(() => null)
			]);
			if (rz) {
				checks = { db: rz.db ?? '', qdrant: rz.qdrant ?? '', redis: rz.redis ?? '' };
			} else {
				checks = {};
				error = $i18n.t('Some services are degraded');
			}
			version = cfg?.version ?? '';
			latest = upd?.latest ?? null;
		} catch {
			error = $i18n.t('Failed to load system health');
		} finally {
			loading = false;
			loaded = true;
		}
	}
	$effect(() => {
		void d.refreshNonce;
		load();
	});

	const rows = [
		{ label: $i18n.t('Database'), key: 'db' },
		{ label: $i18n.t('Vector DB'), key: 'qdrant' },
		{ label: $i18n.t('Redis'), key: 'redis' }
	];
</script>

<DashboardWidget
	title={$i18n.t('System Health')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	onRetry={() => d.refresh()}
	empty={false}
	bodyClass="pt-2"
>
	{#snippet icon()}<Bolt className="size-4" />{/snippet}

	<div class="flex flex-col gap-2.5">
		{#each rows as r (r.key)}
			<div class="flex items-center justify-between">
				<span class="text-xs text-muted-foreground">{r.label}</span>
				<span
					class="flex items-center gap-1.5 text-xs font-medium {up(checks[r.key])
						? 'text-success'
						: 'text-destructive'}"
				>
					<span class="size-2 rounded-full {up(checks[r.key]) ? 'bg-success' : 'bg-destructive'}"
					></span>
					{up(checks[r.key]) ? $i18n.t('Operational') : $i18n.t('Down')}
				</span>
			</div>
		{/each}

		{#if version}
			<div class="mt-1 border-t border-border pt-2.5 text-xs text-muted-foreground">
				{$i18n.t('Version')}
				<span class="ml-1 font-medium text-foreground">{version}</span>
				{#if latest && latest !== version}
					<span
						class="ml-1.5 rounded bg-warning/20 px-1.5 py-0.5 text-[10px] text-warning-foreground"
						>v{latest} {$i18n.t('available')}</span
					>
				{/if}
			</div>
		{/if}
	</div>
</DashboardWidget>
