<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import DashboardWidget from './DashboardWidget.svelte';
	import StackedBarChart from './charts/StackedBarChart.svelte';
	import Shield from '$lib/components/icons/Shield.svelte';
	import { getSecurityTimeline, getSecurityEventStats } from '$lib/apis/security';
	import { formatFull } from './charts/format';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let buckets = $state<{ x: number; segs: Record<string, number> }[]>([]);
	let loaded = $state(false);
	let total = $state(0);
	let blocked = $state(0);

	async function load(startMs: number, endMs: number) {
		loading = true;
		error = null;
		try {
			const gran: 'hour' | 'day' = d.range.key === 'today' ? 'hour' : 'day';
			const [tl, st] = await Promise.all([
				getSecurityTimeline(getToken(), startMs, endMs, gran).catch(() => ({ data: [] })),
				getSecurityEventStats(getToken(), startMs, endMs).catch(() => null)
			]);
			buckets = (tl?.data ?? []).map((b) => ({ x: b.timestamp, segs: b.by_severity ?? {} }));
			total =
				st?.total ??
				buckets.reduce((a, b) => a + Object.values(b.segs).reduce((x, y) => x + y, 0), 0);
			blocked = st?.blocked_count ?? 0;
		} catch {
			error = $i18n.t('Failed to load security timeline');
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

<DashboardWidget
	title={$i18n.t('Security Events')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	onRetry={() => d.refresh()}
	empty={!loading && buckets.length === 0}
	emptyLabel={$i18n.t('No security events in this range')}
	class="lg:col-span-2"
	href="/admin/audit"
	hrefLabel={$i18n.t('Audit')}
	bodyClass="pt-2"
>
	{#snippet icon()}<Shield className="size-4" />{/snippet}

	<div class="mb-3 flex items-center gap-4 text-xs">
		<span class="text-muted-foreground"
			>{$i18n.t('Total')}
			<span class="ml-1 font-semibold tabular-nums text-foreground">{formatFull(total)}</span></span
		>
		<span class="text-muted-foreground"
			>{$i18n.t('Blocked')}
			<span class="ml-1 font-semibold tabular-nums text-destructive">{formatFull(blocked)}</span
			></span
		>
	</div>

	<StackedBarChart data={buckets} height={180} />
</DashboardWidget>
