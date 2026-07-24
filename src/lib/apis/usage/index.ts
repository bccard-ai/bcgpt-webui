import { apiClient } from '$lib/apis/client';

/** Token/cost usage aggregation client → /api/v1/usage/*. All timestamps are ms. */

export interface UsageByDayRow {
	day: number; // epoch-day integer (ms / 86_400_000)
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	cost: number;
	count: number;
}

export interface UsageByGroupRow {
	model?: string;
	user_id?: string;
	agent_id?: string;
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	cost: number;
	count: number;
}

export interface UsageTotal {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	cost: number;
	count: number;
}

const qs = (startMs?: number, endMs?: number): string => {
	const p = new URLSearchParams();
	if (startMs !== undefined) p.set('start_ts', String(startMs));
	if (endMs !== undefined) p.set('end_ts', String(endMs));
	const s = p.toString();
	return s ? `?${s}` : '';
};

export const getUsageTotal = (token: string, startMs?: number, endMs?: number) =>
	apiClient.get<UsageTotal>(`/usage/total${qs(startMs, endMs)}`, { token });

export const getUsageByDay = (token: string, startMs?: number, endMs?: number) =>
	apiClient.get<{ data: UsageByDayRow[] }>(`/usage/by_day${qs(startMs, endMs)}`, { token });

export const getUsageByModel = (token: string, startMs?: number, endMs?: number) =>
	apiClient.get<{ data: UsageByGroupRow[] }>(`/usage/by_model${qs(startMs, endMs)}`, { token });

export const getUsageByUser = (token: string, startMs?: number, endMs?: number) =>
	apiClient.get<{ data: UsageByGroupRow[] }>(`/usage/by_user${qs(startMs, endMs)}`, { token });
