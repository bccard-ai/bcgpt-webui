/**
 * @fileoverview Barrel export for the `utils` package.
 *
 * Re-exports every public utility function from its domain module so that
 * existing deep-import paths like `import { sleep } from '$lib/utils'`
 * continue to resolve without changes.
 *
 * @module utils
 */

// ── String utilities ─────────────────────────────────────────────────
export {
	replaceTokens,
	sanitizeResponseContent,
	processResponseContent,
	unescapeHtml,
	capitalizeFirstLetter
} from './string';

// ── Async utilities ──────────────────────────────────────────────────
export { sleep } from './async';

// ── Stream utilities ─────────────────────────────────────────────────
export { splitStream } from './stream';

// ── Chat history (BC Card) ───────────────────────────────────────────
export { convertMessagesToHistory, createMessagesList } from './chat-history';

// ── Cryptographic helpers (BC Card) ──────────────────────────────────
export { getGravatarURL, calculateSHA256 } from './crypto';

// ── Canvas / image utilities ─────────────────────────────────────────
export { canvasPixelTest, compressImage, generateInitialsImage } from './canvas';

// ── Date & time utilities ────────────────────────────────────────────
export {
	formatDate,
	approximateToHumanReadable,
	getTimeRange,
	getFormattedDate,
	getFormattedTime,
	getCurrentDateTime,
	getUserTimezone,
	getWeekday
} from './date';

// ── Clipboard (BC Card) ──────────────────────────────────────────────
export { copyToClipboard } from './clipboard';

// ── Text processing utilities ────────────────────────────────────────
export {
	findWordIndices,
	removeLastWordFromString,
	removeFirstHashWord,
	transformFileName,
	removeEmojis,
	removeFormattings,
	cleanText,
	removeDetails,
	extractSentences,
	extractParagraphsForAudio,
	extractSentencesForAudio,
	getMessageContentParts,
	getLineCount
} from './text';

// ── Chat import (BC Card) ────────────────────────────────────────────
export { getImportOrigin, convertOpenAIChats } from './chat-import';

// ── Prompt template utilities ────────────────────────────────────────
export { getPromptVariables, promptTemplate, titleGenerationTemplate } from './prompt';

// ── OpenAPI conversion ───────────────────────────────────────────────
export { convertOpenApiToToolPayload } from './openapi';

// ── File utilities ───────────────────────────────────────────────────
export { blobToFile, formatFileSize } from './file';

// ── Frontmatter extraction ───────────────────────────────────────────
export { extractFrontmatter } from './frontmatter';

// ── Miscellaneous helpers ────────────────────────────────────────────
export { isValidHttpUrl, compareVersion, bestMatchingLanguage, getUserPosition } from './misc';
