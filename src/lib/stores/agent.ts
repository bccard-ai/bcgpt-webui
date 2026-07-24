import { writable } from 'svelte/store';

export type AgentAutonomyLevel = 'suggest' | 'assistant' | 'operator';

export interface AutonomyLevelOption {
	value: AgentAutonomyLevel;
	label: string;
	description: string;
}

// 3-Tier agent autonomy (Open-MoAI architecture).
export const agentAutonomyLevels = writable<AutonomyLevelOption[]>([
	{
		value: 'suggest',
		label: 'Suggest',
		description: 'Fast suggestion — no tools, no pre-search.'
	},
	{
		value: 'assistant',
		label: 'Assistant',
		description: 'Default — pre-search (RAG + Web) → merge → LLM → response.'
	},
	{
		value: 'operator',
		label: 'Operator',
		description: 'Autonomous ReAct tool loop (explicit opt-in; may increase cost).'
	}
]);

export const DEFAULT_AUTONOMY_LEVEL: AgentAutonomyLevel = 'assistant';

// Workflow node-type palette (for a future visual workflow editor).
export const workflowNodeTypes = writable([
	{ value: 'user_input', label: 'User Input', color: '#3B82F6' },
	{ value: 'rag_search', label: 'RAG Search', color: '#10B981' },
	{ value: 'web_search', label: 'Web Search', color: '#F59E0B' },
	{ value: 'context_merge', label: 'Context Merge', color: '#8B5CF6' },
	{ value: 'conditional', label: 'Conditional', color: '#EF4444' },
	{ value: 'llm_call', label: 'LLM Call', color: '#06B6D4' },
	{ value: 'api_call', label: 'API Call', color: '#EC4899' },
	{ value: 'text_processor', label: 'Text Processor', color: '#F97316' },
	{ value: 'pii_processor', label: 'PII Processor', color: '#DC2626' },
	{ value: 'response', label: 'Response', color: '#6366F1' }
]);
