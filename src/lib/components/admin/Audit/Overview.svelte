<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import {
		getAuditStats,
		getAuditLogs,
		getAuditTimeline,
		getComplianceSummary,
		getAuditConfig
	} from '$lib/apis/audit';
	import type {
		AuditStats,
		AuditLog,
		TimelineData,
		ComplianceSummary,
		AuditConfig
	} from '$lib/apis/audit';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { formatRelativeTime, severityDot, severityBar, humanize, NEUTRAL_BADGE } from './utils';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let stats = $state<AuditStats | null>(null);
	let recentLogs = $state<AuditLog[]>([]);
	let timeline = $state<TimelineData[]>([]);
	let compliance = $state<ComplianceSummary | null>(null);
	let auditConfig = $state<AuditConfig | null>(null);
	let loading = $state(true);

	let maxTimeline = $derived(Math.max(...timeline.map((t) => t.count), 1));

	onMount(async () => {
		// Auth is cookie-based; the token arg is vestigial. (Previously this read
		// localStorage.token and bailed when empty — which now happens always,
		// leaving the spinner stuck forever.)
		const token = '';

		const [statsResult, logsResult, timelineResult, complianceResult, configResult] =
			await Promise.all([
				getAuditStats(token).catch(() => null),
				getAuditLogs(token, { limit: 8 }).catch(() => ({ logs: [], total: 0 })),
				getAuditTimeline(token, 24, 'hour').catch(() => ({ data: [] })),
				getComplianceSummary(token).catch(() => null),
				getAuditConfig(token).catch(() => null)
			]);

		stats = statsResult;
		recentLogs = logsResult.logs;
		timeline = timelineResult.data;
		compliance = complianceResult;
		auditConfig = configResult;
		loading = false;

		// Don't let a failed dashboard load masquerade as a healthy-but-empty system.
		if (!statsResult) toast.error($i18n.t('Failed to load audit data'));
	});
</script>

{#if loading}
	<div class="flex justify-center py-24 text-gray-400">
		<Spinner className="size-6" />
	</div>
{:else}
	<div class="flex flex-col gap-5">
		<InfoCallout
			>{$i18n.t(
				'A real-time snapshot of audit activity across the platform — log volume, severity breakdown, and compliance signals at a glance.'
			)}</InfoCallout
		>
		{#if auditConfig}
			<div
				class="flex items-center justify-between rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-850 px-3 py-2"
			>
				<div class="flex items-center gap-2 text-xs">
					<span
						class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {auditConfig.audit_log_level ===
						'NONE'
							? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
							: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'}"
					>
						{auditConfig.audit_log_level === 'NONE' ? $i18n.t('Disabled') : $i18n.t('Active')}
					</span>
					<span class="text-gray-500 dark:text-gray-400">
						{$i18n.t('Level')}: {auditConfig.audit_log_level} &middot; {$i18n.t('Retention')}: {auditConfig.audit_retention_days}
						{$i18n.t('days')}
					</span>
				</div>
				<a
					href={resolve('/admin/settings?tab=audit')}
					class="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
				>
					{$i18n.t('Configure audit settings')}
				</a>
			</div>
		{/if}
		<div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
			<div class="rounded-2xl bg-gray-50 dark:bg-gray-850 px-4 py-3.5">
				<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Total Logs')}</div>
				<div class="text-2xl font-semibold mt-1">{(stats?.total_logs ?? 0).toLocaleString()}</div>
			</div>
			<div class="rounded-2xl bg-gray-50 dark:bg-gray-850 px-4 py-3.5">
				<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Logs Today')}</div>
				<div class="text-2xl font-semibold mt-1">{(stats?.logs_today ?? 0).toLocaleString()}</div>
			</div>
			<div class="rounded-2xl bg-gray-50 dark:bg-gray-850 px-4 py-3.5">
				<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Critical (24h)')}</div>
				<div
					class="text-2xl font-semibold mt-1 {(stats?.recent_critical_count ?? 0) > 0
						? 'text-red-600 dark:text-red-400'
						: ''}"
				>
					{(stats?.recent_critical_count ?? 0).toLocaleString()}
				</div>
			</div>
			<div class="rounded-2xl bg-gray-50 dark:bg-gray-850 px-4 py-3.5">
				<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Active Users Today')}</div>
				<div class="text-2xl font-semibold mt-1">
					{(stats?.active_users_today ?? 0).toLocaleString()}
				</div>
			</div>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-3 gap-2.5">
			<!-- Severity distribution -->
			<div class="rounded-2xl border border-gray-50 dark:border-gray-850 px-4 py-4">
				<div class="text-sm font-medium mb-4">{$i18n.t('Severity Distribution')}</div>
				{#if stats?.by_severity && Object.keys(stats.by_severity).length > 0}
					<div class="flex flex-col gap-3">
						{#each Object.entries(stats.by_severity) as [sev, count] (sev)}
							<div>
								<div class="flex justify-between text-xs mb-1.5">
									<span class="capitalize text-gray-600 dark:text-gray-300"
										>{sev.toLowerCase()}</span
									>
									<span class="text-gray-400">{count.toLocaleString()}</span>
								</div>
								<div class="w-full bg-gray-100 dark:bg-gray-850 rounded-full h-1.5">
									<div
										class="h-1.5 rounded-full {severityBar(sev)}"
										style="width: {Math.max(
											(count / Math.max(stats?.total_logs || 1, 1)) * 100,
											2
										)}%"
									></div>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-sm text-gray-400 py-10 text-center">{$i18n.t('No data')}</div>
				{/if}
			</div>

			<!-- Activity timeline -->
			<div class="lg:col-span-2 rounded-2xl border border-gray-50 dark:border-gray-850 px-4 py-4">
				<div class="text-sm font-medium mb-4">{$i18n.t('Activity (Last 24h)')}</div>
				{#if timeline.length > 0}
					<div class="flex items-end gap-0.5 h-28">
						{#each timeline as bucket (bucket.timestamp)}
							<div
								class="flex-1 bg-gray-200 hover:bg-gray-400 dark:bg-gray-700 dark:hover:bg-gray-500 rounded-t transition-colors min-w-[2px]"
								style="height: {Math.max((bucket.count / maxTimeline) * 100, 2)}%"
								title="{new Date(bucket.timestamp).toLocaleTimeString()} · {bucket.count}"
							></div>
						{/each}
					</div>
					<div class="flex justify-between text-xs text-gray-400 mt-2">
						<span>{$i18n.t('24h ago')}</span>
						<span>{$i18n.t('Now')}</span>
					</div>
				{:else}
					<div class="text-sm text-gray-400 py-10 text-center">{$i18n.t('No activity')}</div>
				{/if}
			</div>
		</div>

		<!-- Compliance summary -->
		{#if compliance}
			<div class="rounded-2xl border border-gray-50 dark:border-gray-850 px-4 py-4">
				<div class="flex items-baseline justify-between mb-4">
					<div class="text-sm font-medium">{$i18n.t('Compliance Summary')}</div>
					<div class="text-xs text-gray-400">
						{$i18n.t('Last {{count}} days', { count: compliance.period_days })}
					</div>
				</div>
				<div class="grid grid-cols-2 lg:grid-cols-4 gap-y-4 gap-x-2">
					<div>
						<div class="text-xs text-gray-500 dark:text-gray-400">
							{$i18n.t('Personal Data Access')}
						</div>
						<div class="text-lg font-semibold mt-0.5">
							{compliance.personal_data_access_count.toLocaleString()}
						</div>
						{#if compliance.pii_masked_count > 0}
							<div class="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
								{$i18n.t('PII Masked')}: {compliance.pii_masked_count.toLocaleString()}
							</div>
						{/if}
					</div>
					<div>
						<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Data Exports')}</div>
						<div class="text-lg font-semibold mt-0.5">
							{compliance.data_exports.toLocaleString()}
						</div>
					</div>
					<div>
						<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Security Events')}</div>
						<div class="text-lg font-semibold mt-0.5">
							{compliance.security_events.toLocaleString()}
						</div>
					</div>
					<div>
						<div class="text-xs text-gray-500 dark:text-gray-400">
							{$i18n.t('Failed Auth Attempts')}
						</div>
						<div
							class="text-lg font-semibold mt-0.5 {compliance.failed_auth_attempts > 0
								? 'text-amber-600 dark:text-amber-400'
								: ''}"
						>
							{compliance.failed_auth_attempts.toLocaleString()}
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Recent activity -->
		<div class="rounded-2xl border border-gray-50 dark:border-gray-850 overflow-hidden">
			<div class="px-4 py-3 border-b border-gray-50 dark:border-gray-850 text-sm font-medium">
				{$i18n.t('Recent Activity')}
			</div>
			{#if recentLogs.length > 0}
				<div class="divide-y divide-gray-50 dark:divide-gray-850">
					{#each recentLogs as log (log.id)}
						<div class="flex items-center gap-3 px-4 py-2.5">
							<span class="size-1.5 rounded-full shrink-0 {severityDot(log.severity)}"></span>
							<span class="px-1.5 py-0.5 rounded text-xs font-medium shrink-0 {NEUTRAL_BADGE}">
								{log.action}
							</span>
							<span class="text-sm text-gray-600 dark:text-gray-300 flex-1 truncate">
								{log.request_path || humanize(log.resource_type)}
							</span>
							<span class="text-xs text-gray-400 truncate max-w-[140px] hidden sm:block">
								{log.user_email || $i18n.t('System')}
							</span>
							<span class="text-xs text-gray-400 shrink-0">
								{formatRelativeTime(log.timestamp, $i18n.t)}
							</span>
						</div>
					{/each}
				</div>
			{:else}
				<div class="px-4 py-12 text-center text-sm text-gray-400">
					{$i18n.t('No recent audit activity')}
				</div>
			{/if}
		</div>
	</div>
{/if}
