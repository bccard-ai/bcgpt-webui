<!-- BCGPT WebUI - Root Layout: Global app shell with auth, websocket, notifications -->
<script lang="ts">
	import { get } from 'svelte/store';
	import { logger } from '$lib/utils/logger';
	import { io } from 'socket.io-client';
	import { spring } from 'svelte/motion';

	let loadingProgress = spring(0, {
		stiffness: 0.05
	});

	import { onMount, tick, setContext } from 'svelte';
	import {
		config,
		user,
		settings,
		theme,
		APP_NAME_STORE,
		socket,
		activeUserIds,
		USAGE_POOL,
		chatId,
		chats,
		tags,
		temporaryChatEnabled,
		isLastActiveTab,
		isApp,
		appInfo,
		appData,
		toolServers
	} from '$lib/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Toaster, toast } from 'svelte-sonner';

	import { executeToolServer, getBackendConfig } from '$lib/apis';
	import {
		getSessionUser,
		terminateSession,
		installUnauthorizedInterceptor
	} from '$lib/apis/auths';

	import '../tailwind.css';
	import '../app.css';

	import 'tippy.js/dist/tippy.css';

	import { APP_BASE_URL } from '$lib/constants';
	import i18n, { initI18n, getLanguages, changeLanguage } from '$lib/i18n';
	import { bestMatchingLanguage } from '$lib/utils';
	import { getAllTags, updateChatEntryInList } from '$lib/apis/chats';
	import { createActiveTabSync, createResponsiveHandler } from './_lib/app-layout-helpers.svelte';
	import NotificationToast from '$lib/components/NotificationToast.svelte';
	import AppSidebar from '$lib/components/app/AppSidebar.svelte';
	import Skeleton from '$lib/components/common/Skeleton.svelte';
	import { chatCompletion } from '$lib/apis/openai';
	import type { SessionUser } from '$lib/types/stores';
	/**
	 * @typedef {Object} Props
	 * @property {import('svelte').Snippet} [children]
	 */

	/** @type {Props} */
	let { children } = $props();

	setContext('i18n', i18n);

	const bc = new BroadcastChannel('active-tab-channel');

	let loaded = $state(false);
	let sessionRefreshTimeout: ReturnType<typeof setTimeout> | null = null;
	let sessionRefreshInFlight = false;

	const clearSessionRefresh = () => {
		if (sessionRefreshTimeout !== null) {
			clearTimeout(sessionRefreshTimeout);
			sessionRefreshTimeout = null;
		}
	};

	const scheduleSessionRefresh = (sessionUser: SessionUser) => {
		clearSessionRefresh();

		const expiresAtMs = (sessionUser.expires_at ?? 0) * 1000;
		const refreshDelayMs = expiresAtMs
			? Math.max(30_000, Math.min(12 * 60 * 60_000, expiresAtMs - Date.now() - 60_000))
			: 15 * 60_000;

		sessionRefreshTimeout = setTimeout(() => {
			void refreshSession();
		}, refreshDelayMs);
	};

	const refreshSession = async () => {
		if (sessionRefreshInFlight || !get(user)) return;
		sessionRefreshInFlight = true;

		try {
			const sessionUser = await getSessionUser('');
			await user.set(sessionUser);
			scheduleSessionRefresh(sessionUser);
		} catch (error) {
			// The unauthorized interceptor performs a definitive session check and
			// redirects only when the cookie itself is no longer valid.
			logger.warn('auth', 'Unable to refresh the active session', error);
		} finally {
			sessionRefreshInFlight = false;
		}
	};

	const setupSocket = async (enableWebsocket) => {
		const _socket = io(`${APP_BASE_URL}` || undefined, {
			reconnection: true,
			reconnectionDelay: 1000,
			reconnectionDelayMax: 5000,
			randomizationFactor: 0.5,
			path: '/ws/socket.io',
			transports: enableWebsocket ? ['websocket'] : ['polling', 'websocket'],
			auth: { token: '' }
		});

		await socket.set(_socket);

		_socket.on('connect_error', (_err) => {});

		_socket.on('connect', () => {});

		_socket.on('reconnect_attempt', (_attempt) => {});

		_socket.on('reconnect_failed', () => {});

		_socket.on('disconnect', (_reason, _details) => {});

		_socket.on('user-list', (data) => {
			activeUserIds.set(data.user_ids);
		});

		_socket.on('usage', (data) => {
			USAGE_POOL.set(data['models']);
		});
	};

	const executeTool = async (data, cb) => {
		const toolServer = get(toolServers)?.find((server) => server.url === data.server?.url);

		if (toolServer) {
			const res = await executeToolServer(
				toolServer.key,
				toolServer.url,
				data?.name,
				data?.params,
				toolServer
			);

			if (cb) {
				cb(structuredClone(res));
			}
		} else {
			if (cb) {
				cb(
					JSON.parse(
						JSON.stringify({
							error: 'Tool Server Not Found'
						})
					)
				);
			}
		}
	};

	const chatEventHandler = async (
		event: {
			chat_id: string;
			data?: { type?: string; data?: Record<string, unknown> };
			[key: string]: unknown;
		},
		cb: (...args: unknown[]) => void
	) => {
		let isFocused = document.visibilityState !== 'visible';
		if (window.electronAPI) {
			const res = await window.electronAPI.send({
				type: 'window:isFocused'
			});
			if (res) {
				isFocused = res.isFocused;
			}
		}

		await tick();
		const type = event?.data?.type ?? null;
		const data = (event?.data?.data ?? null) as Record<string, unknown> | null;

		if ((event.chat_id !== get(chatId) && !get(temporaryChatEnabled)) || isFocused) {
			if (type === 'chat:completion') {
				const { done, content, title } = (data ?? {}) as {
					done?: boolean;
					content: string;
					title: string;
				};

				if (done) {
					if (get(isLastActiveTab)) {
						if (get(settings)?.notificationEnabled ?? false) {
							new Notification(`${title} | BCGPT`, {
								body: content,
								icon: `/static/favicon.png`
							});
						}
					}

					toast.custom(NotificationToast, {
						componentProps: {
							onClick: () => {
								goto(resolve(`/c/${event.chat_id}`));
							},
							content: content,
							title: title
						},
						duration: 15000,
						unstyled: true
					});
				}
			} else if (type === 'chat:title') {
				chats.set(
					updateChatEntryInList(get(chats), event.chat_id, {
						title: data,
						updated_at: Date.now() / 1000
					})
				);
			} else if (type === 'chat:tags') {
				tags.set(await getAllTags(''));
			}
		} else if (data?.session_id === get(socket).id) {
			if (type === 'execute:tool') {
				executeTool(data, cb);
			} else if (type === 'request:chat:completion') {
				const { channel, form_data, model } = (data ?? {}) as {
					channel: string;
					form_data: Record<string, string>;
					model: { urlIdx?: number };
				};

				try {
					const directConnections = get(settings)?.directConnections ?? {};

					if (directConnections) {
						const urlIdx = model?.urlIdx;

						const OPENAI_API_URL = directConnections.OPENAI_API_BASE_URLS[urlIdx];
						const OPENAI_API_KEY = directConnections.OPENAI_API_KEYS[urlIdx];
						const API_CONFIG = directConnections.OPENAI_API_CONFIGS[urlIdx];

						try {
							if (API_CONFIG?.prefix_id) {
								const prefixId = API_CONFIG.prefix_id;
								form_data['model'] = form_data['model'].replace(`${prefixId}.`, ``);
							}

							const [res, _controller] = await chatCompletion(
								OPENAI_API_KEY,
								form_data,
								OPENAI_API_URL
							);

							if (res) {
								// raise if the response is not ok
								if (!res.ok) {
									throw await res.json();
								}

								if (form_data?.stream ?? false) {
									cb({
										status: true
									});

									// res will either be SSE or JSON
									const reader = res.body.getReader();
									const decoder = new TextDecoder();

									const processStream = async () => {
										while (true) {
											// Read data chunks from the response stream
											const { done, value } = await reader.read();
											if (done) {
												break;
											}

											// Decode the received chunk
											const chunk = decoder.decode(value, { stream: true });

											// Process lines within the chunk
											const lines = chunk.split('\n').filter((line) => line.trim() !== '');

											for (const line of lines) {
												get(socket)?.emit(channel, line);
											}
										}
									};

									// Process the stream in the background
									await processStream();
								} else {
									const data = await res.json();
									cb(data);
								}
							} else {
								throw new Error('An error occurred while fetching the completion');
							}
						} catch (error) {
							logger.error('layout', 'chatCompletion failed', undefined, error);
							cb(error);
						}
					}
				} catch (error) {
					logger.error('layout', 'chatCompletion failed', undefined, error);
					cb(error);
				} finally {
					get(socket).emit(channel, {
						done: true
					});
				}
			}
		}
	};

	const channelEventHandler = async (event: {
		channel_id: string;
		data?: { type?: string; data?: Record<string, unknown> };
		user?: { id?: string };
		channel?: { name?: string };
		[key: string]: unknown;
	}) => {
		if (event.data?.type === 'typing') {
			return;
		}

		// check url path
		const channel = page.url.pathname.includes(`/channels/${event.channel_id}`);

		let isFocused = document.visibilityState !== 'visible';
		if (window.electronAPI) {
			const res = await window.electronAPI.send({
				type: 'window:isFocused'
			});
			if (res) {
				isFocused = res.isFocused;
			}
		}

		if ((!channel || isFocused) && event?.user?.id !== get(user)?.id) {
			await tick();
			const type = event?.data?.type ?? null;
			const data = (event?.data?.data ?? null) as {
				content: string;
				user?: { name?: string; profile_image_url?: string };
			};

			if (type === 'message') {
				if (get(isLastActiveTab)) {
					if (get(settings)?.notificationEnabled ?? false) {
						new Notification(`${data?.user?.name} (#${event?.channel?.name}) | BCGPT`, {
							body: data?.content,
							icon: data?.user?.profile_image_url ?? `/static/favicon.png`
						});
					}
				}

				toast.custom(NotificationToast, {
					componentProps: {
						onClick: () => {
							goto(resolve(`/channels/${event.channel_id}`));
						},
						content: data?.content,
						title: event?.channel?.name
					},
					duration: 15000,
					unstyled: true
				});
			}
		}
	};

	onMount(async () => {
		installUnauthorizedInterceptor();
		window.addBootLog?.('Initializing runtime...', 'loading');

		if (typeof window !== 'undefined' && window.applyTheme) {
			window.applyTheme();
		}

		if (window?.electronAPI) {
			const info = await window.electronAPI.send({
				type: 'app:info'
			});

			if (info) {
				isApp.set(true);
				appInfo.set(info);

				const data = await window.electronAPI.send({
					type: 'app:data'
				});

				if (data) {
					appData.set(data);
				}
			}
		}

		const cleanupActiveTab = createActiveTabSync(bc);

		theme.set(localStorage.theme);

		const cleanupResize = createResponsiveHandler();
		const refreshOnVisibility = () => {
			if (document.visibilityState === 'visible') {
				void refreshSession();
			}
		};
		document.addEventListener('visibilitychange', refreshOnVisibility);

		user.subscribe((value) => {
			if (value) {
				get(socket)?.off('chat-events', chatEventHandler);
				get(socket)?.off('channel-events', channelEventHandler);

				get(socket)?.on('chat-events', chatEventHandler);
				get(socket)?.on('channel-events', channelEventHandler);
			} else {
				get(socket)?.off('chat-events', chatEventHandler);
				get(socket)?.off('channel-events', channelEventHandler);
			}
		});

		window.addBootLog?.('Fetching backend config...', 'loading');
		let backendConfig = null;
		try {
			const configController = new AbortController();
			const configTimeout = setTimeout(() => configController.abort(), 10000);
			backendConfig = await getBackendConfig(configController.signal);
			clearTimeout(configTimeout);
			window.addBootLog?.('Backend config loaded', 'done');
		} catch (error) {
			const errMsg =
				error?.name === 'AbortError'
					? 'Server response timed out (10s). Please make sure the backend server is running.'
					: `Backend connection failed: ${error?.message || error}`;
			window.addBootLog?.(errMsg, 'error');
			logger.error('layout', 'Error loading backend config', undefined, error);
		}

		initI18n(localStorage?.locale);
		window.addBootLog?.('Initializing i18n...', 'loading');
		if (!localStorage.locale) {
			try {
				const languages = await getLanguages();
				const browserLanguages = navigator.languages
					? navigator.languages
					: [navigator.language || navigator.userLanguage];
				const lang = backendConfig?.default_locale
					? backendConfig.default_locale
					: bestMatchingLanguage(languages, browserLanguages, 'en-US');
				changeLanguage(lang);
			} catch (error) {
				logger.error('layout', 'Error initializing language', undefined, error);
			}
		}
		window.addBootLog?.('i18n ready', 'done');

		if (backendConfig) {
			// Save Backend Status to Store
			await config.set(backendConfig);
			await APP_NAME_STORE.set(backendConfig.name);

			if (get(config)) {
				const isAuthPage = window.location.pathname.startsWith('/auth');

				window.addBootLog?.('Connecting websocket...', 'loading');
				await setupSocket(get(config).features?.enable_websocket ?? true);
				window.addBootLog?.('WebSocket connected', 'done');

				const currentUrl = `${window.location.pathname}${window.location.search}`;
				const encodedUrl = encodeURIComponent(currentUrl);

				// Skip auth check on the auth page — user isn't logged in yet,
				// and calling getSessionUser() would produce an unnecessary 401 error.
				if (isAuthPage) {
					window.addBootLog?.('Auth page detected, skipping session check', 'done');
				} else {
					// Try cookie-based authentication
					// Get Session User Info
					window.addBootLog?.('Authenticating session...', 'loading');
					const sessionUser = await getSessionUser('').catch((error) => {
						toast.error(`${error}`);
						return null;
					});

					if (sessionUser) {
						// Save Session User to Store
						get(socket).emit('user-join', { auth: { token: sessionUser.token } });

						await user.set(sessionUser);
						scheduleSessionRefresh(sessionUser);
						await config.set(await getBackendConfig());
						window.addBootLog?.('Session authenticated', 'done');
					} else {
						window.addBootLog?.('Session expired, redirecting...', 'error');
						await terminateSession({ redirect: false });
						await goto(resolve(`/auth?redirect=${encodedUrl}`));
					}
				}
			}
		} else {
			// Redirect to /error when Backend Not Detected
			window.bootFailed?.(
				$i18n.t('Cannot connect to the backend server'),
				$i18n.t(
					'Backend server is not responding.\n' +
						' - Docker: check container status with docker ps\n' +
						' - Local: verify bcgpt serve or npm run dev is running'
				)
			);
			await goto(resolve(`/error`));
		}

		window.addBootLog?.('Boot complete', 'done');

		await tick();

		if (
			document.documentElement.classList.contains('her') &&
			document.getElementById('progress-bar')
		) {
			loadingProgress.subscribe((value) => {
				const progressBar = document.getElementById('progress-bar');

				if (progressBar) {
					progressBar.style.width = `${value}%`;
				}
			});

			await loadingProgress.set(100);

			document.getElementById('splash-screen')?.remove();

			const audio = new Audio(`/audio/greeting.mp3`);
			const playAudio = () => {
				audio.play();
				document.removeEventListener('click', playAudio);
			};

			document.addEventListener('click', playAudio);

			loaded = true;
		} else {
			document.getElementById('splash-screen')?.remove();
			loaded = true;
		}

		return () => {
			clearSessionRefresh();
			document.removeEventListener('visibilitychange', refreshOnVisibility);
			cleanupResize();
			cleanupActiveTab();
			bc.close();
		};
	});
</script>

<svelte:head>
	<title>{$APP_NAME_STORE}</title>
	<link
		crossorigin="anonymous"
		rel="icon"
		href={$config?.logo_url
			? APP_BASE_URL + $config.logo_url
			: APP_BASE_URL + '/static/favicon.png'}
	/>
	<link
		crossorigin="anonymous"
		rel="shortcut icon"
		href={$config?.logo_url
			? APP_BASE_URL + $config.logo_url
			: APP_BASE_URL + '/static/favicon.ico'}
	/>

	<!-- rosepine themes have been disabled as it's not up to date with our latest version. -->
	<!-- feel free to make a PR to fix if anyone wants to see it return -->
	<!-- <link rel="stylesheet" type="text/css" href="/themes/rosepine.css" />
	<link rel="stylesheet" type="text/css" href="/themes/rosepine-dawn.css" /> -->
</svelte:head>

{#if loaded}
	{#if $isApp}
		<div class="flex flex-row h-screen">
			<AppSidebar />

			<div class="w-full flex-1 max-w-[calc(100%-4.5rem)]">
				{@render children?.()}
			</div>
		</div>
	{:else}
		{@render children?.()}
	{/if}
{:else}
	<div class="flex flex-row h-screen w-full">
		<!-- Sidebar skeleton -->
		<div class="min-w-[4.5rem] bg-gray-50 dark:bg-gray-950 flex gap-2.5 flex-col pt-8 items-center">
			<Skeleton variant="circle" width="2.75rem" />
			<div class="w-10 border-t border-gray-100 dark:border-gray-900"></div>
			{#each Array(5) as _, i (i)}
				<Skeleton variant="circle" width="2.75rem" />
			{/each}
		</div>

		<!-- Main content skeleton -->
		<div class="flex-1 flex flex-col h-full">
			<!-- Header skeleton -->
			<div
				class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-850"
			>
				<Skeleton width="8rem" height="1.5rem" />
				<div class="flex gap-3">
					<Skeleton variant="circle" width="2rem" />
					<Skeleton variant="circle" width="2rem" />
				</div>
			</div>

			<!-- Content area skeleton -->
			<div class="flex-1 flex flex-col items-center justify-center gap-4 p-6">
				<Skeleton width="12rem" height="2rem" />
				<Skeleton width="20rem" height="1rem" />
				<Skeleton width="16rem" height="1rem" />

				<div class="flex gap-3 mt-6">
					{#each Array(3) as _, i (i)}
						<div class="w-40 h-24">
							<Skeleton variant="rect" width="100%" height="100%" />
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
{/if}

<Toaster
	theme={$theme.includes('dark')
		? 'dark'
		: $theme === 'system'
			? window.matchMedia('(prefers-color-scheme: dark)').matches
				? 'dark'
				: 'light'
			: 'light'}
	richColors
	position="top-right"
/>
