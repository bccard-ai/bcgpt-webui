import { apiClient } from '$lib/apis/client';

export const getPipelines = async (token: string = '') =>
	apiClient.get('/agent-pipelines/', { token });

export const createNewPipeline = async (token: string, pipeline: object) =>
	apiClient.post('/agent-pipelines/create', { ...pipeline }, { token });

export const getPipelineById = async (token: string, id: string) =>
	apiClient.get(`/agent-pipelines/id/${id}`, { token });

export const updatePipelineById = async (token: string, id: string, pipeline: object) =>
	apiClient.post(`/agent-pipelines/id/${id}/update`, { ...pipeline }, { token });

export const togglePipelineById = async (token: string, id: string) =>
	apiClient.post(`/agent-pipelines/id/${id}/toggle`, undefined, { token });

export const deletePipelineById = async (token: string, id: string) =>
	apiClient.del(`/agent-pipelines/id/${id}/delete`, undefined, { token });

export const runPipeline = async (token: string, id: string, input: string) =>
	apiClient.post(`/agent-pipelines/id/${id}/run`, { input }, { token });

export const getPipelineBlockValvesSpec = async (token: string, id: string, blockId: string) =>
	apiClient.get(`/agent-pipelines/id/${id}/blocks/${blockId}/valves/spec`, { token });
