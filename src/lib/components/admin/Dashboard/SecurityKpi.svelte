<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import KpiCard from './KpiCard.svelte';
	import Shield from '$lib/components/icons/Shield.svelte';
	import { getSecurityEventStats } from '$lib/apis/security';
	import { formatCompact } from './charts/format';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state(false);
	let value = $state('0');
	let loaded = $state(false);

	async function load(startMs: number, endMs: number) {
		loading = true;
		error = false;
		try {
			const st = await getSecurityEventStats(getToken(), startMs, endMs);
			value = formatCompact(st?.total ?? 0);
		} catch {
			error = true;
		} finally {
			loading = false;
			loaded = true;
		}
	}
	$effect(() => {
		const { startMs, endMs } = d.range;
		void d.refreshNonce;
		load(startMs, endMs);
	});
</script>

<KpiCard
	label={$i18n.t('Security Events')}
	{value}
	sub={$i18n.t('selected range')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	href="/admin/audit"
	accent="var(--destructive)"
>
	{#snippet icon()}<Shield className="size-4" />{/snippet}
</KpiCard>
