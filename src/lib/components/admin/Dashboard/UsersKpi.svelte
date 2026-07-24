<script lang="ts">
	import { useDashboard } from './context';
	import { useI18n } from './i18n';
	import KpiCard from './KpiCard.svelte';
	import UsersSolid from '$lib/components/icons/UsersSolid.svelte';
	import { getBackendConfig } from '$lib/apis';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state(false);
	let value = $state('0');
	let loaded = $state(false);

	async function load() {
		loading = true;
		error = false;
		try {
			const cfg = await getBackendConfig();
			value = String(cfg?.user_count ?? 0);
		} catch {
			error = true;
		} finally {
			loading = false;
			loaded = true;
		}
	}
	$effect(() => {
		void d.refreshNonce;
		load();
	});
</script>

<KpiCard
	label={$i18n.t('Users')}
	{value}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	href="/admin/users"
	accent="var(--chart-1)"
>
	{#snippet icon()}<UsersSolid className="size-4" />{/snippet}
</KpiCard>
