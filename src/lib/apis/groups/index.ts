import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewGroup = async (token: string, group: object) => {
	return apiClient.post('/groups/create', { ...group }, { token });
};

export const getGroups = async (token: string = '') => {
	return apiClient.get('/groups/', { token });
};

export const getGroupById = async (token: string, id: string) => {
	return apiClient.get(`/groups/id/${id}`, { token });
};

export const updateGroupById = async (token: string, id: string, group: object) => {
	return apiClient.post(`/groups/id/${id}/update`, { ...group }, { token });
};

export const deleteGroupById = async (token: string, id: string) => {
	return apiClient.del(`/groups/id/${id}/delete`, undefined, { token });
};
