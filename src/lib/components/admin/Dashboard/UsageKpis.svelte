<!--
  Renders 3 KPI cards (Requests, Tokens, Cost) from a single /usage/total call.
  Must render a fragment (no wrapper) so the cards become grid items.
-->
<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import KpiCard from './KpiCard.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import DocumentChartBar from '$lib/components/icons/DocumentChartBar.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import { getUsageTotal, type UsageTotal } from '$lib/apis/usage';
	import { formatCompact, formatCost } from './charts/format';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state(false);
	let t = $state<UsageTotal | null>(null);
	let loaded = $state(false);

	async function load(startMs: number, endMs: number) {
		loading = true;
		error = false;
		try {
			t = await getUsageTotal(getToken(), startMs, endMs);
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
	label={$i18n.t('Requests')}
	value={t ? formatCompact(t.count) : '0'}
	sub={$i18n.t('LLM calls')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	href="/admin/settings?tab=models"
	accent="var(--chart-1)"
>
	{#snippet icon()}<ChartBar className="size-4" />{/snippet}
</KpiCard>

<KpiCard
	label={$i18n.t('Tokens')}
	value={t ? formatCompact(t.total_tokens) : '0'}
	sub={t ? `${formatCompact(t.prompt_tokens)} in · ${formatCompact(t.completion_tokens)} out` : ''}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	accent="var(--chart-2)"
>
	{#snippet icon()}<DocumentChartBar className="size-4" />{/snippet}
</KpiCard>

<KpiCard
	label={$i18n.t('Cost')}
	value={t ? formatCost(t.cost) : '$0'}
	sub={$i18n.t('selected range')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	accent="var(--chart-3)"
>
	{#snippet icon()}<Bolt className="size-4" />{/snippet}
</KpiCard>
