/**
 * @fileoverview Async utility functions.
 *
 * Extracted from {@link module:utils/string} to keep string helpers focused
 * on text manipulation.
 *
 * @module utils/async
 */

/**
 * Return a promise that resolves after the specified delay.
 *
 * @param ms - Milliseconds to wait.
 */
export const sleep = (ms: number): Promise<void> =>
	new Promise((resolve) => setTimeout(resolve, ms));
