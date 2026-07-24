import { apiClient } from '$lib/apis/client';
import type { Banner } from '$lib/types';

// ---------------------------------------------------------------------------
// Import/export
// ---------------------------------------------------------------------------

export const importConfig = async (token: string, config: object) => {
	return apiClient.post('/configs/import', { config }, { token });
};

export const exportConfig = async (token: string) => {
	return apiClient.get('/configs/export', { token });
};

// ---------------------------------------------------------------------------
// Connection config
// ---------------------------------------------------------------------------

export const getDirectConnectionsConfig = async (token: string) => {
	return apiClient.get('/configs/direct_connections', { token });
};

export const setDirectConnectionsConfig = async (token: string, config: object) => {
	return apiClient.post('/configs/direct_connections', config, { token });
};

// ---------------------------------------------------------------------------
// MCP servers config (admin)
// ---------------------------------------------------------------------------

export interface McpServersConfig {
	ENABLE_MCP_SERVERS: boolean;
	MCP_SERVERS: Record<string, unknown>[];
	MCP_ALLOWED_HOSTS: string[];
	MCP_BUILTINS_ENABLED: string[];
}

export const getMcpServersConfig = async (token: string) =>
	apiClient.get<McpServersConfig>('/configs/mcp_servers', { token });

export const setMcpServersConfig = async (token: string, config: McpServersConfig) =>
	apiClient.post<McpServersConfig>('/configs/mcp_servers', { ...config }, { token });

// ---------------------------------------------------------------------------
// Models config
// ---------------------------------------------------------------------------

export const getModelsConfig = async (token: string) => {
	return apiClient.get('/configs/models', { token });
};

export const setModelsConfig = async (token: string, config: object) => {
	return apiClient.post('/configs/models', config, { token });
};

// ---------------------------------------------------------------------------
// Suggestions & banners
// ---------------------------------------------------------------------------

export const setDefaultPromptSuggestions = async (token: string, promptSuggestions: string) => {
	return apiClient.post('/configs/suggestions', { suggestions: promptSuggestions }, { token });
};

export const getBanners = async (token: string): Promise<Banner[]> => {
	return apiClient.get('/configs/banners', { token });
};

export const setBanners = async (token: string, banners: Banner[]) => {
	return apiClient.post('/configs/banners', { banners }, { token });
};
