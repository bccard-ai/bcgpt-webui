<script lang="ts">
	import { preventDefault, createBubbler } from 'svelte/legacy';

	const bubble = createBubbler();
	import { onMount, getContext } from 'svelte';

	import { getSecurityConfig, updateSecurityConfig } from '$lib/apis/security';
	import type { SecurityConfig } from '$lib/apis/security';
	import { getHandoffConfig, updateHandoffConfig } from '$lib/apis/handoff';
	import type { HandoffConfig } from '$lib/apis/handoff';

	import Switch from '$lib/components/common/Switch.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';

	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	interface Props {
		saveHandler: () => void;
	}

	let { saveHandler }: Props = $props();

	let config: SecurityConfig | null = $state(null);
	let handoffConfig: HandoffConfig | null = $state(null);
	let availableModels = $state<{ value: string; label: string }[]>([]);
	let loading = $state(true);
	let showEmergencyConfirm = $state(false);
	let pendingEmergencyState = false;

	const handleEmergencyToggle = (newState: boolean) => {
		if (newState) {
			pendingEmergencyState = true;
			showEmergencyConfirm = true;
		} else {
			if (config) {
				config.emergency_stop = false;
			}
		}
	};

	const confirmEmergencyStop = async () => {
		if (config) {
			config.emergency_stop = pendingEmergencyState;
		}
		showEmergencyConfirm = false;
		await submitHandler();
	};

	const cancelEmergencyStop = () => {
		showEmergencyConfirm = false;
		pendingEmergencyState = false;
	};

	const submitHandler = async () => {
		if (!config) return;
		try {
			const res = await updateSecurityConfig('', config);
			if (res) {
				saveHandler();
			}
		} catch (e) {
			console.error('Failed to save security config:', e);
		}
	};

	const submitHandoffHandler = async () => {
		if (!handoffConfig) return;
		try {
			await updateHandoffConfig('', handoffConfig);
			saveHandler();
		} catch (e) {
			console.error('Failed to save handoff config:', e);
		}
	};

	onMount(async () => {
		const res = await getSecurityConfig('');
		if (res) {
			config = res;
		}
		const hRes = await getHandoffConfig('').catch(() => null);
		if (hRes) {
			handoffConfig = hRes;
		}
		try {
			const { getModels } = await import('$lib/apis');
			const modelsRes = await getModels('');
			const modelList = Array.isArray(modelsRes) ? modelsRes : (modelsRes?.data ?? []);
			availableModels = [
				{ value: '', label: $i18n.t('Use Default') },
				...modelList
					.filter((m: Record<string, string>) => m.id && !m.id.startsWith('arena'))
					.map((m: Record<string, string>) => ({ value: m.id, label: m.name || m.id }))
			];
		} catch {
			// Non-critical: model selector will show empty
		}
		loading = false;
	});
</script>

{#if !loading && config}
	<form
		class="flex flex-col h-full justify-between text-sm"
		onsubmit={preventDefault(submitHandler)}
	>
		<div class="overflow-y-scroll scrollbar-hidden h-full">
			<div class="mb-2.5">
				<InfoCallout
					>{$i18n.t(
						'Configure platform-wide security controls: the emergency stop, content scanning for prompt injection, jailbreak, PII, and toxic content, AI transparency notices, and chat rate limits.'
					)}</InfoCallout
				>
			</div>

			<!-- Emergency Stop — always visible master kill switch -->
			<div
				class="rounded-lg border p-3 mb-2.5 {config.emergency_stop
					? 'border-red-500/50 bg-red-50 dark:border-red-500/30 dark:bg-red-950/20'
					: 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-850'}"
			>
				<div class="flex w-full justify-between items-center">
					<div>
						<div class="flex items-center gap-2">
							<span class="text-lg">🚨</span>
							<span
								class="font-medium {config.emergency_stop ? 'text-red-600 dark:text-red-400' : ''}"
								>{$i18n.t('Emergency Stop')}</span
							>
						</div>
						<div class="text-xs text-muted-foreground mt-1">
							{$i18n.t('When activated, all AI chat services will be immediately suspended.')}
						</div>
					</div>
					<Switch
						bind:state={config.emergency_stop}
						onchange={() => handleEmergencyToggle(config.emergency_stop)}
					/>
				</div>
				{#if config.emergency_stop}
					<div
						class="mt-2 rounded px-2 py-1 text-xs font-medium bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
					>
						{$i18n.t('AI service suspended by administrator')}
					</div>
				{/if}
			</div>

			<!-- Content Scanner — master toggle + basics -->
			<SettingsSection title={$i18n.t('Security Scanner')}>
				<Field
					inline
					separator
					label={$i18n.t('Enable Scanner')}
					description={$i18n.t('Scans chat messages for security threats before processing')}
				>
					<Switch bind:state={config.enabled} />
				</Field>

				{#if config.enabled}
					<Field
						inline
						separator
						class="mt-3"
						label={$i18n.t('Shadow Mode')}
						description={$i18n.t('Log detections without blocking messages')}
					>
						<Switch bind:state={config.shadow_mode} />
					</Field>

					<Field inline separator label={$i18n.t('Detection Logging')}>
						<Switch bind:state={config.log_detections} />
					</Field>
				{/if}
			</SettingsSection>

			{#if config.enabled}
				<!-- Threat Detectors — everyday pattern-based detectors -->
				<SettingsSection title={$i18n.t('Threat Detectors')}>
					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2">
						<Field
							inline
							label={$i18n.t('Prompt Injection Detection')}
							description={$i18n.t(
								'Detects attempts to manipulate AI behavior through injected instructions'
							)}
						>
							<Switch bind:state={config.prompt_injection.enabled} />
						</Field>
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Jailbreak Detection')}
							description={$i18n.t('Detects attempts to bypass AI safety restrictions')}
						>
							<Switch bind:state={config.jailbreak.enabled} />
						</Field>
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('PII Detection')}
							description={$i18n.t('Detects and masks personally identifiable information')}
						>
							<Switch bind:state={config.pii.enabled} />
						</Field>
						{#if config.pii.enabled}
							<Field inline class="pt-1" label={$i18n.t('Mask Mode')}>
								<Select
									class="w-32"
									bind:value={config.pii.mask_mode}
									items={[
										{ value: 'redact', label: $i18n.t('Redact') },
										{ value: 'block', label: $i18n.t('Block') }
									]}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Toxic Content Detection')}
							description={$i18n.t('Detects toxic, profane, or harmful content')}
						>
							<Switch bind:state={config.toxicity.enabled} />
						</Field>
						{#if config.toxicity.enabled}
							<Field class="pt-1" label={$i18n.t('Custom Word List')}>
								<Textarea
									rows={2}
									placeholder={$i18n.t('Comma-separated list of additional words to flag')}
									bind:value={config.toxicity.custom_word_list}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Secret/Credential Detection')}
							description={$i18n.t('Detects API keys, tokens, and other credentials in messages')}
						>
							<Switch bind:state={config.secrets.enabled} />
						</Field>
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Output Content Filtering')}
							description={$i18n.t('Filters LLM responses for sensitive information')}
						>
							<Switch bind:state={config.output_filter.enabled} />
						</Field>
					</div>
				</SettingsSection>

				<!-- AI-Based Detection — model-driven, advanced -->
				<SettingsSection title={$i18n.t('AI-Based Detection')} open={false}>
					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2">
						<Field
							inline
							label={$i18n.t('LLM-based Detection')}
							description={$i18n.t(
								'Uses AI to detect variant attacks, obfuscation, and multilingual bypasses that regex patterns miss'
							)}
						>
							<Switch bind:state={config.llm_scanner.enabled} />
						</Field>
						{#if config.llm_scanner.enabled}
							<Field
								class="mt-2"
								label={$i18n.t('Scanner Model')}
								helper={$i18n.t(
									'Model used for security analysis. Falls back to the default task model if not set.'
								)}
							>
								<Select
									bind:value={config.llm_scanner.model}
									items={[
										{ value: '', label: $i18n.t('Use Default Task Model') },
										...availableModels.filter((m) => m.value !== '')
									]}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Model-Based Guardrail')}
							description={$i18n.t(
								'Uses AI to detect sophisticated prompt injection that regex patterns miss'
							)}
						>
							<Switch bind:state={config.guardrail.enabled} />
						</Field>
						{#if config.guardrail.enabled}
							<Field
								class="mt-2"
								label={$i18n.t('Scanner Model')}
								helper={$i18n.t(
									'Model used for guardrail analysis. Falls back to the default task model if not set.'
								)}
							>
								<Select
									bind:value={config.guardrail.model}
									items={[
										{ value: '', label: $i18n.t('Use Default Task Model') },
										...availableModels.filter((m) => m.value !== '')
									]}
								/>
							</Field>
							<Field inline class="pt-1" label={$i18n.t('Action on Detection')}>
								<Select
									class="w-32"
									bind:value={config.guardrail.action}
									items={[
										{ value: 'block', label: $i18n.t('Block') },
										{ value: 'warn', label: $i18n.t('Warn') },
										{ value: 'log', label: $i18n.t('Log') }
									]}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Canary Token Protection')}
							description={$i18n.t(
								'Injects hidden tokens to detect system prompt leakage in AI responses'
							)}
						>
							<Switch bind:state={config.canary_tokens.enabled} />
						</Field>
						{#if config.canary_tokens.enabled}
							<Field inline class="pt-1" label={$i18n.t('Token Position')}>
								<Select
									class="w-48"
									bind:value={config.canary_tokens.position}
									items={[
										{ value: 'system_prompt_start', label: $i18n.t('System Prompt Start') },
										{ value: 'system_prompt_end', label: $i18n.t('System Prompt End') }
									]}
								/>
							</Field>
						{/if}
					</div>
				</SettingsSection>

				<!-- Scope & Thresholds -->
				<SettingsSection title={$i18n.t('Scope & Thresholds')} open={false}>
					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2">
						<Field
							inline
							label={$i18n.t('Conversation Scanning')}
							description={$i18n.t(
								'Detects multi-turn attacks by analyzing threat signals across the full conversation'
							)}
						>
							<Switch bind:state={config.conversation_scanning_enabled} />
						</Field>
						{#if config.conversation_scanning_enabled}
							<Field
								inline
								class="pt-1"
								label={$i18n.t('Conversation Threat Threshold')}
								description={$i18n.t('Higher threshold = less sensitive (fewer false positives)')}
							>
								<input
									type="number"
									step="0.1"
									min="0.1"
									class="flex h-8 w-24 rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors text-right focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
									bind:value={config.conversation_threshold}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('File Upload Scanning')}
							description={$i18n.t('Scan uploaded file content for security threats')}
						>
							<Switch bind:state={config.scan_file_uploads} />
						</Field>
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Web Search Scanning')}
							description={$i18n.t('Scan web search results before injection into chat')}
						>
							<Switch bind:state={config.scan_web_results} />
						</Field>
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Confidence Threshold')}
							description={$i18n.t('Minimum confidence score for threat detection (0.0-1.0)')}
						>
							<input
								type="number"
								step="0.1"
								min="0.0"
								max="1.0"
								class="flex h-8 w-24 rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors text-right focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								bind:value={config.confidence_threshold}
							/>
						</Field>
						<div class="text-xs text-muted-foreground">
							{$i18n.t('Lower = more sensitive (more false positives)')} | {$i18n.t(
								'Higher = less sensitive (may miss threats)'
							)}
						</div>
					</div>
				</SettingsSection>

				<!-- Integrations -->
				<SettingsSection title={$i18n.t('Integrations')} open={false}>
					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2">
						<Field
							inline
							label={$i18n.t('SIEM Integration')}
							description={$i18n.t('Forward security events to external SIEM/SOAR systems')}
						>
							<Switch bind:state={config.siem_webhook.enabled} />
						</Field>
						{#if config.siem_webhook.enabled}
							<Field class="pt-1" label={$i18n.t('Webhook URL')}>
								<Input
									size="sm"
									type="text"
									placeholder="https://siem.example.com/api/events"
									bind:value={config.siem_webhook.url}
								/>
							</Field>
							<Field class="pt-1" label={$i18n.t('Custom Headers')}>
								<Textarea
									rows={2}
									placeholder={'{"Authorization": "Bearer token", "X-SIEM-Key": "value"}'}
									bind:value={config.siem_webhook.headers}
								/>
							</Field>
						{/if}
					</div>
				</SettingsSection>
			{/if}

			<!-- AI Transparency -->
			<SettingsSection title={$i18n.t('AI Transparency')} open={false}>
				<Field
					inline
					separator
					label={$i18n.t('Enable AI Transparency')}
					description={$i18n.t('Displays AI transparency notices as required by AI Basic Act §31')}
				>
					<Switch bind:state={config.ai_transparency_enabled} />
				</Field>

				{#if config.ai_transparency_enabled}
					<Field class="mt-3" label={$i18n.t('Notification Title')}>
						<Input
							size="sm"
							type="text"
							placeholder={$i18n.t('AI Assistant Notice')}
							bind:value={config.ai_notification_title}
						/>
					</Field>

					<Field class="mt-2" label={$i18n.t('Notification Message')}>
						<Textarea
							rows={3}
							placeholder={$i18n.t('This service uses generative AI.')}
							bind:value={config.ai_notification_message}
						/>
					</Field>

					<Field class="mt-2" label={$i18n.t('Response Label')}>
						<Input
							size="sm"
							type="text"
							placeholder={$i18n.t('AI-generated response')}
							bind:value={config.ai_response_label}
						/>
					</Field>

					<Field class="mt-2" label={$i18n.t('Disclaimer Text')}>
						<Textarea
							rows={2}
							placeholder={$i18n.t(
								'AI responses are for reference only. For final confirmation of financial transactions, please contact a representative.'
							)}
							bind:value={config.ai_disclaimer_text}
						/>
					</Field>
				{/if}
			</SettingsSection>

			<!-- Chat Rate Limiting -->
			<SettingsSection title={$i18n.t('Chat Rate Limiting')} open={false}>
				<Field
					inline
					separator
					label={$i18n.t('Enable Rate Limiting')}
					description={$i18n.t('Limits chat requests per user to prevent abuse')}
				>
					<Switch bind:state={config.rate_limit_chat_enabled} />
				</Field>

				{#if config.rate_limit_chat_enabled}
					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-3 mt-3">
						<Field label={$i18n.t('Requests per minute')}>
							<input
								type="number"
								min="1"
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								bind:value={config.rate_limit_chat_per_minute}
							/>
						</Field>

						<Field label={$i18n.t('Requests per hour')}>
							<input
								type="number"
								min="1"
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								bind:value={config.rate_limit_chat_per_hour}
							/>
						</Field>

						<Field label={$i18n.t('Requests per day')}>
							<input
								type="number"
								min="1"
								class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								bind:value={config.rate_limit_chat_per_day}
							/>
						</Field>
					</div>
				{/if}
			</SettingsSection>
		</div>

		<div class="flex justify-end pt-3">
			<Button type="submit">{$i18n.t('Save')}</Button>
		</div>
	</form>

	{#if showEmergencyConfirm}
		<div
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
			onself={bubble('self')}
		>
			<div
				class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-5 max-w-md w-full mx-4 border border-red-500/30"
			>
				<div class="flex items-center gap-3 mb-3">
					<span class="text-2xl">🚨</span>
					<h3 class="text-lg font-semibold text-red-600 dark:text-red-400">
						{$i18n.t('Confirm Emergency Stop')}
					</h3>
				</div>
				<p class="text-sm text-gray-600 dark:text-gray-300 mb-1">
					{$i18n.t('Are you sure you want to activate emergency stop?')}
				</p>
				<p class="text-sm font-medium text-red-600 dark:text-red-400 mb-5">
					{$i18n.t('All AI services will be immediately suspended.')}
				</p>
				<div class="flex justify-end gap-2">
					<Button variant="outline" onclick={cancelEmergencyStop}>{$i18n.t('Cancel')}</Button>
					<Button variant="destructive" onclick={confirmEmergencyStop}>{$i18n.t('Activate')}</Button
					>
				</div>
			</div>
		</div>
	{/if}

	{#if handoffConfig}
		<!-- Human Handoff — saved separately from the controls above -->
		<div class="mt-2.5">
			<SettingsSection title={$i18n.t('Handoff Settings')} open={false}>
				<Field
					inline
					separator
					label={$i18n.t('Enable Handoff')}
					description={$i18n.t(
						'Enable users to request human agent assistance for regulatory compliance'
					)}
				>
					<Switch bind:state={handoffConfig.enabled} />
				</Field>

				{#if handoffConfig.enabled}
					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-3">
						<Field
							inline
							label={$i18n.t('Email Notification')}
							description={$i18n.t('Send email when a new handoff request is created')}
						>
							<Switch bind:state={handoffConfig.email_enabled} />
						</Field>
						{#if handoffConfig.email_enabled}
							<Field class="pt-1" label={$i18n.t('Email Recipients')}>
								<Textarea
									rows={2}
									placeholder="[&quot;admin@example.com&quot;]"
									bind:value={handoffConfig.email_recipients}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 space-y-2 mt-2">
						<Field
							inline
							label={$i18n.t('Webhook Notification')}
							description={$i18n.t('Send webhook when a new handoff request is created')}
						>
							<Switch bind:state={handoffConfig.webhook_enabled} />
						</Field>
						{#if handoffConfig.webhook_enabled}
							<Field class="pt-1" label={$i18n.t('Webhook URL')}>
								<Input
									size="sm"
									type="text"
									placeholder="https://hooks.example.com/handoff"
									bind:value={handoffConfig.webhook_url}
								/>
							</Field>
						{/if}
					</div>

					<div class="py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-850 mt-2">
						<Field
							inline
							label={$i18n.t('WebSocket Notification')}
							description={$i18n.t('Automatically sends real-time notifications via WebSocket')}
						>
							<span class="text-xs text-muted-foreground">{$i18n.t('Always on')}</span>
						</Field>
					</div>

					<div class="flex justify-end mt-3">
						<Button onclick={submitHandoffHandler}>{$i18n.t('Save')}</Button>
					</div>
				{/if}
			</SettingsSection>
		</div>
	{/if}
{/if}
