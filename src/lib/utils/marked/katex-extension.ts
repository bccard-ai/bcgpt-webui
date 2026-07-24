/**
 * @fileoverview Marked.js extension for KaTeX / LaTeX math rendering.
 *
 * Supports inline (`$…$`, `\(...\)`) and display (`$$…$$`, `\[…\]`,
 * `\begin{equation}…\end{equation}`) math delimiters, plus chemistry
 * (`\ce{…}`) and unit (`\pu{…}`) shorthands.
 *
 * @module utils/marked/katex-extension
 */

/** Supported math delimiter definitions. */
const DELIMITER_LIST = [
	{ left: '$$', right: '$$', display: true },
	{ left: '$', right: '$', display: false },
	{ left: '\\pu{', right: '}', display: false },
	{ left: '\\ce{', right: '}', display: false },
	{ left: '\\(', right: '\\)', display: false },
	{ left: '\\[', right: '\\]', display: true },
	{ left: '\\begin{equation}', right: '\\end{equation}', display: true }
];

/**
 * Escape special regex characters in a string.
 *
 * @param string - Input string.
 * @returns Regex-safe escaped string.
 */
function escapeRegex(string: string): string {
	return string.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
}

/** Generated regex rule set for inline and block math. */
interface MathRules {
	inlineRule: RegExp;
	blockRule: RegExp;
}

/**
 * Generate inline and block regex patterns from the delimiter list.
 *
 * @param delimiters - Array of delimiter definitions.
 * @returns Compiled `{ inlineRule, blockRule }` regex pair.
 */
function generateRegexRules(delimiters: typeof DELIMITER_LIST): MathRules {
	const inlinePatterns: string[] = [];
	const blockPatterns: string[] = [];

	delimiters.forEach((delimiter) => {
		const { left, right, display } = delimiter;
		const escapedLeft = escapeRegex(left);
		const escapedRight = escapeRegex(right);

		if (!display) {
			// Inline: match everything between delimiters
			inlinePatterns.push(`${escapedLeft}((?:\\\\[^]|[^\\\\])+?)${escapedRight}`);
		} else {
			// Display: doubles as inline when not adjacent to newline
			inlinePatterns.push(`${escapedLeft}(?!\\n)((?:\\\\[^]|[^\\\\])+?)(?!\\n)${escapedRight}`);
			blockPatterns.push(`${escapedLeft}\\n((?:\\\\[^]|[^\\\\])+?)\\n${escapedRight}`);
		}
	});

	// Math formulas may end in punctuation or special characters
	const inlineRule = new RegExp(`^(${inlinePatterns.join('|')})(?=[\\s?。，!-/:-@[-\`{-~]|$)`, 'u');
	const blockRule = new RegExp(`^(${blockPatterns.join('|')})(?=[\\s?。，!-/:-@[-\`{-~]|$)`, 'u');

	return { inlineRule, blockRule };
}

const { inlineRule, blockRule } = generateRegexRules(DELIMITER_LIST);

// ── Token types ───────────────────────────────────────────────────────

/** Shape of a KaTeX token produced by the tokenizers. */
interface KatexToken {
	type: 'inlineKatex' | 'blockKatex';
	raw: string;
	text: string;
	displayMode: boolean;
}

// ── Public API ────────────────────────────────────────────────────────

/**
 * Returns a Marked.js extension set that recognises KaTeX math delimiters.
 *
 * Both inline and block math are tokenised; the renderer simply emits
 * the raw math text (a downstream processor such as KaTeX itself should
 * handle the actual rendering).
 *
 * @example
 * ```ts
 * import { marked } from 'marked';
 * import katexExtension from './katex-extension';
 *
 * marked.use(katexExtension());
 * ```
 */
export default function () {
	return {
		extensions: [inlineKatex(), blockKatex()]
	};
}

// ── Shared helpers ────────────────────────────────────────────────────

/**
 * Find the start index of the first math delimiter in `src`.
 *
 * @param src - Remaining source string.
 * @param displayMode - Whether to look for display (block) or inline delimiters.
 * @returns The character index, or `undefined` when no delimiter is found.
 */
function katexStart(src: string, displayMode: boolean): number | undefined {
	const ruleReg = displayMode ? blockRule : inlineRule;

	let indexSrc = src;

	while (indexSrc) {
		let index = -1;
		let startDelimiter = '';
		let endDelimiter = '';
		for (const delimiter of DELIMITER_LIST) {
			if (delimiter.display !== displayMode) {
				continue;
			}

			const startIndex = indexSrc.indexOf(delimiter.left);
			if (startIndex === -1) {
				continue;
			}

			index = startIndex;
			startDelimiter = delimiter.left;
			endDelimiter = delimiter.right;
		}

		if (index === -1) {
			return undefined;
		}

		// Check if preceded by a word boundary character
		const f = index === 0 || indexSrc.charAt(index - 1).match(/[\s?。，!-/:-@[-`{-~]/);
		if (f) {
			const possibleKatex = indexSrc.substring(index);

			if (possibleKatex.match(ruleReg)) {
				return index;
			}
		}

		indexSrc = indexSrc.substring(index + startDelimiter.length).replace(endDelimiter, '');
	}

	return undefined;
}

/**
 * Tokenise a math expression from the start of `src`.
 *
 * @param src - Source string beginning with a math delimiter.
 * @param displayMode - `true` for block math, `false` for inline.
 * @returns A `KatexToken`, or `undefined` when no match.
 */
function katexTokenizer(src: string, displayMode: boolean): KatexToken | undefined {
	const ruleReg = displayMode ? blockRule : inlineRule;
	const type = displayMode ? 'blockKatex' : 'inlineKatex';

	const match = src.match(ruleReg);

	if (match) {
		const text = match
			.slice(2)
			.filter((item) => item)
			.find((item) => item.trim());

		return {
			type,
			raw: match[0],
			text: text ?? '',
			displayMode
		};
	}

	return undefined;
}

// ── Extension definitions ─────────────────────────────────────────────

/** Inline KaTeX extension for Marked.js. */
function inlineKatex() {
	return {
		name: 'inlineKatex',
		level: 'inline' as const,
		start(src: string): number | undefined {
			return katexStart(src, false);
		},
		tokenizer(src: string): KatexToken | undefined {
			return katexTokenizer(src, false);
		},
		renderer(token: KatexToken): string {
			return `${token?.text ?? ''}`;
		}
	};
}

/** Block KaTeX extension for Marked.js. */
function blockKatex() {
	return {
		name: 'blockKatex',
		level: 'block' as const,
		start(src: string): number | undefined {
			return katexStart(src, true);
		},
		tokenizer(src: string): KatexToken | undefined {
			return katexTokenizer(src, true);
		},
		renderer(token: KatexToken): string {
			return `${token?.text ?? ''}`;
		}
	};
}
