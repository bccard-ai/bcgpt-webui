import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AccessControlValue = null | {
	read: { group_ids: string[]; user_ids: string[] };
	write: { group_ids: string[]; user_ids: string[] };
};

export interface KnowledgeBaseFile {
	id: string | null;
	name?: string;
	size?: number;
	status?: string;
	url?: string;
	type?: string;
	file?: string;
	error?: string;
	itemId?: string;
	meta?: { name?: string; size?: number };
	[key: string]: unknown;
}

export interface KnowledgeBase {
	id: string;
	name: string;
	description: string;
	data: { file_ids: string[] } | null;
	files: KnowledgeBaseFile[];
	access_control: AccessControlValue;
	user_id?: string;
	updated_at?: number;
	created_at?: number;
	[key: string]: unknown;
}

export interface ReprocessWarnings {
	message: string;
	errors: string[];
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewKnowledge = async (
	token: string,
	name: string,
	description: string,
	accessControl: AccessControlValue
): Promise<KnowledgeBase> => {
	return apiClient.post(
		'/knowledge/create',
		{ name, description, access_control: accessControl },
		{ token }
	);
};

export const getKnowledgeBases = async (token: string = ''): Promise<KnowledgeBase[]> => {
	return apiClient.get('/knowledge/', { token });
};

export const getKnowledgeBaseList = async (token: string = ''): Promise<KnowledgeBase[]> => {
	return apiClient.get('/knowledge/list', { token });
};

export const getKnowledgeById = async (token: string, id: string): Promise<KnowledgeBase> => {
	return apiClient.get(`/knowledge/${id}`, { token });
};

type KnowledgeUpdateForm = {
	name?: string;
	description?: string;
	data?: object;
	access_control?: AccessControlValue;
};

export const updateKnowledgeById = async (
	token: string,
	id: string,
	form: KnowledgeUpdateForm
): Promise<KnowledgeBase> => {
	return apiClient.post(
		`/knowledge/${id}/update`,
		{
			name: form?.name || undefined,
			description: form?.description || undefined,
			data: form?.data || undefined,
			access_control: form.access_control
		},
		{ token }
	);
};

// ---------------------------------------------------------------------------
// File operations
// ---------------------------------------------------------------------------

export const addFileToKnowledgeById = async (
	token: string,
	id: string,
	fileId: string
): Promise<KnowledgeBase> => {
	return apiClient.post(`/knowledge/${id}/file/add`, { file_id: fileId }, { token });
};

export const updateFileFromKnowledgeById = async (
	token: string,
	id: string,
	fileId: string
): Promise<KnowledgeBase> => {
	return apiClient.post(`/knowledge/${id}/file/update`, { file_id: fileId }, { token });
};

export const removeFileFromKnowledgeById = async (
	token: string,
	id: string,
	fileId: string
): Promise<KnowledgeBase> => {
	return apiClient.post(`/knowledge/${id}/file/remove`, { file_id: fileId }, { token });
};

export const resetKnowledgeById = async (token: string, id: string): Promise<KnowledgeBase> => {
	return apiClient.post(`/knowledge/${id}/reset`, undefined, { token });
};

export const reprocessKnowledgeById = async (
	token: string,
	id: string
): Promise<KnowledgeBase & { warnings?: ReprocessWarnings }> => {
	return apiClient.post(`/knowledge/${id}/reprocess`, undefined, { token });
};

export const deleteKnowledgeById = async (token: string, id: string) => {
	return apiClient.del(`/knowledge/${id}/delete`, undefined, { token });
};
