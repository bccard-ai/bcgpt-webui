import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const getMemories = async (token: string) => {
	return apiClient.get('/memories/', { token });
};

export const addNewMemory = async (token: string, content: string) => {
	return apiClient.post('/memories/add', { content }, { token });
};

export const updateMemoryById = async (token: string, id: string, content: string) => {
	return apiClient.post(`/memories/${id}/update`, { content }, { token });
};

export const queryMemory = async (token: string, content: string) => {
	return apiClient.post('/memories/query', { content }, { token });
};

export const deleteMemoryById = async (token: string, id: string) => {
	return apiClient.del(`/memories/${id}`, undefined, { token });
};

export const deleteMemoriesByUserId = async (token: string) => {
	return apiClient.del('/memories/delete/user', undefined, { token });
};
