<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { getAuditLogs, getAuditStats, exportAuditLogs } from '$lib/apis/audit';
	import type { AuditLog } from '$lib/apis/audit';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import LogDetailModal from './LogDetailModal.svelte';

	import {
		formatTimestamp,
		severityDot,
		humanize,
		triggerDownload,
		fileStamp,
		NEUTRAL_BADGE
	} from './utils';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const PAGE_SIZE = 25;

	let logs = $state<AuditLog[]>([]);
	let total = $state(0);
	let page = $state(0);
	let loading = $state(true);
	let exporting = $state(false);
	let expandedId = $state<string | null>(null);
	let selectedLog = $state<AuditLog | null>(null);
	let showDetailModal = $state(false);

	// Filter options are derived from the live stats so the dropdowns only ever
	// offer values that actually occur in the data.
	let severityOptions = $state<string[]>([]);
	let actionOptions = $state<string[]>([]);
	let resourceOptions = $state<string[]>([]);

	let search = $state('');
	let severity = $state('');
	let action = $state('');
	let resourceType = $state('');
	let startDate = $state('');
	let endDate = $state('');

	let totalPages = $derived(Math.max(Math.ceil(total / PAGE_SIZE), 1));
	let hasFilters = $derived(
		!!(search || severity || action || resourceType || startDate || endDate)
	);

	function buildParams() {
		return {
			search: search || undefined,
			severity: severity || undefined,
			action: action || undefined,
			resource_type: resourceType || undefined,
			// Interpret the date-only inputs as local-day boundaries (end inclusive of
			// the whole day) — `new Date('YYYY-MM-DD')` would parse as UTC midnight and
			// drop ~a day for non-UTC users. The backend filters `timestamp <= end_time`.
			start_time: startDate ? new Date(startDate + 'T00:00:00').getTime() : undefined,
			end_time: endDate ? new Date(endDate + 'T23:59:59.999').getTime() : undefined
		};
	}

	async function loadLogs() {
		const token = '';
		loading = true;
		expandedId = null;
		try {
			const result = await getAuditLogs(token, {
				skip: page * PAGE_SIZE,
				limit: PAGE_SIZE,
				...buildParams()
			});
			logs = result.logs;
			total = result.total;
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			loading = false;
		}
	}

	function applyFilters() {
		page = 0;
		loadLogs();
	}

	function clearFilters() {
		search = '';
		severity = '';
		action = '';
		resourceType = '';
		startDate = '';
		endDate = '';
		applyFilters();
	}

	async function exportHandler(format: 'csv' | 'json') {
		const token = '';
		exporting = true;
		try {
			const blob = await exportAuditLogs(token, format, buildParams());
			triggerDownload(blob, `audit-logs-${fileStamp()}.${format}`);
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			exporting = false;
		}
	}

	onMount(async () => {
		const token = '';
		const stats = await getAuditStats(token).catch(() => null);
		if (stats) {
			severityOptions = Object.keys(stats.by_severity ?? {});
			actionOptions = Object.keys(stats.by_action ?? {});
			resourceOptions = Object.keys(stats.by_resource_type ?? {});
		}
		await loadLogs();
	});
</script>

<div class="flex flex-col gap-3">
	<InfoCallout
		>{$i18n.t(
			'Browse and search the complete audit trail of every recorded action. Filter by severity, action, resource, or date range, and export the results for review.'
		)}</InfoCallout
	>
	<!-- Search + export -->
	<div class="flex items-center gap-2">
		<div class="flex flex-1 items-center rounded-xl bg-gray-50 dark:bg-gray-850 px-3">
			<Search className="size-4 text-gray-400" />
			<input
				class="w-full text-sm bg-transparent outline-hidden py-2 px-2.5"
				bind:value={search}
				placeholder={$i18n.t('Search logs by path, user, or resource')}
				onkeydown={(e) => e.key === 'Enter' && applyFilters()}
			/>
		</div>

		<Tooltip content={$i18n.t('Export CSV')}>
			<button
				class="p-2 rounded-xl border border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-40"
				onclick={() => exportHandler('csv')}
				disabled={exporting}
			>
				{#if exporting}
					<Spinner className="size-4" />
				{:else}
					<ArrowDownTray className="size-4" />
				{/if}
			</button>
		</Tooltip>
	</div>

	<!-- Filters -->
	<div class="flex flex-wrap items-center gap-2 text-sm">
		<select
			class="min-w-32 rounded-lg border-none bg-gray-50 dark:bg-gray-850 text-gray-700 dark:text-gray-300 px-2.5 py-1.5 text-xs outline-none cursor-pointer"
			bind:value={severity}
			onchange={applyFilters}
			aria-label={$i18n.t('Severity')}
		>
			<option value="">{$i18n.t('All severities')}</option>
			{#each severityOptions as opt (opt)}
				<option value={opt}>{opt}</option>
			{/each}
		</select>

		<select
			class="min-w-32 rounded-lg border-none bg-gray-50 dark:bg-gray-850 text-gray-700 dark:text-gray-300 px-2.5 py-1.5 text-xs outline-none cursor-pointer"
			bind:value={action}
			onchange={applyFilters}
			aria-label={$i18n.t('Action')}
		>
			<option value="">{$i18n.t('All actions')}</option>
			{#each actionOptions as opt (opt)}
				<option value={opt}>{opt}</option>
			{/each}
		</select>

		<select
			class="min-w-32 rounded-lg border-none bg-gray-50 dark:bg-gray-850 text-gray-700 dark:text-gray-300 px-2.5 py-1.5 text-xs outline-none cursor-pointer"
			bind:value={resourceType}
			onchange={applyFilters}
			aria-label={$i18n.t('Resource')}
		>
			<option value="">{$i18n.t('All resources')}</option>
			{#each resourceOptions as opt (opt)}
				<option value={opt}>{humanize(opt)}</option>
			{/each}
		</select>

		<input
			type="date"
			class="rounded-lg border-none bg-gray-50 dark:bg-gray-850 dark:[color-scheme:dark] text-gray-700 dark:text-gray-300 px-2.5 py-1.5 text-xs outline-none cursor-pointer"
			bind:value={startDate}
			onchange={applyFilters}
			aria-label={$i18n.t('From date')}
		/>
		<span class="text-xs text-gray-400">—</span>
		<input
			type="date"
			class="rounded-lg border-none bg-gray-50 dark:bg-gray-850 dark:[color-scheme:dark] text-gray-700 dark:text-gray-300 px-2.5 py-1.5 text-xs outline-none cursor-pointer"
			bind:value={endDate}
			onchange={applyFilters}
			aria-label={$i18n.t('To date')}
		/>

		{#if hasFilters}
			<button
				class="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white px-2 py-1"
				onclick={clearFilters}
			>
				{$i18n.t('Clear')}
			</button>
		{/if}
	</div>

	<!-- Table -->
	<div class="rounded-2xl border border-gray-50 dark:border-gray-850 overflow-hidden">
		{#if loading}
			<div class="flex justify-center py-16 text-gray-400">
				<Spinner className="size-5" />
			</div>
		{:else if logs.length === 0}
			<EmptyState
				title={$i18n.t('No audit logs found')}
				description={hasFilters ? $i18n.t('Try adjusting your filters.') : ''}
			/>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr
							class="border-b border-gray-50 dark:border-gray-850 text-left text-xs uppercase text-gray-700 bg-gray-50 dark:bg-gray-850 dark:text-gray-400"
						>
							<th class="px-4 py-2.5 font-medium w-6"></th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('Time')}</th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('User')}</th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('Action')}</th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('Resource')}</th>
							<th class="px-2 py-2.5 font-medium hidden lg:table-cell">{$i18n.t('IP Address')}</th>
							<th class="px-2 py-2.5 font-medium hidden md:table-cell">{$i18n.t('Status')}</th>
							<th class="px-4 py-2.5 font-medium">{$i18n.t('Severity')}</th>
						</tr>
					</thead>
					<tbody>
						{#each logs as log (log.id)}
							<tr
								class="border-b border-gray-50 dark:border-gray-850 hover:bg-gray-50/70 dark:hover:bg-gray-850/50 transition-colors"
							>
								<td class="px-4 py-2.5">
									<button
										type="button"
										class="flex text-gray-300 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 transition"
										aria-expanded={expandedId === log.id}
										aria-label={$i18n.t('Toggle details')}
										onclick={() => (expandedId = expandedId === log.id ? null : log.id)}
									>
										<ChevronDown
											className="size-3.5 transition-transform {expandedId === log.id
												? 'rotate-180'
												: ''}"
										/>
									</button>
								</td>
								<td class="px-2 py-2.5 text-xs text-gray-500 whitespace-nowrap">
									{formatTimestamp(log.timestamp)}
								</td>
								<td class="px-2 py-2.5 text-xs truncate max-w-[160px]">
									{log.user_email || log.user_id?.slice(0, 8) || '—'}
								</td>
								<td class="px-2 py-2.5">
									<span class="px-1.5 py-0.5 rounded text-xs font-medium {NEUTRAL_BADGE}">
										{log.action}
									</span>
								</td>
								<td class="px-2 py-2.5 text-xs text-gray-600 dark:text-gray-300">
									{humanize(log.resource_type)}
								</td>
								<td class="px-2 py-2.5 text-xs text-gray-500 hidden lg:table-cell">
									{log.ip_address || '—'}
								</td>
								<td class="px-2 py-2.5 text-xs text-gray-500 hidden md:table-cell">
									{log.response_status ?? '—'}
								</td>
								<td class="px-4 py-2.5">
									<span class="inline-flex items-center gap-1.5 text-xs">
										<span class="size-1.5 rounded-full {severityDot(log.severity)}"></span>
										<span class="text-gray-600 dark:text-gray-300">{log.severity}</span>
									</span>
								</td>
							</tr>
							{#if expandedId === log.id}
								<tr class="bg-gray-50/60 dark:bg-gray-850/40">
									<td colspan="8" class="px-4 py-3">
										<div class="grid grid-cols-2 lg:grid-cols-4 gap-x-4 gap-y-2 text-xs">
											<div>
												<span class="text-gray-400">{$i18n.t('Resource ID')}</span>
												<div class="font-mono text-gray-700 dark:text-gray-300 truncate">
													{log.resource_id || '—'}
												</div>
											</div>
											<div>
												<span class="text-gray-400">{$i18n.t('Method')}</span>
												<div class="text-gray-700 dark:text-gray-300">
													{log.request_method || '—'}
												</div>
											</div>
											<div class="lg:col-span-2">
												<span class="text-gray-400">{$i18n.t('Path')}</span>
												<div class="font-mono text-gray-700 dark:text-gray-300 truncate">
													{log.request_path || '—'}
												</div>
											</div>
											<div class="lg:col-span-2">
												<span class="text-gray-400">{$i18n.t('Category')}</span>
												<div class="text-gray-700 dark:text-gray-300">{log.category || '—'}</div>
											</div>
											<div class="lg:col-span-2">
												<span class="text-gray-400">{$i18n.t('User Agent')}</span>
												<div class="text-gray-700 dark:text-gray-300 truncate">
													{log.user_agent || '—'}
												</div>
											</div>
											{#if log.details}
												<div class="col-span-2 lg:col-span-4">
													<span class="text-gray-400">{$i18n.t('Details')}</span>
													<pre
														class="mt-1 p-2.5 rounded-lg bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 overflow-x-auto font-mono text-gray-700 dark:text-gray-300">{JSON.stringify(
															log.details,
															null,
															2
														)}</pre>
												</div>
											{/if}
										</div>
										<div class="col-span-2 lg:col-span-4 flex justify-end pt-1">
											<button
												type="button"
												class="text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 px-2.5 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
												onclick={() => {
													selectedLog = log;
													showDetailModal = true;
												}}
											>
												{$i18n.t('View Details')}
											</button>
										</div>
									</td>
								</tr>
							{/if}
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Pagination -->
			<div
				class="flex items-center justify-between px-4 py-3 border-t border-gray-50 dark:border-gray-850"
			>
				<span class="text-xs text-gray-500">
					{$i18n.t('{{total}} records · page {{page}} of {{pages}}', {
						total: total.toLocaleString(),
						page: page + 1,
						pages: totalPages
					})}
				</span>
				<div class="flex items-center gap-1">
					<button
						class="p-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-850 disabled:opacity-30 transition"
						onclick={() => {
							page = Math.max(0, page - 1);
							loadLogs();
						}}
						disabled={page === 0}
						aria-label={$i18n.t('Previous')}
					>
						<ChevronLeft className="size-4" />
					</button>
					<button
						class="p-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-850 disabled:opacity-30 transition"
						onclick={() => {
							page = Math.min(totalPages - 1, page + 1);
							loadLogs();
						}}
						disabled={page >= totalPages - 1}
						aria-label={$i18n.t('Next')}
					>
						<ChevronRight className="size-4" />
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

<LogDetailModal bind:show={showDetailModal} log={selectedLog} />
