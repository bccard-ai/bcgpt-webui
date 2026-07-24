<!-- BCGPT WebUI - Admin Dashboard: live ops overview with KPIs, usage/security
     trends, system health, and quick navigation. Each widget fetches its own
     endpoint independently (loading/empty/error per card). -->
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { APP_NAME_STORE, user } from '$lib/stores';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import {
		provideDashboard,
		rangeForKey,
		type DashboardCtx
	} from '$lib/components/admin/Dashboard/context';
	import CommandBar from '$lib/components/admin/Dashboard/CommandBar.svelte';
	import UsersKpi from '$lib/components/admin/Dashboard/UsersKpi.svelte';
	import ModelsKpi from '$lib/components/admin/Dashboard/ModelsKpi.svelte';
	import UsageKpis from '$lib/components/admin/Dashboard/UsageKpis.svelte';
	import SecurityKpi from '$lib/components/admin/Dashboard/SecurityKpi.svelte';
	import UsageTrendWidget from '$lib/components/admin/Dashboard/UsageTrendWidget.svelte';
	import CostByModelWidget from '$lib/components/admin/Dashboard/CostByModelWidget.svelte';
	import SecurityTimelineWidget from '$lib/components/admin/Dashboard/SecurityTimelineWidget.svelte';
	import SystemHealthWidget from '$lib/components/admin/Dashboard/SystemHealthWidget.svelte';
	import VectorDbWidget from '$lib/components/admin/Dashboard/VectorDbWidget.svelte';
	import QuickNavigation from '$lib/components/admin/Dashboard/QuickNavigation.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let ready = $state(false);

	// Shared dashboard context: time range + refresh nonce + auto-refresh flag.
	const dash = $state<DashboardCtx>({
		range: rangeForKey('today'),
		refreshNonce: 0,
		auto: true,
		setRangeKey: () => {},
		refresh: () => {},
		toggleAuto: () => {}
	});
	dash.setRangeKey = (k) => {
		dash.range = rangeForKey(k);
	};
	dash.refresh = () => {
		dash.refreshNonce++;
	};
	dash.toggleAuto = () => {
		dash.auto = !dash.auto;
	};
	provideDashboard(dash);

	// Auto-refresh every 30s while enabled.
	$effect(() => {
		if (!dash.auto) return;
		const id = setInterval(() => {
			dash.refreshNonce++;
		}, 30_000);
		return () => clearInterval(id);
	});

	onMount(async () => {
		if (get(user)?.role !== 'admin') {
			await goto(resolve('/'));
			return;
		}
		ready = true;
	});
</script>

<svelte:head>
	<title>{$i18n.t('Admin Dashboard')} | {$APP_NAME_STORE}</title>
</svelte:head>

{#if ready}
	<div class="flex flex-col gap-6 py-4">
		<div>
			<h1 class="text-2xl font-semibold text-foreground">{$i18n.t('Admin Dashboard')}</h1>
			<p class="mt-1 text-sm text-muted-foreground">
				{$i18n.t('Overview of your platform at a glance.')}
			</p>
		</div>

		<CommandBar />

		<!-- KPI row: Users, Models, then 3 usage cards (Requests/Tokens/Cost), Security Events -->
		<div class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
			<UsersKpi />
			<ModelsKpi />
			<UsageKpis />
			<SecurityKpi />
		</div>

		<!-- Widget grid: each cell is an independently-loading card -->
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
			<UsageTrendWidget />
			<CostByModelWidget />
			<SecurityTimelineWidget />
			<SystemHealthWidget />
			<VectorDbWidget />
			<QuickNavigation />
		</div>
	</div>
{/if}
