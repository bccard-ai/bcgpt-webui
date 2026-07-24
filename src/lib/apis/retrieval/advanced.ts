import { retrievalClient } from '$lib/apis/client';

export interface ContextualRetrievalConfig {
	enabled: boolean;
	model: string;
	max_context_tokens: number;
	batch_size: number;
}

export interface CrossEncoderConfig {
	enabled: boolean;
	model: string;
	max_length: number;
	top_k: number;
}

export interface GraphConfig {
	enabled: boolean;
	entity_extraction_model: string;
	max_entities: number;
	max_relations: number;
	community_detection_enabled: boolean;
	max_hops: number;
}

export interface EvaluationConfig {
	enabled: boolean;
	model: string;
	metrics: string;
	log_results: boolean;
}

export interface AdvancedRAGConfig {
	status: boolean;
	contextual_retrieval: ContextualRetrievalConfig;
	cross_encoder: CrossEncoderConfig;
	graph: GraphConfig;
	evaluation: EvaluationConfig;
}

export const getAdvancedRAGConfig = async (token: string): Promise<AdvancedRAGConfig | null> => {
	return retrievalClient.get('/advanced/config', { token });
};

export const updateAdvancedRAGConfig = async (
	token: string,
	payload: Omit<AdvancedRAGConfig, 'status'>
): Promise<AdvancedRAGConfig | null> => {
	return retrievalClient.post('/advanced/config/update', payload, { token });
};
