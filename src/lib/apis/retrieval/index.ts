import { retrievalClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export const getRAGConfig = async (token: string) => {
	return retrievalClient.get('/config', { token });
};

type ChunkConfigForm = {
	chunk_size: number;
	chunk_overlap: number;
};

type DocumentIntelligenceConfigForm = {
	key: string;
	endpoint: string;
};

type ContentExtractConfigForm = {
	engine: string;
	tika_server_url: string | null;
	document_intelligence_config: DocumentIntelligenceConfigForm | null;
};

type YoutubeConfigForm = {
	language: string[];
	translation?: string | null;
	proxy_url: string;
};

type RAGConfigForm = {
	pdf_extract_images?: boolean;
	enable_google_drive_integration?: boolean;
	enable_onedrive_integration?: boolean;
	chunk?: ChunkConfigForm;
	content_extraction?: ContentExtractConfigForm;
	web_loader_ssl_verification?: boolean;
	youtube?: YoutubeConfigForm;
	qdrant_url?: string;
	qdrant_api_key?: string;
	cleansing_enabled?: boolean;
	cleansing_model?: string;
	summary_enabled?: boolean;
	summary_model?: string;
	embedding_model?: string;
};

export const updateRAGConfig = async (token: string, payload: RAGConfigForm) => {
	return retrievalClient.post('/config/update', { ...payload }, { token });
};

export const getRAGTemplate = async (token: string) => {
	const res = await retrievalClient.get<{ template?: string }>('/template', { token });
	return res?.template ?? '';
};

// ---------------------------------------------------------------------------
// Query settings
// ---------------------------------------------------------------------------

type QuerySettings = {
	k: number | null;
	r: number | null;
	template: string | null;
	hybrid: boolean | null;
	k_reranker: number | null;
};

export const getQuerySettings = async (token: string) => {
	return retrievalClient.get('/query/settings', { token });
};

export const updateQuerySettings = async (token: string, settings: QuerySettings) => {
	return retrievalClient.post('/query/settings/update', { ...settings }, { token });
};

// ---------------------------------------------------------------------------
// Embedding & reranking
// ---------------------------------------------------------------------------

export const getEmbeddingConfig = async (token: string) => {
	return retrievalClient.get('/embedding', { token });
};

type OpenAIConfigForm = {
	key: string;
	url: string;
};

type EmbeddingModelUpdateForm = {
	openai_config?: OpenAIConfigForm;
	embedding_engine: string;
	embedding_model: string;
	embedding_batch_size?: number;
};

export const updateEmbeddingConfig = async (token: string, payload: EmbeddingModelUpdateForm) => {
	return retrievalClient.post('/embedding/update', { ...payload }, { token });
};

export const getRerankingConfig = async (token: string) => {
	return retrievalClient.get('/reranking', { token });
};

type RerankingModelUpdateForm = {
	reranking_model: string;
};

export const updateRerankingConfig = async (token: string, payload: RerankingModelUpdateForm) => {
	return retrievalClient.post('/reranking/update', { ...payload }, { token });
};

// ---------------------------------------------------------------------------
// Processing
// ---------------------------------------------------------------------------

export interface SearchDocument {
	status: boolean;
	collection_name: string;
	filenames: string[];
}

export const processFile = async (
	token: string,
	file_id: string,
	collection_name: string | null = null
) => {
	return retrievalClient.post(
		'/process/file',
		{ file_id, collection_name: collection_name || undefined },
		{ token }
	);
};

export const processYoutubeVideo = async (token: string, url: string) => {
	return retrievalClient.post('/process/youtube', { url }, { token });
};

export const processWeb = async (token: string, collection_name: string, url: string) => {
	return retrievalClient.post('/process/web', { url, collection_name }, { token });
};

export const processWebSearch = async (
	token: string,
	query: string,
	collection_name?: string
): Promise<SearchDocument | null> => {
	return retrievalClient.post(
		'/process/web/search',
		{ query, collection_name: collection_name ?? '' },
		{ token }
	);
};

// ---------------------------------------------------------------------------
// Querying
// ---------------------------------------------------------------------------

export const queryDoc = async (
	token: string,
	collection_name: string,
	query: string,
	k: number | null = null
) => {
	return retrievalClient.post('/query/doc', { collection_name, query, k }, { token });
};

export const queryCollection = async (
	token: string,
	collection_names: string,
	query: string,
	k: number | null = null
) => {
	return retrievalClient.post('/query/collection', { collection_names, query, k }, { token });
};

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

export const resetUploadDir = async (token: string) => {
	return retrievalClient.post('/reset/uploads', undefined, { token });
};

export const resetVectorDB = async (token: string) => {
	return retrievalClient.post('/reset/db', undefined, { token });
};

// ---------------------------------------------------------------------------
// Vector DB management
// ---------------------------------------------------------------------------

export interface CollectionInfo {
	name: string;
	document_count: number;
	vector_count?: number;
}

export interface VectorDBStatus {
	backend: string;
	connected: boolean;
	collections: CollectionInfo[];
	embedding_engine?: string;
	embedding_model?: string;
	total_vectors?: number;
	cluster_status?: string | null;
	embedding_loaded?: boolean;
}

export const getVectorDBStatus = async (token: string): Promise<VectorDBStatus | null> => {
	return retrievalClient.get('/db/status', { token });
};

export const deleteVectorDBCollection = async (token: string, collectionName: string) => {
	return retrievalClient.del(`/db/collections/${encodeURIComponent(collectionName)}`, undefined, {
		token
	});
};

export const createVectorDBCollection = async (token: string, name: string) => {
	return retrievalClient.post('/db/collections', { name }, { token });
};

export const getVectorDBCollections = async (token: string): Promise<CollectionInfo[] | null> => {
	return retrievalClient.get('/db/collections', { token });
};

export interface CollectionPoint {
	id: string;
	text: string;
	metadata: Record<string, unknown>;
	score?: number | null;
}

export interface CollectionPointsPage {
	points: CollectionPoint[];
	next_offset: string | null;
	limit: number;
}

export interface CollectionDetail {
	name: string;
	points_count: number | null;
	dimension: number | null;
	distance: string | null;
	status: string | null;
}

export const getVectorDBCollectionInfo = async (
	token: string,
	collectionName: string
): Promise<CollectionDetail | null> => {
	return retrievalClient.get(`/db/collections/${encodeURIComponent(collectionName)}/info`, {
		token
	});
};

export const getVectorDBCollectionPoints = async (
	token: string,
	collectionName: string,
	limit: number = 50,
	offset: string | null = null
): Promise<CollectionPointsPage | null> => {
	const params = new URLSearchParams({ limit: `${limit}` });
	if (offset) params.set('offset', offset);
	return retrievalClient.get(
		`/db/collections/${encodeURIComponent(collectionName)}/points?${params.toString()}`,
		{ token }
	);
};

export const searchVectorDBCollection = async (
	token: string,
	collectionName: string,
	query: string,
	limit: number = 20
): Promise<{ points: CollectionPoint[] } | null> => {
	return retrievalClient.post(
		`/db/collections/${encodeURIComponent(collectionName)}/search`,
		{ query, limit },
		{ token }
	);
};

export const deleteVectorDBCollectionPoint = async (
	token: string,
	collectionName: string,
	pointId: string
) => {
	return retrievalClient.del(
		`/db/collections/${encodeURIComponent(collectionName)}/points/${encodeURIComponent(pointId)}`,
		undefined,
		{ token }
	);
};
