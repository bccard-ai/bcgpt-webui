// Shared presentation + formatting helpers for the Audit module.
//
// Design rule for this module: color is spent ONLY on `severity`, which is the
// single dimension that carries real audit meaning (critical / warning / normal).
// Everything else — actions, resources, status, chart bars — stays monochrome so
// the section reads like the rest of the admin UI rather than a dashboard demo.

type Translate = (key: string, options?: Record<string, unknown>) => string;

// Localized relative time. Takes the i18n translator because this is a plain
// module with no access to the $i18n store; the day-or-older fallback is already
// locale-aware via toLocaleDateString().
export function formatRelativeTime(ms: number, t: Translate): string {
	const diff = Date.now() - ms;
	if (diff < 60_000) return t('just now');
	if (diff < 3_600_000) return t('{{count}}m ago', { count: Math.floor(diff / 60_000) });
	if (diff < 86_400_000) return t('{{count}}h ago', { count: Math.floor(diff / 3_600_000) });
	return new Date(ms).toLocaleDateString();
}

export function formatTimestamp(ms: number): string {
	return new Date(ms).toLocaleString();
}

// Solid dot used as a compact severity marker in tables and lists.
export function severityDot(sev: string): string {
	if (sev === 'CRITICAL') return 'bg-red-500';
	if (sev === 'WARNING') return 'bg-amber-500';
	return 'bg-gray-300 dark:bg-gray-600';
}

// Subtle filled badge for severity (the only colored badge in the module).
// The neutral fallback reuses NEUTRAL_BADGE so the chip style lives in one place.
export function severityBadge(sev: string): string {
	if (sev === 'CRITICAL') return 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400';
	if (sev === 'WARNING')
		return 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400';
	return NEUTRAL_BADGE;
}

// Bar fill for the severity distribution chart — mirrors the dot palette.
export function severityBar(sev: string): string {
	if (sev === 'CRITICAL') return 'bg-red-400 dark:bg-red-500';
	if (sev === 'WARNING') return 'bg-amber-400 dark:bg-amber-500';
	return 'bg-gray-300 dark:bg-gray-600';
}

// Left accent for anomaly cards — restrained, scannable, severity-driven.
export function severityAccent(sev: string): string {
	if (sev === 'CRITICAL') return 'border-l-red-400 dark:border-l-red-500';
	if (sev === 'WARNING') return 'border-l-amber-400 dark:border-l-amber-500';
	return 'border-l-gray-200 dark:border-l-gray-700';
}

// Neutral badge for everything that is metadata, not a signal (action, resource).
export const NEUTRAL_BADGE = 'bg-gray-100 text-gray-600 dark:bg-gray-850 dark:text-gray-300';

export function humanize(value: string): string {
	return value.replace(/_/g, ' ');
}

export function triggerDownload(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

export function fileStamp(): string {
	return new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
}

export const PII_TYPE_LABELS: Record<string, string> = {
	email: 'Email',
	us_phone: 'US Phone',
	korean_phone: '한국 휴대전화',
	us_ssn: 'US SSN',
	korean_rrn: '주민등록번호',
	credit_card: '신용카드',
	korean_bank_account: '은행계좌'
};

export const PII_TYPE_BADGE: Record<string, string> = {
	email: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
	us_phone: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
	korean_phone: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
	us_ssn: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
	korean_rrn: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
	credit_card: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
	korean_bank_account: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400'
};

export function piiLabel(type: string): string {
	return PII_TYPE_LABELS[type] || humanize(type);
}

export function piiBadge(type: string): string {
	return PII_TYPE_BADGE[type] || NEUTRAL_BADGE;
}
