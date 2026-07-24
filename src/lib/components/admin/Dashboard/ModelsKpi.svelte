<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import KpiCard from './KpiCard.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import { getModels } from '$lib/apis';

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
			const models = (await getModels(getToken())) as Array<{
				owned_by?: string;
				info?: { meta?: { hidden?: boolean } };
			}>;
			value = String(
				models.filter((m) => m?.owned_by !== 'arena' && !(m?.info?.meta?.hidden ?? false)).length
			);
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
	label={$i18n.t('Models')}
	{value}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	href="/admin/settings?tab=models"
	accent="var(--chart-4)"
>
	{#snippet icon()}<Cube className="size-4" />{/snippet}
</KpiCard>
