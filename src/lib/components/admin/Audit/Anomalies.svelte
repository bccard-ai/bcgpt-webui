<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { getAnomalies } from '$lib/apis/audit';
	import type { Anomaly } from '$lib/apis/audit';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import { formatTimestamp, severityDot, severityBadge, severityAccent, humanize } from './utils';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let anomalies = $state<Anomaly[]>([]);
	let loading = $state(true);
	let loadError = $state(false);
	let selectedHours = $state(24);

	// Discards out-of-order responses when the time window is changed rapidly.
	let requestSeq = 0;

	const HOUR_OPTIONS = [
		{ value: 6, label: '6h' },
		{ value: 24, label: '24h' },
		{ value: 48, label: '48h' },
		{ value: 168, label: '7d' }
	];

	function anomalyTitle(type: string): string {
		const titles: Record<string, string> = {
			multiple_failed_logins: 'Multiple Failed Logins',
			excessive_exports: 'Excessive Data Exports',
			off_hours_admin_access: 'Off-Hours Access',
			bulk_data_access: 'Bulk Data Access'
		};
		return $i18n.t(titles[type] ?? humanize(type));
	}

	async function loadData() {
		const token = '';
		const seq = ++requestSeq;
		loading = true;
		loadError = false;
		try {
			const result = await getAnomalies(token, selectedHours);
			if (seq !== requestSeq) return;
			anomalies = result.anomalies;
		} catch (e) {
			if (seq !== requestSeq) return;
			// Never let a failed load look like a clean "no anomalies" result.
			loadError = true;
			toast.error(`${e}`);
		} finally {
			if (seq === requestSeq) loading = false;
		}
	}

	$effect(() => {
		void selectedHours;
		loadData();
	});
</script>

<div class="flex flex-col gap-3">
	<InfoCallout
		>{$i18n.t(
			'Surfaces suspicious activity automatically flagged by the audit system, such as repeated failed logins or unusual data access. Adjust the time window to investigate recent patterns.'
		)}</InfoCallout
	>
	<div class="flex items-center justify-between">
		<p class="text-xs text-gray-500 dark:text-gray-400">
			{$i18n.t('Heuristic detection of suspicious activity patterns.')}
		</p>
		<div class="flex gap-0.5 bg-gray-50 dark:bg-gray-850 rounded-lg p-0.5">
			{#each HOUR_OPTIONS as opt (opt.value)}
				<button
					onclick={() => (selectedHours = opt.value)}
					class="px-2.5 py-1 text-xs rounded-md transition-colors {selectedHours === opt.value
						? 'bg-white dark:bg-gray-800 font-medium text-gray-900 dark:text-white'
						: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
				>
					{opt.label}
				</button>
			{/each}
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center py-20 text-gray-400">
			<Spinner className="size-6" />
		</div>
	{:else if loadError}
		<EmptyState title={$i18n.t('Failed to load anomalies')} />
	{:else if anomalies.length === 0}
		<EmptyState title={$i18n.t('No anomalies detected in the selected window.')} />
	{:else}
		<div class="grid gap-2.5">
			{#each anomalies as anomaly (anomaly.type)}
				<div
					class="rounded-2xl border border-gray-50 dark:border-gray-850 border-l-2 {severityAccent(
						anomaly.severity
					)} p-4"
				>
					<div class="flex items-start gap-3">
						<span class="size-2 mt-1.5 rounded-full shrink-0 {severityDot(anomaly.severity)}"
						></span>
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 mb-1 flex-wrap">
								<span class="font-medium text-sm">{anomalyTitle(anomaly.type)}</span>
								<span
									class="px-1.5 py-0.5 rounded text-xs font-medium {severityBadge(
										anomaly.severity
									)}"
								>
									{anomaly.severity}
								</span>
							</div>
							<div class="text-xs text-gray-400 mb-3">
								{$i18n.t('Detected')}: {formatTimestamp(anomaly.detected_at)}
							</div>
							<div class="grid grid-cols-2 lg:grid-cols-3 gap-2 text-xs">
								{#each Object.entries(anomaly.details) as [key, value] (key)}
									<div>
										<span class="text-gray-400">{humanize(key)}:</span>
										<span class="ml-1 font-medium text-gray-700 dark:text-gray-300">{value}</span>
									</div>
								{/each}
							</div>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
