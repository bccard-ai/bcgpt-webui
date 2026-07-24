/**
 * @fileoverview Prompt template utilities for variable substitution
 * and title generation.
 *
 * @module utils/prompt
 */

import {
	getCurrentDateTime,
	getFormattedDate,
	getFormattedTime,
	getWeekday,
	getUserTimezone
} from './date';

/**
 * Build a map of prompt template variables and their current values.
 *
 * @param user_name - Display name of the current user.
 * @param user_location - Human-readable location string (may be `null`).
 * @returns Object keyed by `{{VARIABLE_NAME}}` placeholders.
 */
export const getPromptVariables = (
	user_name: string,
	user_location: string | null
): Record<string, string> => {
	return {
		'{{USER_NAME}}': user_name,
		'{{USER_LOCATION}}': user_location || 'Unknown',
		'{{CURRENT_DATETIME}}': getCurrentDateTime(),
		'{{CURRENT_DATE}}': getFormattedDate(),
		'{{CURRENT_TIME}}': getFormattedTime(),
		'{{CURRENT_WEEKDAY}}': getWeekday(),
		'{{CURRENT_TIMEZONE}}': getUserTimezone(),
		'{{USER_LANGUAGE}}': localStorage.getItem('locale') || 'en-US'
	};
};

/**
 * Replace built-in template placeholders with live values.
 *
 * Supported placeholders:
 * - `{{CURRENT_DATETIME}}` – `YYYY-MM-DD HH:MM:SS AM/PM`
 * - `{{CURRENT_DATE}}` – `YYYY-MM-DD`
 * - `{{CURRENT_TIME}}` – `HH:MM:SS AM/PM`
 * - `{{CURRENT_WEEKDAY}}` – Full weekday name
 * - `{{CURRENT_TIMEZONE}}` – IANA timezone string
 * - `{{USER_LANGUAGE}}` – Locale from localStorage
 * - `{{USER_NAME}}` – (optional) User's display name
 * - `{{USER_LOCATION}}` – (optional) Location or `'LOCATION_UNKNOWN'`
 *
 * @param template - Template string with `{{…}}` placeholders.
 * @param user_name - Optional user name to substitute.
 * @param user_location - Optional location string.
 * @returns Template with placeholders replaced.
 */
export const promptTemplate = (
	template: string,
	user_name?: string,
	user_location?: string
): string => {
	// Date: YYYY-MM-DD
	const currentDate = new Date();
	const formattedDate =
		currentDate.getFullYear() +
		'-' +
		String(currentDate.getMonth() + 1).padStart(2, '0') +
		'-' +
		String(currentDate.getDate()).padStart(2, '0');

	// Time: HH:MM:SS AM/PM
	const currentTime = currentDate.toLocaleTimeString('en-US', {
		hour: 'numeric',
		minute: 'numeric',
		second: 'numeric',
		hour12: true
	});

	const currentWeekday = getWeekday();
	const currentTimezone = getUserTimezone();
	const userLanguage = localStorage.getItem('locale') || 'en-US';

	template = template.replace('{{CURRENT_DATETIME}}', `${formattedDate} ${currentTime}`);
	template = template.replace('{{CURRENT_DATE}}', formattedDate);
	template = template.replace('{{CURRENT_TIME}}', currentTime);
	template = template.replace('{{CURRENT_WEEKDAY}}', currentWeekday);
	template = template.replace('{{CURRENT_TIMEZONE}}', currentTimezone);
	template = template.replace('{{USER_LANGUAGE}}', userLanguage);

	if (user_name) {
		template = template.replace('{{USER_NAME}}', user_name);
	}

	template = template.replace(
		'{{USER_LOCATION}}',
		user_location ?? 'LOCATION_UNKNOWN'
	);

	return template;
};

/**
 * Replace `{{prompt…}}` placeholders in a title-generation template.
 *
 * Supported formats:
 * - `{{prompt}}` – Full prompt text.
 * - `{{prompt:start:<length>}}` – First `<length>` characters.
 * - `{{prompt:end:<length>}}` – Last `<length>` characters.
 * - `{{prompt:middletruncate:<length>}}` – Head + `…` + tail when the prompt exceeds `<length>`.
 *
 * After prompt substitution, {@link promptTemplate} is applied for datetime / user variables.
 *
 * @param template - Title template containing `{{prompt…}}` placeholders.
 * @param prompt - The user's prompt text.
 * @returns Fully resolved title string.
 */
export const titleGenerationTemplate = (template: string, prompt: string): string => {
	template = template.replace(
		/{{prompt}}|{{prompt:start:(\d+)}}|{{prompt:end:(\d+)}}|{{prompt:middletruncate:(\d+)}}/g,
		(match, startLength, endLength, middleLength) => {
			if (match === '{{prompt}}') {
				return prompt;
			} else if (match.startsWith('{{prompt:start:')) {
				return prompt.substring(0, startLength);
			} else if (match.startsWith('{{prompt:end:')) {
				return prompt.slice(-endLength);
			} else if (match.startsWith('{{prompt:middletruncate:')) {
				if (prompt.length <= middleLength) {
					return prompt;
				}
				const start = prompt.slice(0, Math.ceil(middleLength / 2));
				const end = prompt.slice(-Math.floor(middleLength / 2));
				return `${start}...${end}`;
			}
			return '';
		}
	);

	template = promptTemplate(template);

	return template;
};
