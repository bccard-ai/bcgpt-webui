/**
 * @fileoverview Core string manipulation utilities used across the app.
 *
 * Includes token replacement, HTML sanitisation, and simple text transforms.
 *
 * @module utils/string
 */

import { APP_BASE_URL } from '$lib/constants';

/**
 * Replace template tokens in `content` with their resolved values.
 *
 * Supported tokens:
 * - `{{char}}` → replaced with the `char` parameter (case-insensitive).
 * - `{{user}}` → replaced with the `user` parameter (case-insensitive).
 * - `{{VIDEO_FILE_ID_<uuid>}}` → embedded `<video>` element.
 * - `{{HTML_FILE_ID_<uuid>}}` → embedded `<iframe>` element.
 * - Bracketed citations `[1]`, `[2]`, … → `<source_id>` tags when `sourceIds` is provided.
 *
 * Tokens inside fenced code blocks (` ``` `) or inline code (`` ` ``) are **not** replaced.
 *
 * @param content - Template string containing tokens.
 * @param sourceIds - Array of source IDs to map bracket indices to, or `null`.
 * @param char - Character name (replaces `{{char}}`).
 * @param user - User name (replaces `{{user}}`).
 * @returns The content string with tokens replaced.
 */
export const replaceTokens = (
	content: string,
	sourceIds: string[] | null,
	char: string | undefined,
	user: string | undefined
): string => {
	const tokens = [
		{ regex: /{{char}}/gi, replacement: char },
		{ regex: /{{user}}/gi, replacement: user },
		{
			regex: /{{VIDEO_FILE_ID_([a-f0-9-]+)}}/gi,
			replacement: (_: string, fileId: string) =>
				`<video src="${APP_BASE_URL}/api/v1/files/${fileId}/content" controls></video>`
		},
		{
			regex: /{{HTML_FILE_ID_([a-f0-9-]+)}}/gi,
			replacement: (_: string, fileId: string) =>
				`<iframe src="${APP_BASE_URL}/api/v1/files/${fileId}/content/html" width="100%" frameborder="0" onload="this.style.height=(this.contentWindow.document.body.scrollHeight+20)+'px';"></iframe>`
		}
	];

	/**
	 * Apply `replacementFn` to every segment of `text` that is **not**
	 * inside a fenced or inline code block.
	 */
	const processOutsideCodeBlocks = (
		text: string,
		replacementFn: (segment: string) => string
	): string => {
		return text
			.split(/(```[\s\S]*?```|`[\s\S]*?`)/)
			.map((segment) => {
				return segment.startsWith('```') || segment.startsWith('`')
					? segment
					: replacementFn(segment);
			})
			.join('');
	};

	// Apply token replacements outside code blocks only
	content = processOutsideCodeBlocks(content, (segment) => {
		tokens.forEach(({ regex, replacement }) => {
			if (replacement !== undefined && replacement !== null) {
				segment = segment.replace(regex, replacement as string);
			}
		});

		if (Array.isArray(sourceIds)) {
			sourceIds.forEach((sourceId, idx) => {
				const regex = new RegExp(`\\[${idx + 1}\\]`, 'g');
				segment = segment.replace(regex, `<source_id data="${idx + 1}" title="${sourceId}" />`);
			});
		}

		return segment;
	});

	return content;
};

/**
 * Strip incomplete special tokens and escape raw HTML angle brackets.
 *
 * Removes trailing partial tokens such as `<|im` and converts `<` / `>`
 * to their HTML entity equivalents.
 *
 * @param content - Raw model output that may contain special tokens.
 * @returns Sanitised, trimmed string.
 */
export const sanitizeResponseContent = (content: string): string => {
	return content
		.replace(/<\|[a-z]*$/, '')
		.replace(/<\|[a-z]+\|$/, '')
		.replace(/<$/, '')
		.replaceAll(/<\|[a-z]+\|>/g, ' ')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.trim();
};

/**
 * Trim surrounding whitespace from a response content string.
 *
 * @param content - Raw response content.
 * @returns Trimmed content.
 */
export const processResponseContent = (content: string): string => {
	return content.trim();
};

/**
 * Decode the common HTML entities WITHOUT parsing markup.
 *
 * Deliberately not DOMParser-based: DOMParser interprets `<...>` as real
 * elements and returns their textContent, so `unescapeHtml('<script>')` would
 * yield '' (an empty script element) and render blank. The same applies to any
 * bare tag like `<div>`, `<b>`, `<br>`. This regex form decodes ONLY character
 * references and leaves literal `<`, `>` intact, so they survive to be escaped
 * by Svelte's text interpolation and rendered as visible text.
 *
 * @param html - HTML-entity-encoded string (e.g. `&lt;script&gt;`, `a &amp; b`).
 * @returns The entity-decoded plain string.
 */
export function unescapeHtml(html: string): string {
	return html
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&#0*39;/g, "'")
		.replace(/&#x0*27;/gi, "'")
		.replace(/&apos;/g, "'")
		.replace(/&nbsp;/g, ' ')
		.replace(/&amp;/g, '&');
}

/**
 * Capitalize the first character of a string.
 *
 * @param string - Input string.
 * @returns The string with its first letter uppercased.
 */
export const capitalizeFirstLetter = (string: string): string => {
	return string.charAt(0).toUpperCase() + string.slice(1);
};
