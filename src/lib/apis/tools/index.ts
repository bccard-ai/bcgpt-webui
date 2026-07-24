import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewTool = async (token: string, tool: object) =>
	apiClient.post('/tools/create', { ...tool }, { token });

export const getTools = async (token: string = '') => apiClient.get('/tools/', { token });

export const getToolList = async (token: string = '') => apiClient.get('/tools/list', { token });

export const exportTools = async (token: string = '') => apiClient.get('/tools/export', { token });

export const getToolById = async (token: string, id: string) =>
	apiClient.get(`/tools/id/${id}`, { token });

export const updateToolById = async (token: string, id: string, tool: object) =>
	apiClient.post(`/tools/id/${id}/update`, { ...tool }, { token });

export const deleteToolById = async (token: string, id: string) =>
	apiClient.del(`/tools/id/${id}/delete`, undefined, { token });

// ---------------------------------------------------------------------------
// Valves
// ---------------------------------------------------------------------------

export const getToolValvesById = async (token: string, id: string) =>
	apiClient.get(`/tools/id/${id}/valves`, { token });

export const getToolValvesSpecById = async (token: string, id: string) =>
	apiClient.get(`/tools/id/${id}/valves/spec`, { token });

export const updateToolValvesById = async (token: string, id: string, valves: object) =>
	apiClient.post(`/tools/id/${id}/valves/update`, { ...valves }, { token });

// ---------------------------------------------------------------------------
// User valves
// ---------------------------------------------------------------------------

export const getUserValvesById = async (token: string, id: string) =>
	apiClient.get(`/tools/id/${id}/valves/user`, { token });

export const getUserValvesSpecById = async (token: string, id: string) =>
	apiClient.get(`/tools/id/${id}/valves/user/spec`, { token });

export const updateUserValvesById = async (token: string, id: string, valves: object) =>
	apiClient.post(`/tools/id/${id}/valves/user/update`, { ...valves }, { token });
