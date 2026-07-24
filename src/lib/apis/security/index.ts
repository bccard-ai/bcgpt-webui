import { apiClient } from '$lib/apis/client';

export interface ScannerConfig {
	enabled: boolean;
}

export interface PIIScannerConfig extends ScannerConfig {
	mask_mode: string;
}

export interface ToxicityScannerConfig extends ScannerConfig {
	custom_word_list: string;
}

export interface LLMScannerConfig {
	enabled: boolean;
	model: string;
}

export interface GuardrailConfig {
	enabled: boolean;
	model: string;
	action: string;
}

export interface CanaryTokensConfig {
	enabled: boolean;
	position: string;
}

export interface SIEMWebhookConfig {
	enabled: boolean;
	url: string;
	headers: string;
}

export interface SecurityConfig {
	enabled: boolean;
	emergency_stop: boolean;
	shadow_mode: boolean;
	log_detections: boolean;
	prompt_injection: ScannerConfig;
	jailbreak: ScannerConfig;
	pii: PIIScannerConfig;
	toxicity: ToxicityScannerConfig;
	secrets: ScannerConfig;
	output_filter: ScannerConfig;
	llm_scanner: LLMScannerConfig;
	guardrail: GuardrailConfig;
	canary_tokens: CanaryTokensConfig;
	siem_webhook: SIEMWebhookConfig;
	conversation_scanning_enabled: boolean;
	conversation_threshold: string;
	confidence_threshold: string;
	ai_transparency_enabled: boolean;
	ai_notification_title: string;
	ai_notification_message: string;
	ai_disclaimer_text: string;
	ai_response_label: string;
	scan_file_uploads: boolean;
	scan_web_results: boolean;
	rate_limit_chat_enabled: boolean;
	rate_limit_chat_per_minute: number;
	rate_limit_chat_per_hour: number;
	rate_limit_chat_per_day: number;
}

export const getSecurityConfig = async (token: string): Promise<SecurityConfig> => {
	return apiClient.get('/security/config', { token });
};

export const updateSecurityConfig = async (
	token: string,
	config: SecurityConfig
): Promise<SecurityConfig> => {
	return apiClient.post('/security/config/update', { ...config }, { token });
};

// ---------------------------------------------------------------------------
// Security event analytics (admin dashboard). All timestamps are ms.
// ---------------------------------------------------------------------------

export interface SecurityEventStats {
	total: number;
	by_scanner: Record<string, number>;
	by_severity: Record<string, number>;
	by_threat_type: Record<string, number>;
	by_direction: Record<string, number>;
	blocked_count: number;
	shadow_count: number;
}

export interface SecurityTimelineBucket {
	timestamp: number;
	total: number;
	blocked: number;
	by_severity: Record<string, number>;
}

export const getSecurityEventStats = (
	token: string,
	startMs: number,
	endMs: number
): Promise<SecurityEventStats> => {
	return apiClient.get(`/security/events/stats?start_ts=${startMs}&end_ts=${endMs}`, { token });
};

export const getSecurityTimeline = (
	token: string,
	startMs: number,
	endMs: number,
	granularity: 'hour' | 'day' | 'week' = 'hour'
): Promise<{ data: SecurityTimelineBucket[] }> => {
	return apiClient.get(
		`/security/events/timeline?start_ts=${startMs}&end_ts=${endMs}&granularity=${granularity}`,
		{ token }
	);
};

export const getSecurityEventCount = (
	token: string,
	startMs?: number,
	endMs?: number
): Promise<{ count: number }> => {
	const p = new URLSearchParams();
	if (startMs !== undefined) p.set('start_ts', String(startMs));
	if (endMs !== undefined) p.set('end_ts', String(endMs));
	const s = p.toString();
	return apiClient.get(`/security/events/count${s ? `?${s}` : ''}`, { token });
};
