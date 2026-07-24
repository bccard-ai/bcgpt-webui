/**
 * @fileoverview Canvas-based utilities for image processing and
 * fingerprint detection.
 *
 * @module utils/canvas
 */

/**
 * Test whether the browser's canvas API returns correct pixel data.
 *
 * Writes known RGB values to a 1×1 canvas and reads them back. A mismatch
 * typically indicates that a browser extension (e.g. CanvasBlocker) is
 * spoofing canvas fingerprint data.
 *
 * @returns `true` when pixel data round-trips correctly.
 */
export const canvasPixelTest = (): boolean => {
	// Inspiration: https://github.com/kkapsner/CanvasBlocker/blob/master/test/detectionTest.js
	const canvas = document.createElement('canvas');
	const ctx = canvas.getContext('2d')!;
	canvas.height = 1;
	canvas.width = 1;
	const imageData = new ImageData(canvas.width, canvas.height);
	const pixelValues = imageData.data;

	// Generate RGB test data (alpha is always 255)
	for (let i = 0; i < imageData.data.length; i += 1) {
		if (i % 4 !== 3) {
			pixelValues[i] = Math.floor(256 * Math.random());
		} else {
			pixelValues[i] = 255;
		}
	}

	ctx.putImageData(imageData, 0, 0);
	const p = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

	// Verify round-trip and report mismatches
	for (let i = 0; i < p.length; i += 1) {
		if (p[i] !== pixelValues[i]) {
			console.log(
				'canvasPixelTest: Wrong canvas pixel RGB value detected:',
				p[i],
				'at:',
				i,
				'expected:',
				pixelValues[i]
			);
			console.log('canvasPixelTest: Canvas blocking or spoofing is likely');
			return false;
		}
	}

	return true;
};

/**
 * Compress an image by resizing it to fit within the given dimensions
 * while maintaining aspect ratio.
 *
 * If the image already fits within the bounds, the original data-URL is
 * returned unchanged.
 *
 * @param imageUrl - Source image (data-URL or any loadable URL).
 * @param maxWidth - Maximum width in pixels. `undefined` = no width constraint.
 * @param maxHeight - Maximum height in pixels. `undefined` = no height constraint.
 * @returns A promise that resolves to a data-URL of the resized image.
 */
export const compressImage = (
	imageUrl: string,
	maxWidth?: number,
	maxHeight?: number
): Promise<string> => {
	return new Promise((resolve, reject) => {
		const img = new Image();
		img.onload = () => {
			const canvas = document.createElement('canvas');
			let width = img.width;
			let height = img.height;

			if (maxWidth && maxHeight) {
				// Both dimensions constrained — preserve aspect ratio
				if (width <= maxWidth && height <= maxHeight) {
					resolve(imageUrl);
					return;
				}

				if (width / height > maxWidth / maxHeight) {
					height = Math.round((maxWidth * height) / width);
					width = maxWidth;
				} else {
					width = Math.round((maxHeight * width) / height);
					height = maxHeight;
				}
			} else if (maxWidth) {
				if (width <= maxWidth) {
					resolve(imageUrl);
					return;
				}
				height = Math.round((maxWidth * height) / width);
				width = maxWidth;
			} else if (maxHeight) {
				if (height <= maxHeight) {
					resolve(imageUrl);
					return;
				}
				width = Math.round((maxHeight * width) / height);
				height = maxHeight;
			}

			canvas.width = width;
			canvas.height = height;

			const context = canvas.getContext('2d')!;
			context.drawImage(img, 0, 0, width, height);

			const compressedUrl = canvas.toDataURL();
			resolve(compressedUrl);
		};
		img.onerror = (error) => reject(error);
		img.src = imageUrl;
	});
};

/**
 * Generate a 100×100 avatar image from a user's initials.
 *
 * If the canvas pixel test fails (indicating fingerprint evasion), a
 * fallback `/user.png` path is returned instead.
 *
 * @param name - Display name (first letter + first letter of last word used).
 * @returns A data-URL of the generated avatar, or `/user.png` on failure.
 */
export const generateInitialsImage = (name: string): string => {
	const canvas = document.createElement('canvas');
	const ctx = canvas.getContext('2d')!;
	canvas.width = 100;
	canvas.height = 100;

	if (!canvasPixelTest()) {
		console.log(
			'generateInitialsImage: failed pixel test, fingerprint evasion is likely. Using default image.'
		);
		return '/user.png';
	}

	ctx.fillStyle = '#F39C12';
	ctx.fillRect(0, 0, canvas.width, canvas.height);

	ctx.fillStyle = '#FFFFFF';
	ctx.font = '40px Helvetica';
	ctx.textAlign = 'center';
	ctx.textBaseline = 'middle';

	const sanitizedName = name.trim();
	const initials =
		sanitizedName.length > 0
			? sanitizedName[0] +
				(sanitizedName.split(' ').length > 1
					? sanitizedName[sanitizedName.lastIndexOf(' ') + 1]
					: '')
			: '';

	ctx.fillText(initials.toUpperCase(), canvas.width / 2, canvas.height / 2);

	return canvas.toDataURL();
};
