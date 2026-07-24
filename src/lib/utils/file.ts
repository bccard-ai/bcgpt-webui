/**
 * @fileoverview File-related utility helpers.
 *
 * @module utils/file
 */

/**
 * Convert a {@link Blob} into a {@link File} while preserving the MIME type.
 */
export const blobToFile = (blob: Blob, fileName: string): File => {
	return new File([blob], fileName, { type: blob.type });
};

/**
 * Format a byte count into a human-readable file-size string.
 */
export const formatFileSize = (size: number | null | undefined): string => {
	if (size == null) return 'Unknown size';
	if (typeof size !== 'number' || size < 0) return 'Invalid size';
	if (size === 0) return '0 B';
	const units = ['B', 'KB', 'MB', 'GB', 'TB'];
	let unitIndex = 0;

	while (size >= 1024 && unitIndex < units.length - 1) {
		size /= 1024;
		unitIndex++;
	}

	return `${size.toFixed(1)} ${units[unitIndex]}`;
};
