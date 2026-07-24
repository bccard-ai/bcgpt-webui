/**
 * @fileoverview Miscellaneous utility helpers that don't belong to a
 * specific domain module.
 *
 * @module utils/misc
 */

/**
 * Validate that a string is a well-formed HTTP or HTTPS URL.
 */
export const isValidHttpUrl = (string: string): boolean => {
	let url: URL;

	try {
		url = new URL(string);
	} catch {
		return false;
	}

	return url.protocol === 'http:' || url.protocol === 'https:';
};

/**
 * Compare two semver-style version strings.
 *
 * Returns `true` when **current** is strictly older than **latest**.
 * The sentinel value `'0.0.0'` is treated as "unknown / unset" and always
 * returns `false`.
 */
export const compareVersion = (latest: string, current: string): boolean => {
	return current === '0.0.0'
		? false
		: current.localeCompare(latest, undefined, {
				numeric: true,
				sensitivity: 'case',
				caseFirst: 'upper'
			}) < 0;
};

/**
 * Pick the best matching locale from the application's supported list
 * given the user's language preferences.
 */
export const bestMatchingLanguage = (
	supportedLanguages: { code: string }[],
	preferredLanguages: string[],
	defaultLocale: string
): string => {
	const languages = supportedLanguages.map((lang) => lang.code);

	const match = preferredLanguages
		.map((prefLang) => languages.find((lang) => lang.startsWith(prefLang)))
		.find(Boolean);

	return match || defaultLocale;
};

/**
 * Request the user's geolocation via the browser Geolocation API.
 *
 * @param raw - When `true`, returns `{ latitude, longitude }` numerics.
 *              When `false`, returns a human-readable `"lat, long (lat, long)"` string.
 */
export const getUserPosition = async (
	raw: boolean = false
): Promise<string | { latitude: number; longitude: number }> => {
	const position = await new Promise<GeolocationPosition>((resolve, reject) => {
		navigator.geolocation.getCurrentPosition(resolve, reject);
	}).catch((error: GeolocationPositionError) => {
		console.error('Error getting user location:', error);
		throw error;
	});

	if (!position) {
		return 'Location not available';
	}

	const { latitude, longitude } = position.coords;

	if (raw) {
		return { latitude, longitude };
	}

	return `${latitude.toFixed(3)}, ${longitude.toFixed(3)} (lat, long)`;
};
