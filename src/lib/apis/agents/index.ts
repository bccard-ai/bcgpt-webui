import { agentsClient } from '$lib/apis/client';

export const getAgentConfig = async (token: string) => agentsClient.get('/config', { token });

type AgentConfigForm = {
	default_autonomy_level?: string;
	operator_max_tool_iterations?: number;
	quality_pipeline_enabled?: boolean;
	quality_sampling_rate?: number;
	workflow_engine_enabled?: boolean;
	workflow_default_timeout?: number;
	workflow_node_timeout?: number;
	multi_agent_enabled?: boolean;
	multi_agent_max_parallel?: number;
	multi_agent_debate_rounds?: number;
	multi_agent_consensus_threshold?: number;
	quality_claim_decomposition_enabled?: boolean;
	quality_grounding_enabled?: boolean;
	quality_doc_grading_enabled?: boolean;
	quality_default_model?: string;
	quality_claim_model?: string;
	quality_grounding_model?: string;
	quality_doc_grading_model?: string;
	quality_entailment_model?: string;
};

export const updateAgentConfig = async (token: string, payload: AgentConfigForm) =>
	agentsClient.post('/config/update', payload, { token });
