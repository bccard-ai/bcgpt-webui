import { apiClient } from '$lib/apis/client';

export const getModels = async (token: string = '') => apiClient.get('/models/', { token });

export const getBaseModels = async (token: string = '') => apiClient.get('/models/base', { token });

export const createNewModel = async (token: string, model: object) =>
	apiClient.post('/models/create', model, { token });

export const getModelById = async (token: string, id: string) => {
	const searchParams = new URLSearchParams();
	searchParams.append('id', id);
	return apiClient.get(`/models/model?${searchParams.toString()}`, { token });
};

export const toggleModelById = async (token: string, id: string) => {
	const searchParams = new URLSearchParams();
	searchParams.append('id', id);
	return apiClient.post(`/models/model/toggle?${searchParams.toString()}`, undefined, { token });
};

export const updateModelById = async (token: string, id: string, model: object) => {
	const searchParams = new URLSearchParams();
	searchParams.append('id', id);
	return apiClient.post(`/models/model/update?${searchParams.toString()}`, model, { token });
};

export const deleteModelById = async (token: string, id: string) => {
	const searchParams = new URLSearchParams();
	searchParams.append('id', id);
	return apiClient.del(`/models/model/delete?${searchParams.toString()}`, undefined, { token });
};

export const deleteAllModels = async (token: string) =>
	apiClient.del('/models/delete/all', undefined, { token });
