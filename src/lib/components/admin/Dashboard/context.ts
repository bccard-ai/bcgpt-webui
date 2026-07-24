import { getContext, setContext } from 'svelte';

export type RangeKey = 'today' | '7d' | '30d';

export interface RangeState {
	key: RangeKey;
	startMs: number;
	endMs: number;
}

export interface DashboardCtx {
	range: RangeState;
	refreshNonce: number;
	auto: boolean;
	setRangeKey: (k: RangeKey) => void;
	refresh: () => void;
	toggleAuto: () => void;
}

const KEY = Symbol('admin-dashboard');

export function provideDashboard(ctx: DashboardCtx): void {
	setContext(KEY, ctx);
}

export function useDashboard(): DashboardCtx {
	const ctx = getContext<DashboardCtx>(KEY);
	if (!ctx) {
		throw new Error(
			'useDashboard() must be used within a component that called provideDashboard()'
		);
	}
	return ctx;
}

/** Compute [startMs, endMs] for a range key (all in epoch ms). */
export function rangeForKey(key: RangeKey, now = Date.now()): RangeState {
	const endMs = now;
	let startMs: number;
	if (key === 'today') {
		const d = new Date(now);
		startMs = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
	} else {
		const days = key === '7d' ? 7 : 30;
		startMs = now - days * 86_400_000;
	}
	return { key, startMs, endMs };
}

/** The auth token (cookie auth applies when empty). */
export const getToken = (): string =>
	typeof localStorage !== 'undefined' ? (localStorage.token ?? '') : '';

export const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
	{ key: 'today', label: 'Today' },
	{ key: '7d', label: '7 days' },
	{ key: '30d', label: '30 days' }
];
