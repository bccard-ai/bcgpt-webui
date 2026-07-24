<script lang="ts">
	import { useDashboard, getToken } from './context';
	import { useI18n } from './i18n';
	import DashboardWidget from './DashboardWidget.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import { getVectorDBStatus, type VectorDBStatus } from '$lib/apis/retrieval';
	import { formatCompact } from './charts/format';

	const d = useDashboard();
	const i18n = useI18n();
	let loading = $state(true);
	let error = $state<string | null>(null);
	let st = $state<VectorDBStatus | null>(null);
	let loaded = $state(false);

	async function load() {
		loading = true;
		error = null;
		try {
			st = await getVectorDBStatus(getToken());
		} catch {
			error = $i18n.t('Failed to load vector DB status');
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

<DashboardWidget
	title={$i18n.t('Vector Database')}
	loading={loading && !loaded}
	refreshing={loading && loaded}
	{error}
	onRetry={() => d.refresh()}
	empty={!loading && !st}
	emptyLabel={$i18n.t('Not configured')}
	href="/admin/rag"
	hrefLabel={$i18n.t('Manage')}
	bodyClass="pt-2"
>
	{#snippet icon()}<Cube className="size-4" />{/snippet}

	{#if st}
		<div class="flex flex-col gap-2.5 text-xs">
			<div class="flex items-center justify-between">
				<span class="text-muted-foreground">{$i18n.t('Status')}</span>
				<span
					class="flex items-center gap-1.5 font-medium {st.connected
						? 'text-success'
						: 'text-destructive'}"
				>
					<span class="size-2 rounded-full {st.connected ? 'bg-success' : 'bg-destructive'}"></span>
					{st.connected ? $i18n.t('Connected') : $i18n.t('Disconnected')}
				</span>
			</div>
			<div class="flex items-center justify-between">
				<span class="text-muted-foreground">{$i18n.t('Backend')}</span>
				<span class="font-medium text-foreground">{st.backend ?? '—'}</span>
			</div>
			<div class="flex items-center justify-between">
				<span class="text-muted-foreground">{$i18n.t('Collections')}</span>
				<span class="font-medium tabular-nums text-foreground">{st.collections?.length ?? 0}</span>
			</div>
			<div class="flex items-center justify-between">
				<span class="text-muted-foreground">{$i18n.t('Vectors')}</span>
				<span class="font-medium tabular-nums text-foreground"
					>{formatCompact(st.total_vectors ?? 0)}</span
				>
			</div>
			{#if st.embedding_model}
				<div class="flex items-center justify-between gap-2">
					<span class="shrink-0 text-muted-foreground">{$i18n.t('Embedding')}</span>
					<span class="truncate font-medium text-foreground" title={st.embedding_model}
						>{st.embedding_model}</span
					>
				</div>
			{/if}
		</div>
	{/if}
</DashboardWidget>
