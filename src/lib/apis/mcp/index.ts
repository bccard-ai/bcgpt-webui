import { apiClient } from '$lib/apis/client';
import { writable } from 'svelte/store';

// ---------------------------------------------------------------------------
// MCP API client — mirrors bcgpt.routers.mcp (mounted /api/v1/mcp) + configs.
// ---------------------------------------------------------------------------

export interface McpServer {
	id: string;
	name: string;
	url: string;
	token?: string;
	enabled: boolean;
	allow_user_override?: boolean;
	builtin_name?: string;
}

export interface McpTool {
	name: string;
	description?: string;
	inputSchema: Record<string, unknown>;
}

export const mcpServers = writable<McpServer[] | null>(null);

/** Effective servers for the current user (admin catalog ∪ user-registered). */
export const getEffectiveMcpServers = async (token: string) =>
	apiClient.get<{ servers: McpServer[] }>('/mcp/servers', { token }).then((r) => r.servers ?? []);

export const getMcpServerTools = async (token: string, id: string) =>
	apiClient
		.get<{ tools: McpTool[] }>(`/mcp/servers/${encodeURIComponent(id)}/tools`, { token })
		.then((r) => r.tools ?? []);

export const testMcpServer = async (token: string, id: string) =>
	apiClient.post<{ ok: boolean; error?: string }>(
		`/mcp/servers/${encodeURIComponent(id)}/test`,
		undefined,
		{ token }
	);

export const createMcpServer = async (token: string, s: McpServer) =>
	apiClient.post<{ servers: McpServer[] }>('/mcp/servers', { ...s }, { token });

export const deleteMcpServer = async (token: string, id: string) =>
	apiClient.del<{ servers: McpServer[] }>(`/mcp/servers/${encodeURIComponent(id)}`, { token });
