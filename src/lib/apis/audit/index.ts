import { apiClient } from '$lib/apis/client';

export interface AuditLog {
	id: string;
	timestamp: number;
	user_id: string | null;
	user_email: string | null;
	action: string;
	resource_type: string;
	resource_id: string | null;
	resource_name: string | null;
	details: Record<string, unknown> | null;
	ip_address: string | null;
	user_agent: string | null;
	request_method: string | null;
	request_path: string | null;
	response_status: number | null;
	severity: string;
	category: string | null;
	session_id: string | null;
	created_at: number;
}

export interface AuditStats {
	total_logs: number;
	logs_today: number;
	by_severity: Record<string, number>;
	by_action: Record<string, number>;
	by_resource_type: Record<string, number>;
	recent_critical_count: number;
	active_users_today: number;
}

export interface Anomaly {
	type: string;
	severity: string;
	details: Record<string, unknown>;
	detected_at: number;
}

export interface ComplianceSummary {
	period_days: number;
	period_start: number;
	period_end: number;
	total_events: number;
	personal_data_access_count: number;
	pii_masked_count: number;
	data_exports: number;
	security_events: number;
	failed_auth_attempts: number;
	generated_at: number;
}

export interface TimelineData {
	timestamp: number;
	count: number;
}

export interface AuditConfig {
	audit_log_level: string;
	audit_excluded_paths: string;
	max_body_log_size: number;
	audit_log_file_rotation_size: string;
	audit_retention_days: number;
}

const buildQuery = (params?: Record<string, unknown>): string => {
	if (!params) return '';
	const query = new URLSearchParams();
	Object.entries(params).forEach(([key, value]) => {
		if (value !== undefined && value !== null) {
			query.append(key, String(value));
		}
	});
	return `?${query.toString()}`;
};

export const getAuditLogs = async (
	token: string,
	params?: {
		skip?: number;
		limit?: number;
		user_id?: string;
		action?: string;
		resource_type?: string;
		severity?: string;
		start_time?: number;
		end_time?: number;
		search?: string;
	}
): Promise<{ logs: AuditLog[]; total: number }> => {
	return apiClient.get(`/audit/logs${buildQuery(params as Record<string, unknown>)}`, { token });
};

export const getAuditStats = async (token: string): Promise<AuditStats> => {
	return apiClient.get('/audit/stats', { token });
};

export const getPersonalDataAccess = async (
	token: string,
	params?: {
		skip?: number;
		limit?: number;
		user_id?: string;
		start_time?: number;
		end_time?: number;
	}
): Promise<{ logs: AuditLog[]; total: number }> => {
	return apiClient.get(
		`/audit/personal-data-access${buildQuery(params as Record<string, unknown>)}`,
		{ token }
	);
};

export const getAnomalies = async (
	token: string,
	hours: number = 24
): Promise<{ anomalies: Anomaly[] }> => {
	return apiClient.get(`/audit/anomalies?hours=${hours}`, { token });
};

export const getAuditTimeline = async (
	token: string,
	hours: number = 24,
	interval: string = 'hour'
): Promise<{ data: TimelineData[] }> => {
	return apiClient.get(`/audit/timeline?hours=${hours}&interval=${interval}`, { token });
};

export const getComplianceSummary = async (token: string): Promise<ComplianceSummary> => {
	return apiClient.get('/audit/compliance-summary', { token });
};

export const exportAuditLogs = async (
	token: string,
	format: string = 'json',
	params?: {
		user_id?: string;
		action?: string;
		resource_type?: string;
		severity?: string;
		start_time?: number;
		end_time?: number;
	}
): Promise<Blob> => {
	const query = new URLSearchParams({ format });
	if (params) {
		Object.entries(params).forEach(([key, value]) => {
			if (value !== undefined && value !== null) query.append(key, String(value));
		});
	}
	// Route through apiClient so the request hits the correct API base URL
	// (relative URLs break in cross-origin dev) and carries the session cookie.
	const res = await apiClient.get<Response>(`/audit/export?${query.toString()}`, {
		rawResponse: true
	});
	return res.blob();
};

export const purgeAuditLogs = async (
	token: string,
	days: number = 90
): Promise<{ deleted: number }> => {
	return apiClient.del(`/audit/purge?days=${days}`, undefined, { token });
};

export const getAuditConfig = async (token: string): Promise<AuditConfig> => {
	return apiClient.get('/audit/config', { token });
};

export const updateAuditConfig = async (
	token: string,
	config: AuditConfig
): Promise<AuditConfig> => {
	return apiClient.post('/audit/config/update', config, { token });
};
