import { apiClient } from '$lib/apis/client';

export interface HandoffRequest {
	id: string;
	chat_id: string;
	message_id: string;
	user_id: string;
	reason?: string;
	status: 'pending' | 'accepted' | 'resolved' | 'dismissed';
	assigned_to?: string;
	chat_snapshot?: Record<string, unknown>;
	created_at: number;
	updated_at?: number;
	resolved_at?: number;
	metadata?: Record<string, unknown>;
}

export interface HandoffConfig {
	enabled: boolean;
	email_enabled: boolean;
	email_recipients: string;
	webhook_enabled: boolean;
	webhook_url: string;
}

export const createHandoffRequest = async (
	token: string,
	chatId: string,
	messageId: string,
	reason?: string,
	chatSnapshot?: Record<string, unknown>
): Promise<HandoffRequest> =>
	apiClient.post(
		'/handoff',
		{
			chat_id: chatId,
			message_id: messageId,
			reason: reason || null,
			chat_snapshot: chatSnapshot || null
		},
		{ token }
	);

export const getHandoffRequests = async (
	token: string,
	limit?: number,
	offset?: number
): Promise<HandoffRequest[]> => {
	const params = new URLSearchParams();
	if (limit) params.set('limit', String(limit));
	if (offset) params.set('offset', String(offset));
	const query = params.toString() ? `?${params.toString()}` : '';
	return apiClient.get(`/handoff${query}`, { token });
};

export const getPendingHandoffRequests = async (
	token: string,
	limit?: number,
	offset?: number
): Promise<HandoffRequest[]> => {
	const params = new URLSearchParams();
	if (limit) params.set('limit', String(limit));
	if (offset) params.set('offset', String(offset));
	const query = params.toString() ? `?${params.toString()}` : '';
	return apiClient.get(`/handoff/pending${query}`, { token });
};

export const acceptHandoffRequest = async (token: string, id: string): Promise<HandoffRequest> =>
	apiClient.post(`/handoff/${id}/accept`, undefined, { token });

export const resolveHandoffRequest = async (token: string, id: string): Promise<HandoffRequest> =>
	apiClient.post(`/handoff/${id}/resolve`, undefined, { token });

export const dismissHandoffRequest = async (token: string, id: string): Promise<HandoffRequest> =>
	apiClient.post(`/handoff/${id}/dismiss`, undefined, { token });

export const getHandoffStats = async (token: string): Promise<Record<string, unknown>> =>
	apiClient.get('/handoff/stats', { token });

export const getHandoffConfig = async (token: string): Promise<HandoffConfig> =>
	apiClient.get('/handoff/config', { token });

export const updateHandoffConfig = async (
	token: string,
	config: HandoffConfig
): Promise<HandoffConfig> => apiClient.post('/handoff/config/update', { ...config }, { token });
