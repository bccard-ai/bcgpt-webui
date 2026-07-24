import { apiClient } from '$lib/apis/client';
import { logger } from '$lib/utils/logger';

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export const getAdminDetails = async (token: string) => {
	return apiClient.get('/auths/admin/details', { token });
};

export const getAdminConfig = async (token: string) => {
	return apiClient.get('/auths/admin/config', { token });
};

export const updateAdminConfig = async (token: string, body: object) => {
	return apiClient.post('/auths/admin/config', body, { token });
};

// ---------------------------------------------------------------------------
// Session & auth
// ---------------------------------------------------------------------------

export const getSessionUser = async (token: string) => {
	return apiClient.get('/auths/', { token, credentials: 'include' });
};

export const ldapUserSignIn = async (user: string, password: string) => {
	return apiClient.post('/auths/ldap', { user, password }, { credentials: 'include' });
};

export const getLdapConfig = async (token: string = '') => {
	return apiClient.get('/auths/admin/config/ldap', { token });
};

export const updateLdapConfig = async (token: string = '', enable_ldap: boolean) => {
	return apiClient.post('/auths/admin/config/ldap', { enable_ldap }, { token });
};

export const getLdapServer = async (token: string = '') => {
	return apiClient.get('/auths/admin/config/ldap/server', { token });
};

export const updateLdapServer = async (token: string = '', body: object) => {
	return apiClient.post('/auths/admin/config/ldap/server', body, { token });
};

export const userSignIn = async (email: string, password: string, totpCode?: string) => {
	return apiClient.post(
		'/auths/signin',
		{ email, password, ...(totpCode ? { totp_code: totpCode } : {}) },
		{ credentials: 'include' }
	);
};

export const userSignUp = async (
	name: string,
	email: string,
	password: string,
	profile_image_url: string
) => {
	return apiClient.post(
		'/auths/signup',
		{ name, email, password, profile_image_url },
		{ credentials: 'include' }
	);
};

export const userSignOut = async () => {
	return apiClient.get('/auths/signout', { credentials: 'include' });
};

// ---------------------------------------------------------------------------
// User management
// ---------------------------------------------------------------------------

export const addUser = async (
	token: string,
	name: string,
	email: string,
	password: string,
	role: string = 'pending'
) => {
	return apiClient.post('/auths/add', { name, email, password, role }, { token });
};

export const updateUserProfile = async (token: string, name: string, profileImageUrl: string) => {
	return apiClient.post(
		'/auths/update/profile',
		{ name, profile_image_url: profileImageUrl },
		{ token }
	);
};

export const updateUserPassword = async (token: string, password: string, newPassword: string) => {
	return apiClient.post(
		'/auths/update/password',
		{ password, new_password: newPassword },
		{ token }
	);
};

// ---------------------------------------------------------------------------
// Sign-up configuration
// ---------------------------------------------------------------------------

export const getSignUpEnabledStatus = async (token: string) => {
	return apiClient.get('/auths/signup/enabled', { token });
};

export const getDefaultUserRole = async (token: string) => {
	return apiClient.get('/auths/signup/user/role', { token });
};

export const updateDefaultUserRole = async (token: string, role: string) => {
	return apiClient.post('/auths/signup/user/role', { role }, { token });
};

export const toggleSignUpEnabledStatus = async (token: string) => {
	return apiClient.get('/auths/signup/enabled/toggle', { token });
};

// ---------------------------------------------------------------------------
// Token & API key
// ---------------------------------------------------------------------------

export const getJWTExpiresDuration = async (token: string) => {
	return apiClient.get('/auths/token/expires', { token });
};

export const updateJWTExpiresDuration = async (token: string, duration: string) => {
	return apiClient.post('/auths/token/expires/update', { duration }, { token });
};

export const createAPIKey = async (token: string) => {
	const res = await apiClient.post<{ api_key: string }>('/auths/api_key', undefined, { token });
	return res.api_key;
};

export const getAPIKey = async (token: string) => {
	const res = await apiClient.get<{ api_key: string }>('/auths/api_key', { token });
	return res.api_key;
};

export const deleteAPIKey = async (token: string) => {
	return apiClient.del('/auths/api_key', undefined, { token });
};

// ---------------------------------------------------------------------------
// Session lifecycle
// ---------------------------------------------------------------------------

let _isTerminating = false;
let _isUnauthorizedInterceptorInstalled = false;
let _sessionVerification: Promise<boolean> | null = null;

export const isSessionTerminating = () => _isTerminating;

export const terminateSession = async (options?: { redirect?: boolean }) => {
	if (_isTerminating) return;
	_isTerminating = true;

	const shouldRedirect = options?.redirect ?? true;

	try {
		await userSignOut();
	} catch (e) {
		logger.warn('auth', 'Server-side signout failed (session may already be expired)', e);
	}

	const stores = await import('$lib/stores');

	try {
		let socketInstance: { disconnect: () => void } | null = null;
		stores.socket.subscribe((s) => {
			socketInstance = s as { disconnect: () => void } | null;
		})();
		if (socketInstance) {
			socketInstance.disconnect();
		}
		stores.socket.set(null);
	} catch (e) {
		logger.warn('auth', 'Socket disconnect failed', e);
	}

	try {
		let ttsWorkerInstance: { worker: { terminate: () => void } } | null = null;
		stores.TTSWorker.subscribe((w) => {
			ttsWorkerInstance = w as { worker: { terminate: () => void } } | null;
		})();
		if (ttsWorkerInstance?.worker) {
			ttsWorkerInstance.worker.terminate();
		}
		stores.TTSWorker.set(null);
	} catch (e) {
		logger.warn('auth', 'TTSWorker terminate failed', e);
	}

	stores.user.set(undefined);
	stores.config.set(undefined);
	stores.models.set([]);
	stores.chats.set(null);
	stores.tags.set([]);
	stores.pinnedChats.set([]);
	stores.prompts.set(null);
	stores.knowledge.set(null);
	stores.tools.set(null);
	stores.functions.set(null);
	stores.banners.set([]);
	stores.settings.set({});
	stores.activeUserIds.set(null);
	stores.USAGE_POOL.set(null);
	stores.toolServers.set([]);
	stores.showSettings.set(false);
	stores.showArchivedChats.set(false);
	stores.showChangelog.set(false);
	stores.showControls.set(false);
	stores.showOverview.set(false);
	stores.showArtifacts.set(false);
	stores.showCallOverlay.set(false);
	stores.temporaryChatEnabled.set(false);

	try {
		localStorage.clear();
	} catch {
		const keys = ['token', 'settings', 'theme', 'locale', 'dismissedUpdateToast'];
		keys.forEach((key) => {
			try {
				localStorage.removeItem(key);
			} catch {
				// ignore per-key removal failure
			}
		});
	}

	try {
		sessionStorage.clear();
	} catch {
		// ignore sessionStorage clear failure
	}

	_isTerminating = false;

	if (shouldRedirect) {
		window.location.replace('/auth');
	}
};

const requestPathname = (url: string) => {
	try {
		return new URL(url, window.location.origin).pathname;
	} catch {
		return url;
	}
};

const isSessionEndpoint = (url: string) => {
	const pathname = requestPathname(url).replace(/\/$/, '');
	return pathname === '/api/v1/auths';
};

const verifySessionAfterUnauthorizedResponse = async (): Promise<boolean> => {
	if (_sessionVerification) return _sessionVerification;

	_sessionVerification = getSessionUser('')
		.then(() => true)
		.catch((error) => {
			logger.warn('auth', 'Session verification after an API 401 failed', error);
			return false;
		})
		.finally(() => {
			_sessionVerification = null;
		});

	return _sessionVerification;
};

export const installUnauthorizedInterceptor = () => {
	if (_isUnauthorizedInterceptorInstalled) return;
	_isUnauthorizedInterceptorInstalled = true;

	const originalFetch = window.fetch;

	window.fetch = async (...args) => {
		const response = await originalFetch.apply(window, args);

		if (response.status === 401 && !_isTerminating) {
			const url = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url;

			const isApi = typeof url === 'string' && url.includes('/api/');
			const isAuthFlow =
				typeof url === 'string' && /\/(auths|auth)\/(signin|signup|ldap|signout)/.test(url);
			const onAuthPage = typeof window !== 'undefined' && window.location?.pathname === '/auth';

			if (isApi && !isAuthFlow && !onAuthPage) {
				if (isSessionEndpoint(url)) {
					logger.warn('auth', 'Session validation returned 401 - terminating session');
					void terminateSession();
				} else {
					// A 401 from a proxied model provider or a resource permission check is
					// not proof that the browser session expired. Verify the cookie against
					// the dedicated session endpoint before clearing all application state.
					void verifySessionAfterUnauthorizedResponse().then((sessionIsValid) => {
						if (!sessionIsValid && !_isTerminating) {
							logger.warn('auth', `Session verification failed after 401 from ${url}`);
							void terminateSession();
						}
					});
				}
			}
		}

		return response;
	};
};

// ---------------------------------------------------------------------------
// Account management
// ---------------------------------------------------------------------------

export const unlockUserAccount = async (token: string, userId: string) => {
	return apiClient.post(`/users/${userId}/unlock`, undefined, { token });
};

export const uploadLogo = async (token: string, file: File) => {
	const formData = new FormData();
	formData.append('file', file);
	return apiClient.post('/auths/admin/logo', formData, { token });
};

export const deleteLogo = async (token: string) => {
	return apiClient.del('/auths/admin/logo', undefined, { token });
};

export const getUserLockoutStatuses = async (token: string) => {
	return apiClient.get('/users/lockout-statuses', { token });
};

// ---------------------------------------------------------------------------
// MFA / TOTP
// ---------------------------------------------------------------------------

export const mfaStatus = async (token: string) => {
	return apiClient.get<{ enabled: boolean; backup_codes_remaining: number }>('/auths/mfa/status', {
		token
	});
};

export const mfaEnroll = async (token: string) => {
	return apiClient.post<{
		secret: string;
		provisioning_uri: string;
		issuer: string;
		qr_svg: string | null;
	}>('/auths/mfa/enroll', undefined, { token });
};

export const mfaVerify = async (token: string, code: string) => {
	return apiClient.post<{ backup_codes: string[] }>('/auths/mfa/verify', { code }, { token });
};

export const mfaDisable = async (token: string, code: string) => {
	return apiClient.post<{ success: boolean }>('/auths/mfa/disable', { code }, { token });
};
