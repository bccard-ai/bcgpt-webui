import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type FolderItems = {
	chat_ids: string[];
	file_ids: string[];
};

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewFolder = async (token: string, name: string) => {
	return apiClient.post('/folders/', { name }, { token });
};

export const getFolders = async (token: string = '') => {
	return apiClient.get('/folders/', { token });
};

export const getFolderById = async (token: string, id: string) => {
	return apiClient.get(`/folders/${id}`, { token });
};

// ---------------------------------------------------------------------------
// Updates
// ---------------------------------------------------------------------------

export const updateFolderNameById = async (token: string, id: string, name: string) => {
	return apiClient.post(`/folders/${id}/update`, { name }, { token });
};

export const updateFolderIsExpandedById = async (
	token: string,
	id: string,
	isExpanded: boolean
) => {
	return apiClient.post(`/folders/${id}/update/expanded`, { is_expanded: isExpanded }, { token });
};

export const updateFolderParentIdById = async (token: string, id: string, parentId?: string) => {
	return apiClient.post(`/folders/${id}/update/parent`, { parent_id: parentId }, { token });
};

export const updateFolderItemsById = async (token: string, id: string, items: FolderItems) => {
	return apiClient.post(`/folders/${id}/update/items`, { items }, { token });
};

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------

export const deleteFolderById = async (token: string, id: string) => {
	return apiClient.del(`/folders/${id}`, undefined, { token });
};
