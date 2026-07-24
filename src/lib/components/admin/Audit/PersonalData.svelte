<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { getPersonalDataAccess } from '$lib/apis/audit';
	import type { AuditLog } from '$lib/apis/audit';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import { formatTimestamp, humanize, NEUTRAL_BADGE, piiLabel, piiBadge } from './utils';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const PAGE_SIZE = 25;

	let logs = $state<AuditLog[]>([]);
	let total = $state(0);
	let page = $state(0);
	let loading = $state(true);
	let filterUserId = $state('');
	let expandedId = $state<string | null>(null);

	let totalPages = $derived(Math.max(Math.ceil(total / PAGE_SIZE), 1));

	function isPiiMasked(log: AuditLog): boolean {
		return log.action === 'PII_MASKED';
	}

	function getPiiTypes(log: AuditLog): string[] {
		if (!log.details?.threat_types) return [];
		return Array.isArray(log.details.threat_types) ? (log.details.threat_types as string[]) : [];
	}

	function getThreatCount(log: AuditLog): number {
		return typeof log.details?.threat_count === 'number' ? (log.details.threat_count as number) : 0;
	}

	async function loadData() {
		const token = '';
		loading = true;
		try {
			const result = await getPersonalDataAccess(token, {
				skip: page * PAGE_SIZE,
				limit: PAGE_SIZE,
				user_id: filterUserId || undefined
			});
			logs = result.logs;
			total = result.total;
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			loading = false;
		}
	}

	function applyFilter() {
		page = 0;
		loadData();
	}

	function toggleExpand(id: string) {
		expandedId = expandedId === id ? null : id;
	}

	onMount(() => loadData());
</script>

<div class="flex flex-col gap-3">
	<InfoCallout variant="warning"
		>{$i18n.t(
			'This page exposes sensitive personal-data access records for privacy compliance and investigation. Review entries responsibly and only when necessary.'
		)}</InfoCallout
	>
	<p class="text-xs text-gray-500 dark:text-gray-400">
		{$i18n.t('Every access to personally identifiable information, recorded for compliance.')}
	</p>

	<!-- Filter -->
	<div class="flex items-center gap-2">
		<div class="flex flex-1 items-center rounded-xl bg-gray-50 dark:bg-gray-850 px-3">
			<Search className="size-4 text-gray-400" />
			<input
				class="w-full text-sm bg-transparent outline-hidden py-2 px-2.5"
				bind:value={filterUserId}
				placeholder={$i18n.t('Filter by user ID')}
				onkeydown={(e) => e.key === 'Enter' && applyFilter()}
			/>
		</div>
	</div>

	<!-- Table -->
	<div class="rounded-2xl border border-gray-50 dark:border-gray-850 overflow-hidden">
		{#if loading}
			<div class="flex justify-center py-16 text-gray-400">
				<Spinner className="size-5" />
			</div>
		{:else if logs.length === 0}
			<EmptyState title={$i18n.t('No personal data access records found')} />
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr
							class="border-b border-gray-50 dark:border-gray-850 text-left text-xs uppercase text-gray-700 bg-gray-50 dark:bg-gray-850 dark:text-gray-400"
						>
							<th class="w-8 px-2 py-2.5"></th>
							<th class="px-4 py-2.5 font-medium">{$i18n.t('Time')}</th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('User')}</th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('Action')}</th>
							<th class="px-2 py-2.5 font-medium">{$i18n.t('Resource')}</th>
							<th class="px-2 py-2.5 font-medium hidden md:table-cell">{$i18n.t('Filtered PII')}</th
							>
							<th class="px-2 py-2.5 font-medium hidden lg:table-cell">{$i18n.t('IP Address')}</th>
						</tr>
					</thead>
					<tbody>
						{#each logs as log (log.id)}
							{@const piiTypes = getPiiTypes(log)}
							{@const masked = isPiiMasked(log)}
							{@const expanded = expandedId === log.id}

							<tr
								class="border-b border-gray-50 dark:border-gray-850 hover:bg-gray-50/70 dark:hover:bg-gray-850/50 transition-colors cursor-pointer"
								onclick={() => toggleExpand(log.id)}
								onkeydown={(e) => e.key === 'Enter' && toggleExpand(log.id)}
								role="button"
								tabindex="0"
								aria-expanded={expanded}
							>
								<td class="px-2 py-2.5 text-gray-400">
									<ChevronDown
										className="size-3.5 transition-transform {expanded ? 'rotate-180' : ''}"
									/>
								</td>
								<td class="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">
									{formatTimestamp(log.timestamp)}
								</td>
								<td class="px-2 py-2.5 text-xs truncate max-w-[160px]">
									{log.user_email || log.user_id?.slice(0, 8) || '—'}
								</td>
								<td class="px-2 py-2.5 text-xs">
									{#if masked}
										<span
											class="px-1.5 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
										>
											PII Masked
										</span>
									{:else}
										<span class="text-gray-600 dark:text-gray-300">{humanize(log.action)}</span>
									{/if}
								</td>
								<td class="px-2 py-2.5">
									<span class="px-1.5 py-0.5 rounded text-xs font-medium {NEUTRAL_BADGE}">
										{humanize(log.resource_type)}
									</span>
								</td>
								<td class="px-2 py-2.5 hidden md:table-cell">
									{#if piiTypes.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each piiTypes as type (type)}
												<span class="px-1.5 py-0.5 rounded text-xs font-medium {piiBadge(type)}">
													{piiLabel(type)}
												</span>
											{/each}
										</div>
									{:else if log.details}
										<span
											class="text-xs text-gray-400 truncate max-w-[200px] inline-block align-middle"
										>
											{JSON.stringify(log.details)}
										</span>
									{:else}
										<span class="text-xs text-gray-400">—</span>
									{/if}
								</td>
								<td class="px-2 py-2.5 text-xs text-gray-500 hidden lg:table-cell">
									{log.ip_address || '—'}
								</td>
							</tr>

							{#if expanded}
								<tr class="border-b border-gray-50 dark:border-gray-850">
									<td colspan="7" class="px-4 py-3 bg-gray-50/50 dark:bg-gray-850/30">
										<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
											{#if masked}
												<div>
													<span class="text-gray-500 font-medium">{$i18n.t('Threat Count')}</span>
													<p class="mt-0.5 font-semibold text-red-600 dark:text-red-400">
														{getThreatCount(log)}
													</p>
												</div>
												{#if log.details?.chat_id}
													<div>
														<span class="text-gray-500 font-medium">{$i18n.t('Chat ID')}</span>
														<p class="mt-0.5 font-mono text-gray-600 dark:text-gray-300">
															{log.details.chat_id}
														</p>
													</div>
												{/if}
											{/if}

											<div>
												<span class="text-gray-500 font-medium">{$i18n.t('Resource ID')}</span>
												<p class="mt-0.5 font-mono text-gray-600 dark:text-gray-300">
													{log.resource_id || '—'}
												</p>
											</div>

											{#if log.resource_name}
												<div>
													<span class="text-gray-500 font-medium">{$i18n.t('Resource Name')}</span>
													<p class="mt-0.5 text-gray-600 dark:text-gray-300">
														{log.resource_name}
													</p>
												</div>
											{/if}

											{#if log.ip_address}
												<div>
													<span class="text-gray-500 font-medium">{$i18n.t('IP Address')}</span>
													<p class="mt-0.5 font-mono text-gray-600 dark:text-gray-300">
														{log.ip_address}
													</p>
												</div>
											{/if}

											{#if log.request_path}
												<div>
													<span class="text-gray-500 font-medium">{$i18n.t('Request Path')}</span>
													<p class="mt-0.5 font-mono text-gray-600 dark:text-gray-300">
														{log.request_method || 'GET'}
														{log.request_path}
													</p>
												</div>
											{/if}

											{#if log.user_agent}
												<div class="md:col-span-2">
													<span class="text-gray-500 font-medium">{$i18n.t('User Agent')}</span>
													<p class="mt-0.5 font-mono text-gray-600 dark:text-gray-300 break-all">
														{log.user_agent}
													</p>
												</div>
											{/if}

											{#if log.details && !masked}
												<div class="md:col-span-2 lg:col-span-3">
													<span class="text-gray-500 font-medium">{$i18n.t('Details')}</span>
													<pre
														class="mt-0.5 p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 text-xs overflow-x-auto whitespace-pre-wrap">{JSON.stringify(
															log.details,
															null,
															2
														)}</pre>
												</div>
											{/if}
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
							loadData();
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
							loadData();
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
