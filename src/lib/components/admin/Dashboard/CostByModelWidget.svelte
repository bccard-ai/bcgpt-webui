<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import DashboardWidget from './DashboardWidget.svelte';
	import HBarChart from './charts/HBarChart.svelte';
	import DocumentChartBar from '$lib/components/icons/DocumentChartBar.svelte';
	import { getUsageByModel, type UsageByGroupRow } from '$lib/apis/usage';
	import { formatCost } from './charts/format';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let rows = $state<UsageByGroupRow[]>([]);
	let loaded = $state(false);

	async function load(startMs: number, endMs: number) {
		loading = true;
		error = null;
		try {
			const res = await getUsageByModel(getToken(), startMs, endMs);
			rows = [...(res?.data ?? [])].sort((a, b) => b.cost - a.cost).slice(0, 8);
		} catch {
			error = $i18n.t('Failed to load cost data');
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

	const items = $derived(
		rows.map((r) => ({ label: r.model ?? 'unknown', value: r.cost })).filter((i) => i.value > 0)
	);
</script>

<DashboardWidget
	title={$i18n.t('Cost by Model')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	onRetry={() => d.refresh()}
	empty={!loading && items.length === 0}
	emptyLabel={$i18n.t('No cost data')}
	bodyClass="pt-2"
>
	{#snippet icon()}<DocumentChartBar className="size-4" />{/snippet}
	<HBarChart data={items} color="var(--chart-3)" valueFormatter={formatCost} />
</DashboardWidget>
