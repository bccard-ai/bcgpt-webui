<!-- BCGPT WebUI - Auth Page: Login, signup, LDAP, and OAuth authentication -->
<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';

	import { getBackendConfig } from '$lib/apis';
	import { ldapUserSignIn, getSessionUser, userSignIn, userSignUp } from '$lib/apis/auths';

	import { APP_BASE_URL } from '$lib/constants';
	import { APP_NAME_STORE, config, user, socket } from '$lib/stores';

	import { generateInitialsImage } from '$lib/utils';

	import SlideShow from '$lib/components/common/SlideShow.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import OnBoarding from '$lib/components/OnBoarding.svelte';
	import Marquee from '$lib/components/common/Marquee.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let loaded = $state(false);

	let mode = $state($config?.features.enable_ldap ? 'ldap' : 'signin');

	let name = $state('');
	let email = $state('');
	let password = $state('');

	let ldapUsername = $state('');

	let accountLocked = $state(false);
	let accountLockedMessage = $state('');

	let mfaRequired = $state(false);
	let totpCode = $state('');

	const querystringValue = (key) => {
		const querystring = window.location.search;
		const urlParams = new URLSearchParams(querystring);
		return urlParams.get(key);
	};

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			toast.success($i18n.t(`You're now logged in.`));

			try {
				get(socket)?.emit('user-join', { auth: { token: sessionUser.token } });
			} catch {
				// socket may not be initialised yet (e.g. page-reload recovery)
			}
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			const redirectPath = querystringValue('redirect') || '/';
			goto(resolve(redirectPath as unknown as '/'));
		}
	};

	const signInHandler = async () => {
		accountLocked = false;
		accountLockedMessage = '';

		const sessionUser = await userSignIn(email, password, totpCode || undefined).catch((error) => {
			const errorStr = String(error);
			if (errorStr.includes('mfa_required')) {
				mfaRequired = true;
				return null;
			}
			if (errorStr.includes('account has been locked')) {
				accountLocked = true;
				accountLockedMessage = errorStr;
			}
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		const sessionUser = await userSignUp(name, email, password, generateInitialsImage(name)).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		if (mode === 'ldap') {
			await ldapSignInHandler();
		} else if (mode === 'signin') {
			await signInHandler();
		} else {
			await signUpHandler();
		}
	};

	const checkOauthCallback = async () => {
		if (!page.url.hash) {
			return;
		}
		const hash = page.url.hash.substring(1);
		if (!hash) {
			return;
		}
		const params = new URLSearchParams(hash);
		const token = params.get('token');
		if (!token) {
			return;
		}
		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!sessionUser) {
			return;
		}
		await setSessionUser(sessionUser);
	};

	let onboarding = $state(false);

	async function setLogoImage() {
		await tick();
		const logo = document.getElementById('logo');

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = '/static/favicon-dark.png';

				darkImage.onload = () => {
					logo.src = '/static/favicon-dark.png';
					logo.style.filter = ''; // Ensure no inversion is applied if favicon-dark.png exists
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)'; // Invert image if favicon-dark.png is missing
				};
			}
		}
	}

	onMount(async () => {
		if (get(user) !== undefined) {
			const redirectPath = querystringValue('redirect') || '/';
			goto(resolve(redirectPath as unknown as '/'));
			return;
		}

		// If the Svelte store was reset (e.g. Vite HMR page reload) but the
		// HttpOnly session cookie is still valid, recover the session
		// automatically instead of showing the login form again.
		const cookieSession = await getSessionUser('').catch(() => null);
		if (cookieSession) {
			await setSessionUser(cookieSession);
			return;
		}

		await checkOauthCallback();

		loaded = true;
		setLogoImage();

		if (
			(get(config)?.features.auth_trusted_header ?? false) ||
			get(config)?.features.auth === false
		) {
			await signInHandler();
		} else {
			onboarding = get(config)?.onboarding ?? false;
		}
	});
</script>

<svelte:head>
	<title>
		{`${$APP_NAME_STORE}`}
	</title>
</svelte:head>

<OnBoarding
	bind:show={onboarding}
	getStartedHandler={() => {
		onboarding = false;
		mode = $config?.features.enable_ldap ? 'ldap' : 'signup';
	}}
/>

<div class="w-full h-screen max-h-[100dvh] text-white relative">
	<div class="w-full h-full absolute top-0 left-0 bg-white dark:bg-black"></div>

	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region"></div>

	{#if loaded}
		<SlideShow duration={15000} />

		<div class="fixed m-10 z-50">
			<div class="flex space-x-2">
				<div class=" self-center">
					<img
						id="logo"
						crossorigin="anonymous"
						src={$config?.logo_url || '/static/splash.png'}
						class="w-6 rounded-full"
						alt="logo"
					/>
				</div>
			</div>
		</div>

		<div
			class="fixed bg-transparent min-h-screen w-full flex justify-center font-primary z-50 text-black dark:text-white text-white"
		>
			<div class="w-full sm:max-w-md px-10 min-h-screen flex flex-col text-center">
				{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
					<div class=" my-auto pb-10 w-full">
						<div
							class="flex items-center justify-center gap-3 text-xl sm:text-2xl text-center font-semibold dark:text-gray-200"
						>
							<div>
								{$i18n.t('Signing in to {{APP_NAME_STORE}}', { APP_NAME_STORE: $APP_NAME_STORE })}
							</div>

							<div>
								<Spinner />
							</div>
						</div>
					</div>
				{:else}
					<div class="  my-auto pb-10 w-full dark:text-gray-100">
						<form
							class=" flex flex-col justify-center"
							onsubmit={(e: SubmitEvent) => {
								e.preventDefault();
								submitHandler();
							}}
						>
							<div class="mb-1">
								<div class=" text-2xl font-medium">
									{#if $config?.onboarding ?? false}
										{$i18n.t(`Get started with {{APP_NAME_STORE}}`, {
											APP_NAME_STORE: $APP_NAME_STORE
										})}
										<!-- {:else if mode === 'ldap'}
										{$i18n.t(`Sign in to {{APP_NAME_STORE}} with LDAP`, { APP_NAME_STORE: $APP_NAME_STORE })}
									{:else if mode === 'signin'}
										{$i18n.t(`Sign in to {{APP_NAME_STORE}}`, { APP_NAME_STORE: $APP_NAME_STORE })}
									{:else}
										{$i18n.t(`Sign up to {{APP_NAME_STORE}}`, { APP_NAME_STORE: $APP_NAME_STORE })} -->
									{/if}
								</div>

								<div class="text-2xl text-white">
									<Marquee
										duration={5000}
										words={[
											$i18n.t('Into a world of infinite knowledge'),
											$i18n.t('Opening new horizons of innovation'),
											$i18n.t('The start of a challenge toward the future'),
											$i18n.t('A moment of profound insight'),
											$i18n.t('A journey of discovery beyond boundaries'),
											$i18n.t('The starting point of innovative thinking'),
											$i18n.t('Opening a new chapter of knowledge'),
											$i18n.t('Exploring infinite possibilities'),
											$i18n.t('A moment of creative innovation'),
											$i18n.t('Insight that leads the future')
										]}
									/>
								</div>
								<div
									class="text-6xl font-bold animate-rainbow-text bg-gradient-to-r from-cyan-400 via-rose-400 via-yellow-300 via-emerald-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent bg-[length:200%]"
								>
									BCGPT
								</div>
								<div class="text-xs text-white">BC Gerative Pre-trained Transformer</div>

								{#if $config?.onboarding ?? false}
									<div class=" mt-1 text-xs font-medium text-white">
										ⓘ {$APP_NAME_STORE}
										{$i18n.t(
											'does not make any external connections, and your data stays securely on your locally hosted server.'
										)}
									</div>
								{/if}
							</div>

							{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
								<div class="flex flex-col mt-4">
									{#if mode === 'signup'}
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Name')}</div>
											<input
												bind:value={name}
												type="text"
												class="my-0.5 w-full text-sm border-1 border-gray-300 rounded-md p-2 bg-gray-50 text-black"
												autocomplete="name"
												placeholder={$i18n.t('Enter Your Full Name')}
												required
											/>
										</div>
									{/if}

									{#if mode === 'ldap'}
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Username')}</div>
											<input
												bind:value={ldapUsername}
												type="text"
												class="my-0.5 w-full text-sm border-1 border-gray-300 rounded-md p-2 bg-gray-50 text-black"
												autocomplete="username"
												name="username"
												placeholder={$i18n.t('Enter Your Username')}
												required
											/>
										</div>
									{:else}
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Email')}</div>
											<input
												bind:value={email}
												type="email"
												class="my-0.5 w-full text-sm border-1 border-gray-300 rounded-md p-2 bg-gray-50 text-black"
												autocomplete="email"
												name="email"
												placeholder={$i18n.t('Enter Your Email')}
												required
											/>
										</div>
									{/if}

									<div>
										<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Password')}</div>

										<input
											bind:value={password}
											type="password"
											class="my-0.5 w-full text-sm border-1 border-gray-300 rounded-md p-2 bg-gray-50 text-black"
											placeholder={$i18n.t('Enter Your Password')}
											autocomplete="current-password"
											name="current-password"
											required
										/>
									</div>
								</div>
							{/if}

							{#if mfaRequired && mode === 'signin'}
								<div class="flex flex-col mt-4">
									<div class="mb-2">
										<div class="text-sm font-medium text-left mb-1">
											{$i18n.t('Two-factor code')}
										</div>
										<input
											bind:value={totpCode}
											type="text"
											inputmode="numeric"
											maxlength={8}
											autocomplete="one-time-code"
											class="my-0.5 w-full text-sm border-1 border-gray-300 rounded-md p-2 bg-gray-50 text-black"
											placeholder={$i18n.t('6-digit code from your authenticator app')}
											onkeydown={(e) => {
												if (e.key === 'Enter') {
													e.preventDefault();
													signInHandler();
												}
											}}
										/>
									</div>
									<button
										class="bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										type="button"
										onclick={() => signInHandler()}
									>
										{$i18n.t('Verify')}
									</button>
								</div>
							{/if}

							<div class="mt-5">
								{#if accountLocked}
									<div
										class="mb-3 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"
									>
										<div class="flex items-start gap-2">
											<svg
												xmlns="http://www.w3.org/2000/svg"
												class="w-5 h-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
												/>
											</svg>
											<div>
												<div class="text-sm font-medium text-red-700 dark:text-red-300">
													{$i18n.t('Account Locked')}
												</div>
												<div class="text-xs text-red-600 dark:text-red-400 mt-0.5">
													{accountLockedMessage}
												</div>
											</div>
										</div>
									</div>
								{/if}

								{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
									{#if mode === 'ldap'}
										<button
											class="bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
											type="submit"
										>
											{$i18n.t('Authenticate')}
										</button>
									{:else}
										<button
											class="bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
											type="submit"
										>
											{mode === 'signin'
												? $i18n.t('Sign in')
												: ($config?.onboarding ?? false)
													? $i18n.t('Create Admin Account')
													: $i18n.t('Create Account')}
										</button>

										{#if $config?.features.enable_signup && !($config?.onboarding ?? false)}
											<div class=" mt-4 text-sm text-center">
												{mode === 'signin'
													? $i18n.t("Don't have an account?")
													: $i18n.t('Already have an account?')}

												<button
													class=" font-medium underline"
													type="button"
													onclick={() => {
														if (mode === 'signin') {
															mode = 'signup';
														} else {
															mode = 'signin';
														}
														mfaRequired = false;
														totpCode = '';
													}}
												>
													{mode === 'signin' ? $i18n.t('Sign up') : $i18n.t('Sign in')}
												</button>
											</div>
										{/if}
									{/if}
								{/if}
							</div>
						</form>

						{#if Object.keys($config?.oauth?.providers ?? {}).length > 0}
							<div class="inline-flex items-center justify-center w-full">
								<hr class="w-32 h-px my-4 border-0 dark:bg-gray-100/10 bg-gray-700/10" />
								{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
									<span
										class="px-3 text-sm font-medium text-gray-900 dark:text-white bg-transparent"
										>{$i18n.t('or')}</span
									>
								{/if}

								<hr class="w-32 h-px my-4 border-0 dark:bg-gray-100/10 bg-gray-700/10" />
							</div>
							<div class="flex flex-col space-y-2">
								{#if $config?.oauth?.providers?.google}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										onclick={() => {
											window.location.href = `${APP_BASE_URL}/oauth/google/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="size-6 mr-3">
											<path
												fill="#EA4335"
												d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
											/><path
												fill="#4285F4"
												d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
											/><path
												fill="#FBBC05"
												d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
											/><path
												fill="#34A853"
												d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
											/><path fill="none" d="M0 0h48v48H0z" />
										</svg>
										<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.microsoft}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										onclick={() => {
											window.location.href = `${APP_BASE_URL}/oauth/microsoft/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" class="size-6 mr-3">
											<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
												x="1"
												y="11"
												width="9"
												height="9"
												fill="#00a4ef"
											/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
												x="11"
												y="11"
												width="9"
												height="9"
												fill="#ffb900"
											/>
										</svg>
										<span>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.github}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										onclick={() => {
											window.location.href = `${APP_BASE_URL}/oauth/github/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-6 mr-3">
											<path
												fill="currentColor"
												d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.92 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57C20.565 21.795 24 17.31 24 12c0-6.63-5.37-12-12-12z"
											/>
										</svg>
										<span>{$i18n.t('Continue with {{provider}}', { provider: 'GitHub' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.oidc}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										onclick={() => {
											window.location.href = `${APP_BASE_URL}/oauth/oidc/login`;
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="1.5"
											stroke="currentColor"
											class="size-6 mr-3"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
											/>
										</svg>

										<span
											>{$i18n.t('Continue with {{provider}}', {
												provider: $config?.oauth?.providers?.oidc ?? 'SSO'
											})}</span
										>
									</button>
								{/if}
							</div>
						{/if}

						{#if $config?.features.enable_ldap && $config?.features.enable_login_form}
							<div class="mt-2">
								<button
									class="flex justify-center items-center text-xs w-full text-center underline"
									type="button"
									onclick={() => {
										if (mode === 'ldap')
											mode = ($config?.onboarding ?? false) ? 'signup' : 'signin';
										else mode = 'ldap';
										mfaRequired = false;
										totpCode = '';
									}}
								>
									<span
										>{mode === 'ldap'
											? $i18n.t('Continue with Email')
											: $i18n.t('Continue with LDAP')}</span
									>
								</button>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
