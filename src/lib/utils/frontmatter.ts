/**
 * @fileoverview Frontmatter extraction from prompt/markdown content.
 *
 * @module utils/frontmatter
 */

/**
 * Extract triple-quoted frontmatter from a content string.
 *
 * Frontmatter is delimited by `"""` on its own line at the very start
 * of the content. Key-value pairs inside use `key: value` syntax.
 */
export const extractFrontmatter = (content: string): Record<string, string> => {
	const frontmatter: Record<string, string> = {};
	const frontmatterPattern = /^\s*([a-z_]+):\s*(.*)\s*$/i;

	const lines = content.split('\n');

	if (lines[0].trim() !== '"""') {
		return {};
	}

	for (let i = 1; i < lines.length; i++) {
		const line = lines[i];

		if (line.includes('"""')) {
			break;
		}

		const match = frontmatterPattern.exec(line);
		if (match) {
			const [, key, value] = match;
			frontmatter[key.trim()] = value.trim();
		}
	}

	return frontmatter;
};
