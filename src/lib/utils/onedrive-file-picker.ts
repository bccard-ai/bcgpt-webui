/**
 * @fileoverview OneDrive file picker integration.
 *
 * Uses Microsoft Authentication Library (MSAL) for OAuth and the
 * OneDrive file picker SDK for file selection and download.
 *
 * @module utils/onedrive-file-picker
 */

import { PublicClientApplication } from '@azure/msal-browser';
import type { PopupRequest } from '@azure/msal-browser';
import { getBackendConfig } from '$lib/apis';
import { v4 as uuidv4 } from 'uuid';

// ── Configuration ─────────────────────────────────────────────────────

/** OneDrive app client ID, fetched from the backend config endpoint. */
let CLIENT_ID = '';

// ── Type definitions ──────────────────────────────────────────────────

/** Metadata returned by the OneDrive picker for a selected file. */
type OneDriveFileInfo = {
	id: string;
	name: string;
	parentReference: {
		driveId: string;
	};
	'@sharePoint.endpoint': string;
};

/** Additional file metadata including the download URL. */
type OneDriveFileMetadata = {
	'@content.downloadUrl'?: string;
};

/** A command received from the OneDrive picker iframe. */
type OneDrivePickerCommand = {
	command: string;
	items?: OneDriveFileInfo[];
};

/** A message received from the OneDrive picker iframe. */
type OneDrivePickerMessage = {
	type?: 'notification' | 'command';
	id?: string;
	data?: OneDrivePickerCommand;
};

/** The shape returned by {@link openOneDrivePicker}. */
type OneDrivePickerResult = OneDrivePickerCommand;

// ── Credential management ─────────────────────────────────────────────

/**
 * Fetch the OneDrive client ID from the backend `/api/config` endpoint.
 *
 * @throws When the request fails or the client ID is missing.
 */
async function getCredentials(): Promise<void> {
	if (CLIENT_ID) return;

	const config = (await getBackendConfig()) as {
		onedrive?: { client_id: string };
	};
	CLIENT_ID = config.onedrive?.client_id ?? '';
	if (!CLIENT_ID) {
		throw new Error('OneDrive client ID not configured');
	}
}

// ── MSAL authentication ──────────────────────────────────────────────

let msalInstance: PublicClientApplication | null = null;

/**
 * Initialise the MSAL `PublicClientApplication` singleton.
 *
 * @returns The initialised MSAL instance.
 * @throws When MSAL initialisation fails.
 */
async function initializeMsal(): Promise<PublicClientApplication> {
	try {
		if (!CLIENT_ID) {
			await getCredentials();
		}

		const msalParams = {
			auth: {
				authority: 'https://login.microsoftonline.com/consumers',
				clientId: CLIENT_ID
			}
		};

		if (!msalInstance) {
			msalInstance = new PublicClientApplication(msalParams);
			if (msalInstance.initialize) {
				await msalInstance.initialize();
			}
		}

		return msalInstance;
	} catch (error) {
		throw new Error(
			'MSAL initialization failed: ' + (error instanceof Error ? error.message : String(error)),
			{ cause: error }
		);
	}
}

/**
 * Acquire an OneDrive access token.
 *
 * Tries silent acquisition first; falls back to an interactive popup login.
 *
 * @returns The access token string.
 * @throws When token acquisition fails.
 */
async function getToken(): Promise<string> {
	const authParams: PopupRequest = { scopes: ['OneDrive.ReadWrite'] };
	let accessToken = '';
	try {
		msalInstance = await initializeMsal();
		if (!msalInstance) {
			throw new Error('MSAL not initialized');
		}

		const resp = await msalInstance.acquireTokenSilent(authParams);
		accessToken = resp.accessToken;
	} catch (err) {
		if (!msalInstance) {
			throw new Error('MSAL not initialized', { cause: err });
		}

		try {
			const resp = await msalInstance.loginPopup(authParams);
			msalInstance.setActiveAccount(resp.account);
			if (resp.idToken) {
				const resp2 = await msalInstance.acquireTokenSilent(authParams);
				accessToken = resp2.accessToken;
			}
		} catch (popupError) {
			throw new Error(
				'Failed to login: ' +
					(popupError instanceof Error ? popupError.message : String(popupError)),
				{ cause: popupError }
			);
		}
	}

	if (!accessToken) {
		throw new Error('Failed to acquire access token');
	}

	return accessToken;
}

// ── Picker configuration ─────────────────────────────────────────────

const baseUrl = 'https://onedrive.live.com/picker';
const params = {
	sdk: '8.0',
	entry: {
		oneDrive: {
			files: {}
		}
	},
	authentication: {},
	messaging: {
		origin: typeof window !== 'undefined' ? window.location.origin : '',
		channelId: uuidv4()
	},
	typesAndSources: {
		mode: 'files',
		pivots: {
			oneDrive: true,
			recent: true
		}
	}
};

// ── File download ─────────────────────────────────────────────────────

/**
 * Download a file from OneDrive given its picker metadata.
 *
 * @param fileInfo - File metadata from the picker.
 * @returns The file contents as a `Blob`.
 * @throws When the download URL is missing or the request fails.
 */
async function downloadOneDriveFile(fileInfo: OneDriveFileInfo): Promise<Blob> {
	const accessToken = await getToken();
	if (!accessToken) {
		throw new Error('Unable to retrieve OneDrive access token.');
	}
	const fileInfoUrl = `${fileInfo['@sharePoint.endpoint']}/drives/${fileInfo.parentReference.driveId}/items/${fileInfo.id}`;
	const response = await fetch(fileInfoUrl, {
		headers: {
			Authorization: `Bearer ${accessToken}`
		}
	});
	if (!response.ok) {
		throw new Error('Failed to fetch file information.');
	}
	const fileData = (await response.json()) as OneDriveFileMetadata;
	const downloadUrl = fileData['@content.downloadUrl'];
	if (!downloadUrl) {
		throw new Error('Missing OneDrive download URL.');
	}
	const downloadResponse = await fetch(downloadUrl);
	if (!downloadResponse.ok) {
		throw new Error('Failed to download file.');
	}
	return await downloadResponse.blob();
}

// ── Public API ────────────────────────────────────────────────────────

/**
 * Open the OneDrive file picker in a popup window.
 *
 * Communicates with the picker via `MessagePort` to handle authentication,
 * close, and pick events.
 *
 * @returns Picker result containing selected items, or `null` when the user cancels.
 * @throws In non-browser environments or when the popup cannot be opened.
 */
export async function openOneDrivePicker(): Promise<OneDrivePickerResult | null> {
	if (typeof window === 'undefined') {
		throw new Error('Not in browser environment');
	}
	return new Promise((resolve, reject) => {
		let pickerWindow: Window | null = null;
		let channelPort: MessagePort | null = null;

		const handleWindowMessage = (event: MessageEvent) => {
			if (event.source !== pickerWindow) return;
			const message = event.data;
			if (message?.type === 'initialize' && message?.channelId === params.messaging.channelId) {
				channelPort = event.ports?.[0];
				if (!channelPort) return;
				channelPort.addEventListener('message', handlePortMessage);
				channelPort.start();
				channelPort.postMessage({ type: 'activate' });
			}
		};

		const handlePortMessage = async (portEvent: MessageEvent<OneDrivePickerMessage>) => {
			const portData = portEvent.data;
			switch (portData.type) {
				case 'notification':
					break;
				case 'command': {
					channelPort?.postMessage({ type: 'acknowledge', id: portData.id });
					const command = portData.data;
					if (!command) {
						channelPort?.postMessage({
							result: 'error',
							error: { code: 'invalidCommand', message: 'Missing command data' },
							isExpected: true
						});
						break;
					}
					switch (command.command) {
						case 'authenticate': {
							try {
								const newToken = await getToken();
								if (newToken) {
									channelPort?.postMessage({
										type: 'result',
										id: portData.id,
										data: { result: 'token', token: newToken }
									});
								} else {
									throw new Error('Could not retrieve auth token');
								}
							} catch (err) {
								const message = err instanceof Error ? err.message : 'Failed to get token';
								channelPort?.postMessage({
									result: 'error',
									error: { code: 'tokenError', message },
									isExpected: true
								});
							}
							break;
						}
						case 'close': {
							cleanup();
							resolve(null);
							break;
						}
						case 'pick': {
							channelPort?.postMessage({
								type: 'result',
								id: portData.id,
								data: { result: 'success' }
							});
							cleanup();
							resolve(command);
							break;
						}
						default: {
							channelPort?.postMessage({
								result: 'error',
								error: { code: 'unsupportedCommand', message: command.command },
								isExpected: true
							});
							break;
						}
					}
					break;
				}
			}
		};

		function cleanup() {
			window.removeEventListener('message', handleWindowMessage);
			if (channelPort) {
				channelPort.removeEventListener('message', handlePortMessage);
			}
			if (pickerWindow) {
				pickerWindow.close();
				pickerWindow = null;
			}
		}

		const initializePicker = async () => {
			try {
				const authToken = await getToken();
				if (!authToken) {
					return reject(new Error('Failed to acquire access token'));
				}

				pickerWindow = window.open('', 'OneDrivePicker', 'width=800,height=600');
				if (!pickerWindow) {
					return reject(new Error('Failed to open OneDrive picker window'));
				}

				const queryString = new URLSearchParams({
					filePicker: JSON.stringify(params)
				});
				const url = `${baseUrl}?${queryString.toString()}`;

				const form = pickerWindow.document.createElement('form');
				form.setAttribute('action', url);
				form.setAttribute('method', 'POST');
				const input = pickerWindow.document.createElement('input');
				input.setAttribute('type', 'hidden');
				input.setAttribute('name', 'access_token');
				input.setAttribute('value', authToken);
				form.appendChild(input);

				pickerWindow.document.body.appendChild(form);
				form.submit();

				window.addEventListener('message', handleWindowMessage);
			} catch (err) {
				if (pickerWindow) {
					pickerWindow.close();
				}
				reject(err);
			}
		};

		initializePicker();
	});
}

/**
 * Open the OneDrive picker and download the selected file.
 *
 * Convenience wrapper combining {@link openOneDrivePicker} and
 * {@link downloadOneDriveFile}.
 *
 * @returns The file blob and name, or `null` when the user cancels.
 */
export async function pickAndDownloadFile(): Promise<{ blob: Blob; name: string } | null> {
	const pickerResult = await openOneDrivePicker();

	if (!pickerResult || !pickerResult.items || pickerResult.items.length === 0) {
		return null;
	}

	const selectedFile = pickerResult.items[0];
	const blob = await downloadOneDriveFile(selectedFile);

	return { blob, name: selectedFile.name };
}

export { downloadOneDriveFile };
