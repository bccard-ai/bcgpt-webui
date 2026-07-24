/**
 * @fileoverview Google Drive file picker integration.
 *
 * Loads the Google Picker and Auth APIs on demand, authenticates the user
 * via OAuth 2.0, presents the picker UI, and downloads the selected file.
 *
 * @module utils/google-drive-picker
 */

import { getBackendConfig } from '$lib/apis';
import { logger } from '$lib/utils/logger';

// ── Configuration ─────────────────────────────────────────────────────

/** Google Drive API key, fetched from the backend config endpoint. */
let API_KEY = '';
/** Google OAuth client ID, fetched from the backend config endpoint. */
let CLIENT_ID = '';

/** OAuth scopes required for read-only Drive access. */
const SCOPE = [
	'https://www.googleapis.com/auth/drive.readonly',
	'https://www.googleapis.com/auth/drive.file'
];

// ── Type definitions ──────────────────────────────────────────────────

type GoogleOAuthResponse = {
	access_token?: string;
};

type GoogleOAuthError = {
	message?: string;
};

type GooglePickerDocument = Record<string, string>;

type GooglePickerData = Record<string, unknown>;

/** Result returned after a successful file pick and download. */
type GoogleDrivePickerResult = {
	id: string;
	name: string;
	url: string;
	blob: Blob;
	headers: {
		Authorization: string;
		Accept: string;
	};
};

// ── Credential management ─────────────────────────────────────────────

/**
 * Fetch Google Drive API credentials from the backend `/api/config` endpoint.
 *
 * @throws When the request fails or credentials are missing.
 */
async function getCredentials(): Promise<void> {
	const config = (await getBackendConfig()) as {
		google_drive?: { api_key: string; client_id: string };
	};
	API_KEY = config.google_drive?.api_key ?? '';
	CLIENT_ID = config.google_drive?.client_id ?? '';

	if (!API_KEY || !CLIENT_ID) {
		throw new Error('Google Drive API credentials not configured');
	}
}

/**
 * Validate that non-empty API key and client ID are present.
 *
 * @throws When credentials are missing or blank.
 */
const validateCredentials = (): void => {
	if (!API_KEY || !CLIENT_ID) {
		throw new Error('Google Drive API credentials not configured');
	}
	if (API_KEY === '' || CLIENT_ID === '') {
		throw new Error('Please configure valid Google Drive API credentials');
	}
};

// ── State ─────────────────────────────────────────────────────────────

let oauthToken: string | null = null;
let initialized = false;

// ── API loading ───────────────────────────────────────────────────────

/**
 * Dynamically load the Google Picker API script.
 *
 * @returns A promise that resolves to `true` once the `picker` module is ready.
 */
export const loadGoogleDriveApi = (): Promise<boolean> => {
	return new Promise((resolve, reject) => {
		if (typeof gapi === 'undefined') {
			const script = document.createElement('script');
			script.src = 'https://apis.google.com/js/api.js';
			script.onload = () => {
				gapi.load('picker', () => {
					resolve(true);
				});
			};
			script.onerror = reject;
			document.body.appendChild(script);
		} else {
			gapi.load('picker', () => {
				resolve(true);
			});
		}
	});
};

/**
 * Dynamically load the Google Identity Services (GIS) client script.
 *
 * @returns A promise that resolves to `true` once the GIS library is available.
 */
export const loadGoogleAuthApi = (): Promise<boolean> => {
	return new Promise((resolve, reject) => {
		if (typeof google === 'undefined') {
			const script = document.createElement('script');
			script.src = 'https://accounts.google.com/gsi/client';
			script.onload = () => resolve(true);
			script.onerror = reject;
			document.body.appendChild(script);
		} else {
			resolve(true);
		}
	});
};

// ── Authentication ────────────────────────────────────────────────────

/**
 * Obtain an OAuth 2.0 access token via Google Identity Services.
 *
 * Caches the token in module state so subsequent calls are instant.
 *
 * @returns The access token string.
 */
export const getAuthToken = async (): Promise<string | null> => {
	if (!oauthToken) {
		return new Promise<string | null>((resolve, reject) => {
			const tokenClient = google.accounts.oauth2.initTokenClient({
				client_id: CLIENT_ID,
				scope: SCOPE.join(' '),
				callback: (response: GoogleOAuthResponse) => {
					if (response.access_token) {
						oauthToken = response.access_token;
						resolve(oauthToken);
					} else {
						reject(new Error('Failed to get access token'));
					}
				},
				error_callback: (error: GoogleOAuthError) => {
					reject(new Error(error.message || 'OAuth error occurred'));
				}
			});
			tokenClient.requestAccessToken();
		});
	}
	return oauthToken;
};

// ── Initialisation ────────────────────────────────────────────────────

/**
 * Perform one-time initialisation: fetch credentials and load the Picker
 * and Auth APIs.
 */
const initialize = async (): Promise<void> => {
	if (!initialized) {
		await getCredentials();
		validateCredentials();
		await Promise.all([loadGoogleDriveApi(), loadGoogleAuthApi()]);
		initialized = true;
	}
};

// ── File download helpers ─────────────────────────────────────────────

/**
 * Determine the export MIME type for Google Workspace documents.
 *
 * @param mimeType - Original MIME type (e.g. `application/vnd.google-apps.document`).
 * @returns The export MIME type.
 */
const getGoogleWorkspaceExportFormat = (mimeType: string): string => {
	if (mimeType.includes('document')) {
		return 'text/plain';
	}
	if (mimeType.includes('spreadsheet')) {
		return 'text/csv';
	}
	if (mimeType.includes('presentation')) {
		return 'text/plain';
	}
	return 'application/pdf';
};

/**
 * Build the download URL for a Drive file, handling both native Google
 * Workspace files (export endpoint) and regular files (media endpoint).
 *
 * @param fileId - Google Drive file ID.
 * @param mimeType - File MIME type.
 * @returns Download URL string.
 */
const getDownloadUrl = (fileId: string, mimeType: string): string => {
	if (mimeType.includes('google-apps')) {
		const exportFormat = getGoogleWorkspaceExportFormat(mimeType);
		return `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=${encodeURIComponent(exportFormat)}`;
	}

	return `https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`;
};

/**
 * Download a picked file from Google Drive using the authenticated token.
 *
 * @param doc - Picker document object.
 * @param token - OAuth access token.
 * @returns File metadata and blob.
 */
const downloadPickedFile = async (
	doc: GooglePickerDocument,
	token: string
): Promise<GoogleDrivePickerResult> => {
	const fileId = doc[google.picker.Document.ID];
	const fileName = doc[google.picker.Document.NAME];
	const mimeType = doc[google.picker.Document.MIME_TYPE];

	if (!fileId || !fileName || !mimeType) {
		throw new Error('Required file details missing');
	}

	const downloadUrl = getDownloadUrl(fileId, mimeType);
	const headers = {
		Authorization: `Bearer ${token}`,
		Accept: '*/*'
	};

	const response = await fetch(downloadUrl, { headers });

	if (!response.ok) {
		const errorText = await response.text();
		logger.error('google-drive', 'Download failed', undefined, {
			status: response.status,
			statusText: response.statusText,
			error: errorText
		});
		throw new Error(`Failed to download file (${response.status}): ${errorText}`);
	}

	const blob = await response.blob();
	return {
		id: fileId,
		name: fileName,
		url: downloadUrl,
		blob,
		headers
	};
};

// ── Public API ────────────────────────────────────────────────────────

/**
 * Open the Google Drive Picker and download the selected file.
 *
 * Handles the full lifecycle: initialise → authenticate → pick → download.
 *
 * @returns The picked file's metadata and blob, or `null` when the user cancels.
 * @throws On authentication failure, network errors, or missing credentials.
 */
export const createPicker = async (): Promise<GoogleDrivePickerResult | null> => {
	try {
		await initialize();
		const token = await getAuthToken();
		if (!token) {
			logger.error('google-drive', 'Failed to get OAuth token');
			throw new Error('Unable to get OAuth token');
		}

		return new Promise((resolve, reject) => {
			const picker = new google.picker.PickerBuilder()
				.enableFeature(google.picker.Feature.NAV_HIDDEN)
				.enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
				.addView(
					new google.picker.DocsView()
						.setIncludeFolders(false)
						.setSelectFolderEnabled(false)
						.setMimeTypes(
							'application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.google-apps.document,application/vnd.google-apps.spreadsheet,application/vnd.google-apps.presentation'
						)
				)
				.setOAuthToken(token)
				.setDeveloperKey(API_KEY)
				.setCallback((data: GooglePickerData) => {
					const action = data[google.picker.Response.ACTION];

					if (action === google.picker.Action.PICKED) {
						const docs = data[google.picker.Response.DOCUMENTS] as
							| GooglePickerDocument[]
							| undefined;
						const doc = docs?.[0];

						if (!doc) {
							reject(new Error('Required file details missing'));
							return;
						}

						downloadPickedFile(doc, token).then(resolve).catch(reject);
					} else if (action === google.picker.Action.CANCEL) {
						resolve(null);
					}
				})
				.build();
			picker.setVisible(true);
		});
	} catch (error) {
		logger.error('google-drive', 'Google Drive Picker error', undefined, error);
		throw error;
	}
};
