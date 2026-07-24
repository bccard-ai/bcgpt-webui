/**
 * @fileoverview Stream splitting utility for processing chunked responses.
 *
 * @module utils/stream
 */

/**
 * Create a `TransformStream` that splits incoming chunks on a delimiter.
 *
 * Useful for parsing newline-delimited JSON streams (NDJSON) or similar
 * protocols where logical messages are separated by a known string.
 *
 * @param splitOn - Delimiter string to split on (e.g. `'\n'`).
 * @returns A `TransformStream` that emits individual segments.
 */
export const splitStream = (splitOn: string): TransformStream => {
	let buffer = '';
	return new TransformStream({
		transform(chunk: string, controller: TransformStreamDefaultController) {
			buffer += chunk;
			const parts = buffer.split(splitOn);
			parts.slice(0, -1).forEach((part) => controller.enqueue(part));
			buffer = parts[parts.length - 1];
		},
		flush(controller: TransformStreamDefaultController) {
			if (buffer) controller.enqueue(buffer);
		}
	});
};
