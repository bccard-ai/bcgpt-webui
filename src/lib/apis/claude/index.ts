import { apiClient } from '$lib/apis/client';

export const getClaudeConfig = async (token: string = '') => {
	return apiClient.get('/claude/config', { token });
};

export const updateClaudeConfig = async (token: string = '', config: object) => {
	return apiClient.post('/claude/config/update', config, { token });
};

export const verifyClaudeConnection = async (token: string = '') => {
	return apiClient.post('/claude/verify', undefined, { token });
};

export const getClaudeModels = async (token: string = '') => {
	return apiClient.get('/claude/models', { token });
};
