<script lang="ts">
	import { preventDefault } from 'svelte/legacy';

	import { toast } from 'svelte-sonner';

	import { onMount, getContext } from 'svelte';

	import { getAgentConfig, updateAgentConfig } from '$lib/apis/agents';
	import { getModels as fetchModels } from '$lib/apis';

	import Switch from '$lib/components/common/Switch.svelte';
	import Selector from '$lib/components/common/Selector.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Select } from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	type Model = {
		id: string;
		name?: string;
	};

	type ModelsResponse = Model[] | { data?: Model[] };

	// Agent System
	let defaultAutonomyLevel = $state('assistant');
	let operatorMaxToolIterations = $state(10);
	let qualityPipelineEnabled = $state(false);
	let qualitySamplingRate = $state(0.1);

	// Workflow Engine
	let workflowEngineEnabled = $state(true);
	let workflowDefaultTimeout = $state(300);
	let workflowNodeTimeout = $state(60);

	// Multi-Agent
	let multiAgentEnabled = $state(false);
	let multiAgentMaxParallel = $state(5);
	let multiAgentDebateRounds = $state(3);
	let multiAgentConsensusThreshold = $state(0.8);

	// Quality Pipeline
	let qualityClaimDecompositionEnabled = $state(false);
	let qualityGroundingEnabled = $state(false);
	let qualityDocGradingEnabled = $state(false);

	// Quality Pipeline Models
	let qualityDefaultModel = $state('');
	let qualityClaimModel = $state('');
	let qualityGroundingModel = $state('');
	let qualityDocGradingModel = $state('');
	let qualityEntailmentModel = $state('');
	let availableModels = $state<{ value: string; label: string }[]>([]);

	// Advanced groups start collapsed unless their feature is already enabled (set on load).
	let multiAgentOpen = $state(false);
	let qualityPipelineOpen = $state(false);

	const submitHandler = async () => {
		try {
			await updateAgentConfig('', {
				default_autonomy_level: defaultAutonomyLevel,
				operator_max_tool_iterations: operatorMaxToolIterations,
				quality_pipeline_enabled: qualityPipelineEnabled,
				quality_sampling_rate: qualitySamplingRate,
				workflow_engine_enabled: workflowEngineEnabled,
				workflow_default_timeout: workflowDefaultTimeout,
				workflow_node_timeout: workflowNodeTimeout,
				multi_agent_enabled: multiAgentEnabled,
				multi_agent_max_parallel: multiAgentMaxParallel,
				multi_agent_debate_rounds: multiAgentDebateRounds,
				multi_agent_consensus_threshold: multiAgentConsensusThreshold,
				quality_claim_decomposition_enabled: qualityClaimDecompositionEnabled,
				quality_grounding_enabled: qualityGroundingEnabled,
				quality_doc_grading_enabled: qualityDocGradingEnabled,
				quality_default_model: qualityDefaultModel,
				quality_claim_model: qualityClaimModel,
				quality_grounding_model: qualityGroundingModel,
				quality_doc_grading_model: qualityDocGradingModel,
				quality_entailment_model: qualityEntailmentModel
			});

			onSave?.();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	onMount(async () => {
		try {
			const config = await getAgentConfig('');
			if (config) {
				defaultAutonomyLevel = config.agent_system?.default_autonomy_level ?? 'assistant';
				operatorMaxToolIterations = config.agent_system?.operator_max_tool_iterations ?? 10;
				qualityPipelineEnabled = config.agent_system?.quality_pipeline_enabled ?? false;
				qualitySamplingRate = config.agent_system?.quality_sampling_rate ?? 0.1;

				workflowEngineEnabled = config.workflow_engine?.enabled ?? true;
				workflowDefaultTimeout = config.workflow_engine?.default_timeout ?? 300;
				workflowNodeTimeout = config.workflow_engine?.node_timeout ?? 60;

				multiAgentEnabled = config.multi_agent?.enabled ?? false;
				multiAgentMaxParallel = config.multi_agent?.max_parallel ?? 5;
				multiAgentDebateRounds = config.multi_agent?.debate_rounds ?? 3;
				multiAgentConsensusThreshold = config.multi_agent?.consensus_threshold ?? 0.8;

				qualityClaimDecompositionEnabled = config.quality?.claim_decomposition_enabled ?? false;
				qualityGroundingEnabled = config.quality?.grounding_enabled ?? false;
				qualityDocGradingEnabled = config.quality?.doc_grading_enabled ?? false;
				qualityDefaultModel = config.quality?.default_model ?? '';
				qualityClaimModel = config.quality?.claim_model ?? '';
				qualityGroundingModel = config.quality?.grounding_model ?? '';
				qualityDocGradingModel = config.quality?.doc_grading_model ?? '';
				qualityEntailmentModel = config.quality?.entailment_model ?? '';

				multiAgentOpen = multiAgentEnabled;
				qualityPipelineOpen = qualityPipelineEnabled;
			}

			// Fetch available models for quality pipeline selectors
			const modelsRes: ModelsResponse | null = await fetchModels('');
			const modelData = Array.isArray(modelsRes) ? modelsRes : (modelsRes?.data ?? []);
			availableModels = [
				{ value: '', label: $i18n.t('Use Default') },
				...modelData.map((m) => ({ value: m.id, label: m.name || m.id }))
			];
		} catch (e) {
			console.warn('Failed to load Agent config:', e);
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	onsubmit={preventDefault(() => {
		submitHandler();
	})}
>
	<div class="space-y-2.5 overflow-y-scroll scrollbar-hidden h-full pr-1.5">
		<div class="mb-2.5">
			<InfoCallout
				>{$i18n.t(
					'Configure agent autonomy, multi-agent orchestration, the workflow engine, and the response quality pipeline, including which models handle each quality-checking step.'
				)}</InfoCallout
			>
		</div>

		<!-- Agent System (Core) -->
		<SettingsSection title={$i18n.t('Agent System (Core)')}>
			<Field class="mb-2.5" label={$i18n.t('Default Autonomy Level')}>
				<Select
					bind:value={defaultAutonomyLevel}
					items={[
						{ value: 'suggest', label: $i18n.t('Suggest') },
						{ value: 'assistant', label: $i18n.t('Assistant') },
						{ value: 'operator', label: $i18n.t('Operator') }
					]}
				/>
			</Field>

			<Field class="mb-2.5" label={$i18n.t('Max Tool Iterations')}>
				<input
					class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					type="number"
					min="1"
					max="50"
					bind:value={operatorMaxToolIterations}
				/>
			</Field>
		</SettingsSection>

		<!-- Workflow Engine -->
		<SettingsSection title={$i18n.t('Workflow Engine')}>
			<Field class="mb-2.5" inline label={$i18n.t('Enable Workflow Engine')}>
				<Switch bind:state={workflowEngineEnabled} />
			</Field>

			{#if workflowEngineEnabled}
				<Field class="mb-2.5" label={$i18n.t('Default Timeout (seconds)')}>
					<input
						class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						type="number"
						min="30"
						max="3600"
						bind:value={workflowDefaultTimeout}
					/>
				</Field>

				<Field class="mb-2.5" label={$i18n.t('Node Timeout (seconds)')}>
					<input
						class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						type="number"
						min="5"
						max="600"
						bind:value={workflowNodeTimeout}
					/>
				</Field>
			{/if}
		</SettingsSection>

		<!-- Multi-Agent Orchestration -->
		<SettingsSection title={$i18n.t('Multi-Agent Orchestration')} bind:open={multiAgentOpen}>
			<Field class="mb-2.5" inline label={$i18n.t('Enable Multi-Agent')}>
				<Switch bind:state={multiAgentEnabled} />
			</Field>

			{#if multiAgentEnabled}
				<Field class="mb-2.5" label={$i18n.t('Max Parallel Agents')}>
					<input
						class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						type="number"
						min="1"
						max="20"
						bind:value={multiAgentMaxParallel}
					/>
				</Field>

				<Field class="mb-2.5" label={$i18n.t('Debate rounds')}>
					<input
						class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						type="number"
						min="1"
						max="10"
						bind:value={multiAgentDebateRounds}
					/>
				</Field>

				<Field class="mb-2.5" label={$i18n.t('Consensus Threshold')}>
					<input
						class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						type="number"
						min="0"
						max="1"
						step="0.1"
						bind:value={multiAgentConsensusThreshold}
					/>
				</Field>
			{/if}
		</SettingsSection>

		<!-- Quality Pipeline -->
		<SettingsSection title={$i18n.t('Quality Pipeline')} bind:open={qualityPipelineOpen}>
			<Field class="mb-2.5" inline label={$i18n.t('Enable Quality Pipeline')}>
				<Switch bind:state={qualityPipelineEnabled} />
			</Field>

			{#if qualityPipelineEnabled}
				<Field class="mb-2.5" label={$i18n.t('Sampling Rate')}>
					<input
						class="flex h-8 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						type="number"
						min="0"
						max="1"
						step="0.05"
						bind:value={qualitySamplingRate}
					/>
				</Field>

				<!-- Quality Checks & Models -->
				<SettingsSection title={$i18n.t('Quality Checks & Models')} open={false}>
					<Field class="mb-2.5" label={$i18n.t('Quality Pipeline Model')}>
						<Selector
							size="sm"
							bind:value={qualityDefaultModel}
							items={availableModels}
							placeholder={$i18n.t('Use Default')}
							searchPlaceholder={$i18n.t('Search models...')}
						/>
					</Field>

					<Field class="mb-2.5" inline label={$i18n.t('Claim Decomposition')}>
						<Switch bind:state={qualityClaimDecompositionEnabled} />
					</Field>

					{#if qualityClaimDecompositionEnabled}
						<Field class="mb-2.5" label={$i18n.t('Claim Decomposition Model')}>
							<Selector
								size="sm"
								bind:value={qualityClaimModel}
								items={availableModels}
								placeholder={$i18n.t('Use Default')}
								searchPlaceholder={$i18n.t('Search models...')}
							/>
						</Field>
					{/if}

					<Field class="mb-2.5" inline label={$i18n.t('Grounding Check')}>
						<Switch bind:state={qualityGroundingEnabled} />
					</Field>

					{#if qualityGroundingEnabled}
						<Field class="mb-2.5" label={$i18n.t('Grounding Model')}>
							<Selector
								size="sm"
								bind:value={qualityGroundingModel}
								items={availableModels}
								placeholder={$i18n.t('Use Default')}
								searchPlaceholder={$i18n.t('Search models...')}
							/>
						</Field>
					{/if}

					<Field class="mb-2.5" inline label={$i18n.t('Document Grading')}>
						<Switch bind:state={qualityDocGradingEnabled} />
					</Field>

					{#if qualityDocGradingEnabled}
						<Field class="mb-2.5" label={$i18n.t('Document Grading Model')}>
							<Selector
								size="sm"
								bind:value={qualityDocGradingModel}
								items={availableModels}
								placeholder={$i18n.t('Use Default')}
								searchPlaceholder={$i18n.t('Search models...')}
							/>
						</Field>
					{/if}

					<Field class="mb-2.5" label={$i18n.t('Entailment Scoring Model')}>
						<Selector
							size="sm"
							bind:value={qualityEntailmentModel}
							items={availableModels}
							placeholder={$i18n.t('Use Default')}
							searchPlaceholder={$i18n.t('Search models...')}
						/>
					</Field>
				</SettingsSection>
			{/if}
		</SettingsSection>
	</div>

	<div class="flex justify-end pt-3">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
