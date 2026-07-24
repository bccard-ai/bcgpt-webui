<script lang="ts">
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import type { AuditLog } from '$lib/apis/audit';

	import Modal from '$lib/components/common/Modal.svelte';

	import { formatTimestamp, severityBadge, severityDot, humanize, NEUTRAL_BADGE } from './utils';

	interface Props {
		show?: boolean;
		log: AuditLog | null;
	}

	let { show = $bindable(false), log }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
	}
</script>

<Modal size="lg" bind:show>
	{#if log}
		<div class="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
			<!-- Header -->
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2.5">
					<span class="size-2.5 rounded-full {severityDot(log.severity)}"></span>
					<div class="text-lg font-medium text-gray-800 dark:text-gray-100">
						{$i18n.t('Audit Log Detail')}
					</div>
				</div>
				<button
					class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
					onclick={() => (show = false)}
					aria-label={$i18n.t('Close')}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="size-5 text-gray-400"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<hr class="border-gray-100 dark:border-gray-850" />

			<!-- Summary row -->
			<div class="flex flex-wrap items-center gap-2 text-xs">
				<span class="px-2 py-1 rounded-lg font-medium {severityBadge(log.severity)}">
					{log.severity}
				</span>
				<span class="px-2 py-1 rounded-lg font-medium {NEUTRAL_BADGE}">{log.action}</span>
				{#if log.category}
					<span class="px-2 py-1 rounded-lg font-medium {NEUTRAL_BADGE}">
						{humanize(log.category)}
					</span>
				{/if}
				{#if log.response_status}
					<span
						class="px-2 py-1 rounded-lg font-medium {log.response_status >= 400
							? 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
							: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'}"
					>
						{log.response_status}
					</span>
				{/if}
			</div>

			<!-- Timestamp & ID -->
			<div class="grid grid-cols-2 gap-4">
				<div>
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
						{$i18n.t('Timestamp')}
					</div>
					<div class="text-sm text-gray-700 dark:text-gray-300">
						{formatTimestamp(log.timestamp)}
					</div>
				</div>
				<div>
					<div class="flex items-center justify-between mb-1">
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Log ID')}
						</div>
						<button
							class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
							onclick={() => copyToClipboard(log.id)}
						>
							{$i18n.t('Copy')}
						</button>
					</div>
					<div class="text-xs font-mono text-gray-600 dark:text-gray-300 truncate">{log.id}</div>
				</div>
			</div>

			<!-- User section -->
			<div>
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
					{$i18n.t('User')}
				</div>
				<div class="rounded-lg bg-gray-50 dark:bg-gray-850 p-3 grid grid-cols-2 gap-3 text-xs">
					<div>
						<div class="text-gray-400 mb-0.5">{$i18n.t('Email')}</div>
						<div class="text-gray-700 dark:text-gray-300">
							{log.user_email || '—'}
						</div>
					</div>
					<div>
						<div class="flex items-center justify-between mb-0.5">
							<div class="text-gray-400">{$i18n.t('User ID')}</div>
							{#if log.user_id}
								<button
									class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
									onclick={() => copyToClipboard(log.user_id!)}
									aria-label={$i18n.t('Copy')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-3"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</button>
							{/if}
						</div>
						<div class="font-mono text-gray-700 dark:text-gray-300 truncate">
							{log.user_id || '—'}
						</div>
					</div>
					{#if log.session_id}
						<div class="col-span-2">
							<div class="flex items-center justify-between mb-0.5">
								<div class="text-gray-400">{$i18n.t('Session ID')}</div>
								<button
									class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
									onclick={() => copyToClipboard(log.session_id!)}
									aria-label={$i18n.t('Copy')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-3"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</button>
							</div>
							<div class="font-mono text-gray-700 dark:text-gray-300 truncate">
								{log.session_id}
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Request section -->
			<div>
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
					{$i18n.t('Request')}
				</div>
				<div class="rounded-lg bg-gray-50 dark:bg-gray-850 p-3 grid grid-cols-2 gap-3 text-xs">
					{#if log.request_method}
						<div>
							<div class="text-gray-400 mb-0.5">{$i18n.t('Method')}</div>
							<div class="text-gray-700 dark:text-gray-300">
								<span class="font-mono">{log.request_method}</span>
							</div>
						</div>
					{/if}
					{#if log.request_path}
						<div class={log.request_method ? 'col-span-2' : ''}>
							<div class="flex items-center justify-between mb-0.5">
								<div class="text-gray-400">{$i18n.t('Path')}</div>
								<button
									class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
									onclick={() => copyToClipboard(log.request_path!)}
									aria-label={$i18n.t('Copy')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-3"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</button>
							</div>
							<div class="font-mono text-gray-700 dark:text-gray-300 break-all">
								{log.request_path}
							</div>
						</div>
					{/if}
					<div>
						<div class="text-gray-400 mb-0.5">{$i18n.t('IP Address')}</div>
						<div class="font-mono text-gray-700 dark:text-gray-300">
							{log.ip_address || '—'}
						</div>
					</div>
					{#if log.user_agent}
						<div>
							<div class="flex items-center justify-between mb-0.5">
								<div class="text-gray-400">{$i18n.t('User Agent')}</div>
								<button
									class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
									onclick={() => copyToClipboard(log.user_agent!)}
									aria-label={$i18n.t('Copy')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-3"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</button>
							</div>
							<div class="text-gray-700 dark:text-gray-300 break-all">{log.user_agent}</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Resource section -->
			<div>
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
					{$i18n.t('Resource')}
				</div>
				<div class="rounded-lg bg-gray-50 dark:bg-gray-850 p-3 grid grid-cols-2 gap-3 text-xs">
					<div>
						<div class="text-gray-400 mb-0.5">{$i18n.t('Type')}</div>
						<div class="text-gray-700 dark:text-gray-300">{humanize(log.resource_type)}</div>
					</div>
					{#if log.resource_name}
						<div>
							<div class="text-gray-400 mb-0.5">{$i18n.t('Name')}</div>
							<div class="text-gray-700 dark:text-gray-300">{log.resource_name}</div>
						</div>
					{/if}
					{#if log.resource_id}
						<div class={log.resource_name ? 'col-span-2' : ''}>
							<div class="flex items-center justify-between mb-0.5">
								<div class="text-gray-400">{$i18n.t('Resource ID')}</div>
								<button
									class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
									onclick={() => copyToClipboard(log.resource_id!)}
									aria-label={$i18n.t('Copy')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-3"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</button>
							</div>
							<div class="font-mono text-gray-700 dark:text-gray-300 truncate">
								{log.resource_id}
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Audit Details JSON -->
			{#if log.details && Object.keys(log.details).length > 0}
				<div>
					<div class="flex items-center justify-between mb-1">
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
							{$i18n.t('Details')}
						</div>
						<button
							class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
							onclick={() => copyToClipboard(JSON.stringify(log.details, null, 2))}
						>
							{$i18n.t('Copy')}
						</button>
					</div>
					<pre
						class="text-xs font-mono rounded-lg bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 p-3 max-h-64 overflow-auto text-gray-700 dark:text-gray-300"
					>{JSON.stringify(log.details, null, 2)}</pre>
				</div>
			{/if}

			<!-- Footer -->
			<div class="flex justify-end pt-1">
				<button
					class="px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-850 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					onclick={() => (show = false)}
				>
					{$i18n.t('Close')}
				</button>
			</div>
		</div>
	{/if}
</Modal>
