/**
 * @fileoverview Date and time formatting utilities built on top of dayjs.
 *
 * @module utils/date
 */

import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import isToday from 'dayjs/plugin/isToday';
import isYesterday from 'dayjs/plugin/isYesterday';
import localizedFormat from 'dayjs/plugin/localizedFormat';

// Extend dayjs with the plugins we need
dayjs.extend(relativeTime);
dayjs.extend(isToday);
dayjs.extend(isYesterday);
dayjs.extend(localizedFormat);

/**
 * Format a date with contextual labels ("Today at …", "Yesterday at …").
 *
 * @param inputDate - A parseable date value (string, Date, timestamp, etc.).
 * @returns A human-readable date string.
 */
export const formatDate = (inputDate: string | Date | number): string => {
	const date = dayjs(inputDate);

	if (date.isToday()) {
		return `Today at ${date.format('LT')}`;
	} else if (date.isYesterday()) {
		return `Yesterday at ${date.format('LT')}`;
	} else {
		return `${date.format('L')} at ${date.format('LT')}`;
	}
};

/**
 * Convert a nanosecond duration into a human-readable `"Xh Xm Xs"` string.
 *
 * @param nanoseconds - Duration in nanoseconds.
 * @returns A string like `"1h 2m 5s"` (zero-valued units are omitted except seconds).
 */
export const approximateToHumanReadable = (nanoseconds: number): string => {
	const seconds = Math.floor((nanoseconds / 1e9) % 60);
	const minutes = Math.floor((nanoseconds / 6e10) % 60);
	const hours = Math.floor((nanoseconds / 3.6e12) % 24);

	const results: string[] = [];

	if (seconds >= 0) {
		results.push(`${seconds}s`);
	}

	if (minutes > 0) {
		results.push(`${minutes}m`);
	}

	if (hours > 0) {
		results.push(`${hours}h`);
	}

	return results.reverse().join(' ');
};

/**
 * Classify a Unix timestamp into a human-friendly time range bucket.
 *
 * Buckets (in order of priority):
 * `"Today"` → `"Yesterday"` → `"Previous 7 days"` → `"Previous 30 days"`
 * → month name (same year) → year number (older).
 *
 * @param timestamp - Unix timestamp in **seconds**.
 * @returns The bucket label string.
 */
export const getTimeRange = (timestamp: number): string => {
	const now = new Date();
	const date = new Date(timestamp * 1000); // Convert Unix seconds → ms

	const diffTime = now.getTime() - date.getTime();
	const diffDays = diffTime / (1000 * 3600 * 24);

	const nowDate = now.getDate();
	const nowMonth = now.getMonth();
	const nowYear = now.getFullYear();

	const dateDate = date.getDate();
	const dateMonth = date.getMonth();
	const dateYear = date.getFullYear();

	if (nowYear === dateYear && nowMonth === dateMonth && nowDate === dateDate) {
		return 'Today';
	} else if (nowYear === dateYear && nowMonth === dateMonth && nowDate - dateDate === 1) {
		return 'Yesterday';
	} else if (diffDays <= 7) {
		return 'Previous 7 days';
	} else if (diffDays <= 30) {
		return 'Previous 30 days';
	} else if (nowYear === dateYear) {
		return date.toLocaleString('default', { month: 'long' });
	} else {
		return date.getFullYear().toString();
	}
};

/**
 * Get today's date formatted as `YYYY-MM-DD`.
 *
 * @returns Date string.
 */
export const getFormattedDate = (): string => {
	const date = new Date();
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

/**
 * Get the current time formatted as `HH:MM:SS`.
 *
 * @returns Time string.
 */
export const getFormattedTime = (): string => {
	const date = new Date();
	return date.toTimeString().split(' ')[0];
};

/**
 * Get the current date and time as `YYYY-MM-DD HH:MM:SS`.
 *
 * @returns Datetime string.
 */
export const getCurrentDateTime = (): string => {
	return `${getFormattedDate()} ${getFormattedTime()}`;
};

/**
 * Detect the user's IANA timezone string (e.g. `"Asia/Seoul"`).
 *
 * @returns The timezone identifier.
 */
export const getUserTimezone = (): string => {
	return Intl.DateTimeFormat().resolvedOptions().timeZone;
};

/**
 * Get the current day of the week as a full English name.
 *
 * @returns E.g. `"Monday"`, `"Tuesday"`, …
 */
export const getWeekday = (): string => {
	const date = new Date();
	const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
	return weekdays[date.getDay()];
};
