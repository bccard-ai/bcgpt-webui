import { apiClient } from '$lib/apis/client';

export const getGeminiConfig = async (token: string = '') => {
	return apiClient.get('/gemini/config', { token });
};

export const updateGeminiConfig = async (token: string = '', config: object) => {
	return apiClient.post('/gemini/config/update', config, { token });
};

export const verifyGeminiConnection = async (token: string = '') => {
	return apiClient.post('/gemini/verify', undefined, { token });
};

export const getGeminiModels = async (token: string = '') => {
	return apiClient.get('/gemini/models', { token });
};
