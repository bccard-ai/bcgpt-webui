<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { logger } from '$lib/utils/logger';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import { getAuditLogs, exportAuditLogs } from '$lib/apis/audit';
	import type { AuditLog } from '$lib/apis/audit';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const PAGE_SIZE = 25;
	const ACTIONS = ['CREATE', 'READ', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'EXPORT', 'ACCESS'];
	const RESOURCE_TYPES = ['user', 'chat', 'message', 'file', 'function', 'config', 'auth', 'api_key', 'evaluation', 'system'];
	const SEVERITIES = ['INFO', 'WARNING', 'CRITICAL'];

	let logs = $state<AuditLog[]>([]);
	let total = $state(0);
	let page = $state(0);
	let loading = $state(true);
	let expandedId = $state<string | null>(null);

	let filterAction = $state('');
	let filterResourceType = $state('');
	let filterSeverity = $state('');
	let filterSearch = $state('');

	function formatTime(ms: number): string {
		return new Date(ms).toLocaleString();
	}

	function severityColor(sev: string): string {
		if (sev === 'CRITICAL') return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
		if (sev === 'WARNING') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
		return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
	}

	function actionColor(action: string): string {
		const colors: Record<string, string> = {
			CREATE: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
			UPDATE: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
			DELETE: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
			LOGIN: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
			EXPORT: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400',
		};
		return colors[action] || 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400';
	}

	function totalPages(): number {
		return Math.ceil(total / PAGE_SIZE);
	}

	async function loadLogs() {
		const token = '';

		loading = true;
		try {
			const result = await getAuditLogs(token, {
				skip: page * PAGE_SIZE,
				limit: PAGE_SIZE,
				action: filterAction || undefined,
				resource_type: filterResourceType || undefined,
				severity: filterSeverity || undefined,
				search: filterSearch || undefined
			});
			logs = result.logs;
			total = result.total;
		} catch (e) {
			logger.error('audit', 'Failed to load audit logs', undefined, e);
		} finally {
			loading = false;
		}
	}

	async function handleExport(format: string) {
		const token = '';

		try {
			const blob = await exportAuditLogs(token, format, {
				action: filterAction || undefined,
				resource_type: filterResourceType || undefined,
				severity: filterSeverity || undefined
			});
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `audit_logs.${format}`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			logger.error('audit', 'Export failed', undefined, e);
		}
	}

	function applyFilters() {
		page = 0;
		loadLogs();
	}

	function resetFilters() {
		filterAction = '';
		filterResourceType = '';
		filterSeverity = '';
		filterSearch = '';
		page = 0;
		loadLogs();
	}

	onMount(() => loadLogs());
</script>

<svelte:head>
	<title>{$i18n.t('Audit Logs')} | {$i18n.t('Admin')}</title>
</svelte:head>

<div class="flex flex-col gap-5">
	<div class="flex items-center justify-between">
		<div class="text-lg font-medium">{$i18n.t('Audit Logs')}</div>
		<div class="flex gap-2">
			<button
				onclick={() => handleExport('csv')}
				class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
			>
				{$i18n.t('Export CSV')}
			</button>
			<button
				onclick={() => handleExport('json')}
				class="px-3 py-1.5 text-xs rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
			>
				{$i18n.t('Export JSON')}
			</button>
		</div>
	</div>

	<!-- Filters -->
	<div class="bg-white dark:bg-gray-850 rounded-xl p-4 shadow-sm border border-gray-100 dark:border-gray-750">
		<div class="flex flex-wrap gap-3 items-end">
		<div class="flex flex-col gap-1">
			<label for="audit-filter-search" class="text-xs text-gray-500"
				>{$i18n.t('Search')}</label
			>
			<input
				id="audit-filter-search"
				type="text"
				bind:value={filterSearch}
					placeholder={$i18n.t('email, path, IP...')}
					class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent min-w-[180px]"
					onkeydown={(e) => e.key === 'Enter' && applyFilters()}
				/>
			</div>
		<div class="flex flex-col gap-1">
			<label for="audit-filter-action" class="text-xs text-gray-500"
				>{$i18n.t('Action')}</label
			>
			<select
				id="audit-filter-action"
				bind:value={filterAction}
					class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent"
				>
					<option value="">{$i18n.t('All')}</option>
					{#each ACTIONS as a (a)}
						<option value={a}>{a}</option>
					{/each}
				</select>
			</div>
		<div class="flex flex-col gap-1">
			<label for="audit-filter-resource" class="text-xs text-gray-500"
				>{$i18n.t('Resource')}</label
			>
			<select
				id="audit-filter-resource"
				bind:value={filterResourceType}
					class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent"
				>
					<option value="">{$i18n.t('All')}</option>
					{#each RESOURCE_TYPES as r (r)}
						<option value={r}>{r}</option>
					{/each}
				</select>
			</div>
		<div class="flex flex-col gap-1">
			<label for="audit-filter-severity" class="text-xs text-gray-500"
				>{$i18n.t('Severity')}</label
			>
			<select
				id="audit-filter-severity"
				bind:value={filterSeverity}
					class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent"
				>
					<option value="">{$i18n.t('All')}</option>
					{#each SEVERITIES as s (s)}
						<option value={s}>{s}</option>
					{/each}
				</select>
			</div>
			<button
				onclick={applyFilters}
				class="px-4 py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
			>
				{$i18n.t('Filter')}
			</button>
			<button
				onclick={resetFilters}
				class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
			>
				{$i18n.t('Reset')}
			</button>
		</div>
	</div>

	<!-- Table -->
	<div class="bg-white dark:bg-gray-850 rounded-xl shadow-sm border border-gray-100 dark:border-gray-750 overflow-hidden">
		{#if loading}
			<div class="flex justify-center py-16">
				<div class="animate-spin h-6 w-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
			</div>
		{:else if logs.length === 0}
			<div class="p-12 text-center text-sm text-gray-400">{$i18n.t('No audit logs found')}</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-100 dark:border-gray-750 text-left text-xs text-gray-500">
							<th class="px-4 py-3 font-medium">{$i18n.t('Time')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('User')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('Action')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('Resource')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('Path')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('Severity')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('IP')}</th>
							<th class="px-4 py-3 font-medium">{$i18n.t('Status')}</th>
						</tr>
					</thead>
					<tbody>
						{#each logs as log (log.id)}
							<tr
								class="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
								onclick={() => (expandedId = expandedId === log.id ? null : log.id)}
							>
								<td class="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">{formatTime(log.timestamp)}</td>
								<td class="px-4 py-2.5 text-xs truncate max-w-[150px]">{log.user_email || log.user_id?.slice(0, 8) || '—'}</td>
								<td class="px-4 py-2.5">
									<span class="px-2 py-0.5 rounded-full text-xs font-medium {actionColor(log.action)}">{log.action}</span>
								</td>
								<td class="px-4 py-2.5 text-xs">{log.resource_type}</td>
								<td class="px-4 py-2.5 text-xs text-gray-500 truncate max-w-[200px]">{log.request_path || '—'}</td>
								<td class="px-4 py-2.5">
									<span class="px-2 py-0.5 rounded-full text-xs font-medium {severityColor(log.severity)}">{log.severity}</span>
								</td>
								<td class="px-4 py-2.5 text-xs text-gray-500">{log.ip_address || '—'}</td>
								<td class="px-4 py-2.5 text-xs">{log.response_status ?? '—'}</td>
							</tr>
							{#if expandedId === log.id}
								<tr>
									<td colspan="8" class="px-4 py-3 bg-gray-50 dark:bg-gray-800/30">
										<div class="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
											<div><span class="text-gray-400">{$i18n.t('ID:')}</span> {log.id}</div>
											<div><span class="text-gray-400">{$i18n.t('User ID:')}</span> {log.user_id || '—'}</div>
											<div><span class="text-gray-400">{$i18n.t('Resource ID:')}</span> {log.resource_id || '—'}</div>
											<div><span class="text-gray-400">{$i18n.t('Resource Name:')}</span> {log.resource_name || '—'}</div>
											<div><span class="text-gray-400">{$i18n.t('Method:')}</span> {log.request_method || '—'}</div>
											<div><span class="text-gray-400">{$i18n.t('Session:')}</span> {log.session_id || '—'}</div>
											<div><span class="text-gray-400">{$i18n.t('Category:')}</span> {log.category || '—'}</div>
											<div><span class="text-gray-400">{$i18n.t('User Agent:')}</span> <span class="truncate inline-block max-w-[300px]">{log.user_agent || '—'}</span></div>
										</div>
										{#if log.details}
											<div class="mt-3">
												<span class="text-xs text-gray-400">{$i18n.t('Details:')}</span>
												<pre class="mt-1 text-xs bg-gray-100 dark:bg-gray-900 rounded-lg p-3 overflow-x-auto max-h-40">{JSON.stringify(log.details, null, 2)}</pre>
											</div>
										{/if}
									</td>
								</tr>
							{/if}
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Pagination -->
			<div class="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-gray-750">
				<span class="text-xs text-gray-500">
					{$i18n.t('{{total}} results — page {{page}} of {{pages}}', {
						total,
						page: page + 1,
						pages: totalPages() || 1
					})}
				</span>
				<div class="flex gap-2">
					<button
						onclick={() => { page = Math.max(0, page - 1); loadLogs(); }}
						disabled={page === 0}
						class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-700 disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
					>
						{$i18n.t('Previous')}
					</button>
					<button
						onclick={() => { page = Math.min(totalPages() - 1, page + 1); loadLogs(); }}
						disabled={page >= totalPages() - 1}
						class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-700 disabled:opacity-30 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
					>
						{$i18n.t('Next')}
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
