import dayjs from 'dayjs';

/** Compact number formatting: 1234 -> "1.2K", 2_500_000 -> "2.5M". */
export const formatCompact = (n: number): string => {
	if (n === null || n === undefined || !isFinite(n)) return '0';
	const abs = Math.abs(n);
	if (abs >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
	if (abs >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
	if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
	return String(Math.round(n));
};

/** Token counts reuse compact formatting. */
export const formatTokens = (n: number): string => formatCompact(n);

/** Cost formatting with adaptive precision. */
export const formatCost = (n: number): string => {
	if (n === null || n === undefined || !isFinite(n)) return '$0';
	const abs = Math.abs(n);
	if (abs >= 1000) return '$' + formatCompact(n);
	if (abs >= 1) return '$' + n.toFixed(2);
	if (abs > 0) return '$' + n.toFixed(4);
	return '$0';
};

/** Full locale-formatted number for tooltips. */
export const formatFull = (n: number): string => Math.round(n).toLocaleString();

/** Short date label for chart axes. */
export const formatDate = (ms: number, pattern = 'M/D'): string => dayjs(ms).format(pattern);

/** Verbose date+time for tooltips. */
export const formatDateTime = (ms: number): string => dayjs(ms).format('MMM D · HH:mm');
