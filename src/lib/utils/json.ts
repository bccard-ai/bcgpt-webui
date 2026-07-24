/**
 * @fileoverview Safe JSON parsing with fallback values.
 *
 * @module utils/json
 */

/**
 * Safely parse a JSON string, returning a fallback value on failure.
 *
 * Use this instead of raw `JSON.parse()` when reading from localStorage,
 * sessionStorage, or other untrusted sources where malformed JSON could
 * crash the application.
 *
 * @typeParam T - Expected type of the parsed value.
 * @param raw - JSON string to parse. `null`, `undefined`, or empty strings all return the fallback.
 * @param fallback - Value returned when parsing fails.
 * @returns The parsed value, or `fallback` on any error.
 */
export function safeJsonParse<T>(raw: string | null | undefined, fallback: T): T {
	if (raw === null || raw === undefined) {
		return fallback;
	}
	try {
		return JSON.parse(raw) as T;
	} catch {
		return fallback;
	}
}
