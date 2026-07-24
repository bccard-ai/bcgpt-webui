<script lang="ts">
	import { preventDefault } from 'svelte/legacy';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { resolve } from '$app/paths';

	import { getAuditConfig, updateAuditConfig, purgeAuditLogs } from '$lib/apis/audit';
	import type { AuditConfig } from '$lib/apis/audit';

	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import SettingsSection from './SettingsSection.svelte';

	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';

	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	interface Props {
		saveHandler: () => void;
	}

	let { saveHandler }: Props = $props();

	let config: AuditConfig | null = $state(null);
	let loading = $state(true);
	let showPurgeConfirm = $state(false);
	let purgeResult = $state<{ deleted: number } | null>(null);
	let purgeLoading = $state(false);

	const submitHandler = async () => {
		if (!config) return;
		const res = await updateAuditConfig('', config);
		if (res) {
			saveHandler();
		}
	};

	const confirmPurge = async () => {
		if (!config) return;
		purgeLoading = true;
		try {
			const res = await purgeAuditLogs('', config.audit_retention_days);
			purgeResult = res;
			toast.success($i18n.t('Deleted {{count}} log entries', { count: res.deleted }));
		} catch {
			toast.error($i18n.t('Failed to purge logs'));
		}
		purgeLoading = false;
		showPurgeConfirm = false;
	};

	const cancelPurge = () => {
		showPurgeConfirm = false;
	};

	onMount(async () => {
		const res = await getAuditConfig('');
		if (res) {
			config = res;
		}
		loading = false;
	});
</script>

{#if !loading && config}
	<form
		class="flex flex-col h-full justify-between space-y-3 text-sm"
		onsubmit={preventDefault(submitHandler)}
	>
		<div class="overflow-y-scroll scrollbar-hidden h-full">
			<div class="mb-2.5">
				<InfoCallout
					>{$i18n.t(
						'Configure audit logging level, retention policy, and data capture settings. Changes are applied system-wide.'
					)}</InfoCallout
				>
			</div>

			<!-- Logging -->
			<SettingsSection title={$i18n.t('Logging')}>
				<div
					class="rounded-lg border p-3 {config.audit_log_level === 'NONE'
						? 'border-red-500/50 bg-red-50 dark:border-red-500/30 dark:bg-red-950/20'
						: 'border-green-500/50 bg-green-50 dark:border-green-500/30 dark:bg-green-950/20'}"
				>
					<div class="flex w-full justify-between items-center">
						<div class="flex items-center gap-2">
							<span
								class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium {config.audit_log_level ===
								'NONE'
									? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
									: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'}"
							>
								{config.audit_log_level === 'NONE' ? $i18n.t('Disabled') : $i18n.t('Active')}
							</span>
							{#if config.audit_log_level !== 'NONE'}
								<span class="text-xs text-muted-foreground">
									{config.audit_log_level}
								</span>
							{:else}
								<span class="text-xs text-muted-foreground">
									{$i18n.t('Audit logging is disabled')}
								</span>
							{/if}
						</div>
						<a href={resolve('/admin/audit')} class="text-xs font-medium text-primary underline">
							{$i18n.t('View audit logs')}
						</a>
					</div>
				</div>

				<div class="mt-3">
					<Field
						label={$i18n.t('Audit Logging Level')}
						description={$i18n.t(
							'Controls what information is captured in audit logs. Changes take effect immediately.'
						)}
					>
						<Select
							size="sm"
							bind:value={config.audit_log_level}
							items={[
								{
									value: 'NONE',
									label: `${$i18n.t('NONE')}: ${$i18n.t('Disabled - No audit logging')}`
								},
								{
									value: 'METADATA',
									label: `${$i18n.t('METADATA')}: ${$i18n.t(
										'Metadata - Log HTTP method, path, status, user, IP'
									)}`
								},
								{
									value: 'REQUEST',
									label: `${$i18n.t('REQUEST')}: ${$i18n.t(
										'Request - Metadata + request body capture'
									)}`
								},
								{
									value: 'REQUEST_RESPONSE',
									label: `${$i18n.t('REQUEST_RESPONSE')}: ${$i18n.t(
										'Full - Request + response body capture (highest detail)'
									)}`
								}
							]}
						/>
					</Field>
				</div>
			</SettingsSection>

			<!-- Capture & Storage -->
			<SettingsSection title={$i18n.t('Capture & Storage')} open={false}>
				<!-- Log Retention (native number input: number binding kept native per kit guidance) -->
				<div class="mb-2.5 border-b border-dashed border-border pb-2">
					<Field
						inline
						label={$i18n.t('Log Retention (days)')}
						description={$i18n.t(
							'Automatically delete audit logs older than this many days. Set to 0 for unlimited retention.'
						)}
					>
						<input
							type="number"
							min="0"
							step="1"
							class="flex h-8 w-24 rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors text-right focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							bind:value={config.audit_retention_days}
						/>
					</Field>
					{#if config.audit_retention_days === 0}
						<div
							class="mt-2 rounded px-2 py-1 text-xs font-medium bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300"
						>
							{$i18n.t('Unlimited retention may consume significant disk space over time')}
						</div>
					{/if}
				</div>

				<!-- Max Body Capture Size (native number input: number binding kept native) -->
				<Field
					inline
					separator
					label={$i18n.t('Max Body Capture Size (bytes)')}
					description={$i18n.t('Maximum size of request/response body to capture per log entry')}
				>
					<div class="flex items-center gap-2">
						{#if config.max_body_log_size > 0}
							<span class="text-xs text-muted-foreground">
								{Math.round((config.max_body_log_size / 1024) * 10) / 10} KB
							</span>
						{/if}
						<input
							type="number"
							min="0"
							step="256"
							class="flex h-8 w-24 rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors text-right focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							bind:value={config.max_body_log_size}
						/>
					</div>
				</Field>

				<!-- Excluded API Paths -->
				<Field
					separator
					label={$i18n.t('Excluded API Paths')}
					description={$i18n.t(
						'Comma-separated list of API path prefixes to exclude from audit logging'
					)}
				>
					<Textarea
						rows={3}
						placeholder="chats, chat, folders"
						class="resize-y"
						bind:value={config.audit_excluded_paths}
					/>
				</Field>

				<!-- Log File Rotation Size -->
				<Field
					label={$i18n.t('Log File Rotation Size')}
					description={$i18n.t('Size threshold for audit log file rotation (e.g., 10MB, 50MB)')}
				>
					<Input size="sm" placeholder="10 MB" bind:value={config.audit_log_file_rotation_size} />
				</Field>
			</SettingsSection>

			<!-- Maintenance (danger; destructive purge) -->
			<SettingsSection title={$i18n.t('Maintenance')} danger open={false}>
				<Field
					label={$i18n.t('Purge Expired Logs')}
					description={$i18n.t(
						'Manually trigger deletion of logs older than the configured retention period'
					)}
				>
					<div class="flex items-center gap-3">
						<Button
							variant="outline"
							size="sm"
							type="button"
							class="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
							onclick={() => {
								showPurgeConfirm = true;
							}}>{$i18n.t('Purge Now')}</Button
						>
						{#if purgeResult}
							<span class="text-xs text-muted-foreground">
								{$i18n.t('Deleted {{count}} log entries', { count: purgeResult.deleted })}
							</span>
						{/if}
					</div>
				</Field>
			</SettingsSection>
		</div>

		<div class="flex justify-end pt-3">
			<Button type="submit">{$i18n.t('Save')}</Button>
		</div>
	</form>

	{#if showPurgeConfirm}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
			<div
				class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-5 max-w-md w-full mx-4 border border-red-500/30"
			>
				<div class="flex items-center gap-3 mb-3">
					<h3 class="text-lg font-semibold text-red-600 dark:text-red-400">
						{$i18n.t('Confirm Purge')}
					</h3>
				</div>
				<p class="text-sm text-muted-foreground mb-1">
					{$i18n.t('Are you sure you want to purge audit logs older than {{days}} days?', {
						days: config?.audit_retention_days ?? 90
					})}
				</p>
				<p class="text-sm font-medium text-red-600 dark:text-red-400 mb-5">
					{$i18n.t('This action cannot be undone.')}
				</p>
				<div class="flex justify-end gap-2">
					<Button variant="outline" size="sm" onclick={cancelPurge}>{$i18n.t('Cancel')}</Button>
					<Button variant="destructive" size="sm" onclick={confirmPurge} disabled={purgeLoading}
						>{purgeLoading ? $i18n.t('Purging...') : $i18n.t('Purge')}</Button
					>
				</div>
			</div>
		</div>
	{/if}
{/if}
