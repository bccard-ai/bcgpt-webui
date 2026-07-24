import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewFunction = async (token: string, func: object) =>
	apiClient.post('/functions/create', { ...func }, { token });

export const getFunctions = async (token: string = '') => apiClient.get('/functions/', { token });

export const exportFunctions = async (token: string = '') =>
	apiClient.get('/functions/export', { token });

export const getFunctionById = async (token: string, id: string) =>
	apiClient.get(`/functions/id/${id}`, { token });

export const updateFunctionById = async (token: string, id: string, func: object) =>
	apiClient.post(`/functions/id/${id}/update`, { ...func }, { token });

export const deleteFunctionById = async (token: string, id: string) =>
	apiClient.del(`/functions/id/${id}/delete`, undefined, { token });

// ---------------------------------------------------------------------------
// Toggle
// ---------------------------------------------------------------------------

export const toggleFunctionById = async (token: string, id: string) =>
	apiClient.post(`/functions/id/${id}/toggle`, undefined, { token });

export const toggleGlobalById = async (token: string, id: string) =>
	apiClient.post(`/functions/id/${id}/toggle/global`, undefined, { token });

// ---------------------------------------------------------------------------
// Valves
// ---------------------------------------------------------------------------

export const getFunctionValvesById = async (token: string, id: string) =>
	apiClient.get(`/functions/id/${id}/valves`, { token });

export const getFunctionValvesSpecById = async (token: string, id: string) =>
	apiClient.get(`/functions/id/${id}/valves/spec`, { token });

export const updateFunctionValvesById = async (token: string, id: string, valves: object) =>
	apiClient.post(`/functions/id/${id}/valves/update`, { ...valves }, { token });

// ---------------------------------------------------------------------------
// User valves
// ---------------------------------------------------------------------------

export const getUserValvesById = async (token: string, id: string) =>
	apiClient.get(`/functions/id/${id}/valves/user`, { token });

export const getUserValvesSpecById = async (token: string, id: string) =>
	apiClient.get(`/functions/id/${id}/valves/user/spec`, { token });

export const updateUserValvesById = async (token: string, id: string, valves: object) =>
	apiClient.post(`/functions/id/${id}/valves/user/update`, { ...valves }, { token });
