<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import DashboardWidget from './DashboardWidget.svelte';
	import AreaChart from './charts/AreaChart.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import { getUsageByDay, type UsageByDayRow } from '$lib/apis/usage';
	import { formatTokens, formatCost, formatDate } from './charts/format';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let rows = $state<UsageByDayRow[]>([]);
	let loaded = $state(false);
	let metric = $state<'tokens' | 'cost'>('tokens');

	async function load(startMs: number, endMs: number) {
		loading = true;
		error = null;
		try {
			const res = await getUsageByDay(getToken(), startMs, endMs);
			rows = [...(res?.data ?? [])].sort((a, b) => a.day - b.day);
		} catch {
			error = $i18n.t('Failed to load usage trend');
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

	const points = $derived(
		rows.map((r) => ({
			x: r.day * 86_400_000,
			y: metric === 'tokens' ? r.total_tokens : r.cost
		}))
	);

	const metricOptions = [
		{ key: 'tokens' as const, label: $i18n.t('Tokens') },
		{ key: 'cost' as const, label: $i18n.t('Cost') }
	];
</script>

<DashboardWidget
	title={$i18n.t('Usage Trend')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	onRetry={() => d.refresh()}
	empty={!loading && points.length === 0}
	emptyLabel={$i18n.t('No usage recorded in this range')}
	class="lg:col-span-2"
	bodyClass="pt-2"
>
	{#snippet icon()}<ChartBar className="size-4" />{/snippet}

	<div class="mb-2 flex items-center justify-end gap-1">
		{#each metricOptions as opt (opt.key)}
			<button
				class="rounded-md px-2 py-0.5 text-xs transition {metric === opt.key
					? 'bg-primary text-primary-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				onclick={() => (metric = opt.key)}
			>
				{opt.label}
			</button>
		{/each}
	</div>

	<AreaChart
		data={points}
		color={metric === 'tokens' ? 'var(--chart-1)' : 'var(--chart-3)'}
		yFormatter={metric === 'tokens' ? formatTokens : formatCost}
		xFormatter={(ms: number) => formatDate(ms)}
		height={220}
	/>
</DashboardWidget>
