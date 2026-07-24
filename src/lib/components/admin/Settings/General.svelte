<script lang="ts">
	/**
	 * Admin General Settings
	 *
	 * Server-wide configuration including branding, authentication,
	 * default user roles, JWT expiration, and LDAP integration.
	 *
	 * Controls are organized into collapsible groups (SettingsSection): everyday
	 * groups (Branding, Authentication & Access, Features) stay open, while advanced
	 * or rarely-touched groups (API Keys, LDAP, URLs & Webhooks, About) start collapsed.
	 */
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';

	import { getVersionUpdates, getWebhookUrl, updateWebhookUrl } from '$lib/apis';
	import {
		getAdminConfig,
		getLdapConfig,
		getLdapServer,
		updateAdminConfig,
		updateLdapConfig,
		updateLdapServer,
		uploadLogo,
		deleteLogo
	} from '$lib/apis/auths';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Select } from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import SettingsSection from './SettingsSection.svelte';
	import { APP_BUILD_HASH, APP_VERSION } from '$lib/constants';
	import { config, APP_NAME_STORE } from '$lib/stores';
	import { compareVersion } from '$lib/utils';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Callback invoked after settings are successfully saved */
		saveHandler: () => void;
	}

	let { saveHandler }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	// --- Version tracking ---
	let updateAvailable = $state<number | null>(null);
	let version = $state({ current: '', latest: '' });

	// --- Admin configuration ---
	let adminConfig = $state<Record<string, unknown> | null>(null);
	let webhookUrl = $state('');

	// --- Logo management ---
	let logoInputElement: HTMLInputElement = $state();
	let logoPreviewUrl: string = $state('');

	// --- LDAP configuration ---
	let ENABLE_LDAP = $state(false);
	let LDAP_SERVER = $state({
		label: '',
		host: '',
		port: '',
		attribute_for_mail: 'mail',
		attribute_for_username: 'uid',
		app_dn: '',
		app_dn_password: '',
		search_base: '',
		search_filters: '',
		use_tls: false,
		certificate_path: '',
		ciphers: ''
	});

	/** LDAP section starts collapsed unless LDAP is already enabled (set on load). */
	let ldapOpen = $state(false);

	/** Check for available version updates */
	const checkForVersionUpdates = async () => {
		updateAvailable = null;
		version = await getVersionUpdates('').catch(() => ({
			current: APP_VERSION,
			latest: APP_VERSION
		}));
		updateAvailable = compareVersion(version.latest, version.current);
	};

	/** Persist LDAP server configuration */
	const updateLdapServerHandler = async () => {
		if (!ENABLE_LDAP) return;
		const res = await updateLdapServer('', LDAP_SERVER).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('LDAP server updated'));
		}
	};

	/** Save all general settings */
	const updateHandler = async () => {
		webhookUrl = await updateWebhookUrl('', webhookUrl);
		const res = await updateAdminConfig('', adminConfig);
		await updateLdapServerHandler();

		if (res) {
			if (adminConfig.name) {
				APP_NAME_STORE.set(adminConfig.name);
			}
			saveHandler();
		} else {
			toast.error($i18n.t('Failed to update settings'));
		}
	};

	/** Handle logo file upload */
	const uploadLogoHandler = async () => {
		const logoInputFile = logoInputElement.files?.[0];
		if (!logoInputFile) return;

		const res = await uploadLogo('', logoInputFile).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			adminConfig.logo_url = res.logo_url;
			logoPreviewUrl = res.logo_url;
			config.set({ ...get(config), logo_url: `${res.logo_url}?t=${Date.now()}` });
			toast.success($i18n.t('Logo updated successfully'));
		}
	};

	/** Handle logo removal */
	const deleteLogoHandler = async () => {
		const res = await deleteLogo('').catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			adminConfig.logo_url = '';
			logoPreviewUrl = '';
			config.set({ ...get(config), logo_url: '' });
			toast.success($i18n.t('Logo removed'));
		}
	};

	/** Trigger the hidden file input */
	const triggerLogoUpload = () => logoInputElement.click();

	/** Toggle LDAP and persist the config change */
	const handleLdapToggle = async () => {
		await updateLdapConfig('', ENABLE_LDAP);
	};

	onMount(async () => {
		checkForVersionUpdates();

		await Promise.all([
			(async () => {
				adminConfig = await getAdminConfig('');
				logoPreviewUrl = adminConfig?.logo_url || '';
			})(),
			(async () => {
				webhookUrl = await getWebhookUrl('');
			})(),
			(async () => {
				LDAP_SERVER = await getLdapServer('');
			})()
		]);

		const ldapConfig = await getLdapConfig('');
		ENABLE_LDAP = ldapConfig.ENABLE_LDAP;
		ldapOpen = ENABLE_LDAP;
	});
</script>

<form class="flex flex-col h-full justify-between text-sm" onsubmit={preventDefault(updateHandler)}>
	<div class="mt-0.5 overflow-y-scroll scrollbar-hidden h-full">
		<div class="mb-2.5">
			<InfoCallout>
				{$i18n.t(
					'Configure server-wide settings here, including branding, authentication, default user roles, JWT expiration, and LDAP integration.'
				)}
			</InfoCallout>
		</div>

		{#if adminConfig !== null}
			<!-- Branding -->
			<SettingsSection title={$i18n.t('Branding')}>
				<Field
					class="mb-2.5"
					label={$i18n.t('Logo')}
					helper={$i18n.t(
						'Upload a custom logo for your instance. If not set, the default logo will be used.'
					)}
				>
					<div class="flex items-center gap-3">
						<div class="shrink-0">
							<img
								src={logoPreviewUrl || '/static/favicon.png'}
								alt="logo"
								class="size-16 rounded-xl object-cover"
							/>
						</div>
						<div class="flex flex-col gap-1.5">
							<input
								bind:this={logoInputElement}
								type="file"
								accept="image/*"
								hidden
								onchange={uploadLogoHandler}
							/>
							<Button variant="secondary" size="sm" type="button" onclick={triggerLogoUpload}
								>{$i18n.t('Upload Logo')}</Button
							>
							{#if logoPreviewUrl}
								<Button
									variant="ghost"
									size="sm"
									type="button"
									class="text-destructive hover:bg-destructive/10"
									onclick={deleteLogoHandler}>{$i18n.t('Remove')}</Button
								>
							{/if}
						</div>
					</div>
				</Field>

				<Field
					label={$i18n.t('Browser Title')}
					helper={$i18n.t('This title will appear in the browser tab.')}
				>
					<Input
						size="sm"
						type="text"
						placeholder={$i18n.t('Enter a title for the browser tab')}
						bind:value={adminConfig.name}
					/>
				</Field>
			</SettingsSection>

			<!-- Authentication & Access -->
			<SettingsSection title={$i18n.t('Authentication & Access')}>
				<Field inline separator label={$i18n.t('Default User Role')}>
					<Select
						class="w-44"
						bind:value={adminConfig.DEFAULT_USER_ROLE}
						items={[
							{ value: 'pending', label: $i18n.t('pending') },
							{ value: 'user', label: $i18n.t('user') },
							{ value: 'admin', label: $i18n.t('admin') }
						]}
					/>
				</Field>

				<Field inline separator label={$i18n.t('Enable New Sign Ups')}>
					<Switch bind:state={adminConfig.ENABLE_SIGNUP} />
				</Field>

				<Field inline separator label={$i18n.t('Show Admin Details in Account Pending Overlay')}>
					<Switch bind:state={adminConfig.SHOW_ADMIN_DETAILS} />
				</Field>

				<Field label={$i18n.t('JWT Expiration')}>
					<Input
						size="sm"
						type="text"
						placeholder={$i18n.t('e.g.) "30m","1h", "10d". ')}
						bind:value={adminConfig.JWT_EXPIRES_IN}
					/>
					<p class="mt-1 text-xs text-muted-foreground">
						{$i18n.t('Valid time units:')}
						<span class="font-medium text-foreground">
							{$i18n.t("'s', 'm', 'h', 'd', 'w' or '-1' for no expiration.")}
						</span>
					</p>
				</Field>
			</SettingsSection>

			<!-- API Keys (advanced) -->
			<SettingsSection title={$i18n.t('API Keys')} open={false}>
				<Field inline separator label={$i18n.t('Enable API Key')}>
					<Switch bind:state={adminConfig.ENABLE_API_KEY} />
				</Field>

				{#if adminConfig?.ENABLE_API_KEY}
					<Field inline separator label={$i18n.t('API Key Endpoint Restrictions')}>
						<Switch bind:state={adminConfig.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS} />
					</Field>

					{#if adminConfig?.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS}
						<Field label={$i18n.t('Allowed Endpoints')}>
							<Input
								size="sm"
								type="text"
								placeholder="e.g.) /api/v1/messages, /api/v1/channels"
								bind:value={adminConfig.API_KEY_ALLOWED_ENDPOINTS}
							/>
							<p class="mt-1 text-xs text-muted-foreground">
								<a
									href="https://github.com/bccard-ai/bcgpt-webui"
									target="_blank"
									class="font-medium text-primary underline"
								>
									{$i18n.t('To learn more about available endpoints, visit our documentation.')}
								</a>
							</p>
						</Field>
					{/if}
				{/if}
			</SettingsSection>

			<!-- LDAP Integration (advanced; auto-opens when enabled) -->
			<SettingsSection title={$i18n.t('LDAP')} bind:open={ldapOpen}>
				<Field inline label={$i18n.t('Enable LDAP')}>
					<Switch bind:state={ENABLE_LDAP} onchange={handleLdapToggle} />
				</Field>

				{#if ENABLE_LDAP}
					<div class="flex flex-col gap-3 mt-2">
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Label')}>
								<Input
									size="sm"
									required
									placeholder={$i18n.t('Enter server label')}
									bind:value={LDAP_SERVER.label}
								/>
							</Field>
							<div class="w-full"></div>
						</div>
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Host')}>
								<Input
									size="sm"
									required
									placeholder={$i18n.t('Enter server host')}
									bind:value={LDAP_SERVER.host}
								/>
							</Field>
							<Field class="w-full" label={$i18n.t('Port')}>
								<Tooltip
									placement="top-start"
									content={$i18n.t('Default to 389 or 636 if TLS is enabled')}
								>
									<Input
										size="sm"
										type="number"
										placeholder={$i18n.t('Enter server port')}
										bind:value={LDAP_SERVER.port}
									/>
								</Tooltip>
							</Field>
						</div>
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Application DN')}>
								<Tooltip
									content={$i18n.t('The Application Account DN you bind with for search')}
									placement="top-start"
								>
									<Input
										size="sm"
										required
										placeholder={$i18n.t('Enter Application DN')}
										bind:value={LDAP_SERVER.app_dn}
									/>
								</Tooltip>
							</Field>
							<Field class="w-full" label={$i18n.t('Application DN Password')}>
								<SensitiveInput
									placeholder={$i18n.t('Enter Application DN Password')}
									bind:value={LDAP_SERVER.app_dn_password}
								/>
							</Field>
						</div>
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Attribute for Mail')}>
								<Tooltip
									content={$i18n.t(
										'The LDAP attribute that maps to the mail that users use to sign in.'
									)}
									placement="top-start"
								>
									<Input
										size="sm"
										required
										placeholder={$i18n.t('Example: mail')}
										bind:value={LDAP_SERVER.attribute_for_mail}
									/>
								</Tooltip>
							</Field>
						</div>
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Attribute for Username')}>
								<Tooltip
									content={$i18n.t(
										'The LDAP attribute that maps to the username that users use to sign in.'
									)}
									placement="top-start"
								>
									<Input
										size="sm"
										required
										placeholder={$i18n.t('Example: sAMAccountName or uid or userPrincipalName')}
										bind:value={LDAP_SERVER.attribute_for_username}
									/>
								</Tooltip>
							</Field>
						</div>
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Search Base')}>
								<Tooltip content={$i18n.t('The base to search for users')} placement="top-start">
									<Input
										size="sm"
										required
										placeholder={$i18n.t('Example: ou=users,dc=foo,dc=example')}
										bind:value={LDAP_SERVER.search_base}
									/>
								</Tooltip>
							</Field>
						</div>
						<div class="flex w-full gap-2">
							<Field class="w-full" label={$i18n.t('Search Filters')}>
								<Input
									size="sm"
									placeholder={$i18n.t('Example: (&(objectClass=inetOrgPerson)(uid=%s))')}
									bind:value={LDAP_SERVER.search_filters}
								/>
							</Field>
						</div>
						<p class="text-xs text-muted-foreground">
							<a
								class="font-medium text-primary underline"
								href="https://ldap.com/ldap-filters/"
								target="_blank"
							>
								{$i18n.t('Click here for filter guides.')}
							</a>
						</p>
						<div>
							<Field inline label={$i18n.t('TLS')}>
								<Switch bind:state={LDAP_SERVER.use_tls} />
							</Field>
							{#if LDAP_SERVER.use_tls}
								<div class="flex flex-col gap-3 mt-2">
									<div class="flex w-full gap-2">
										<Field class="w-full" label={$i18n.t('Certificate Path')}>
											<Input
												size="sm"
												placeholder={$i18n.t('Enter certificate path')}
												bind:value={LDAP_SERVER.certificate_path}
											/>
										</Field>
									</div>
									<div class="flex w-full gap-2">
										<Field class="w-full" label={$i18n.t('Ciphers')}>
											<Tooltip content={$i18n.t('Default to ALL')} placement="top-start">
												<Input
													size="sm"
													placeholder={$i18n.t('Example: ALL')}
													bind:value={LDAP_SERVER.ciphers}
												/>
											</Tooltip>
										</Field>
										<div class="w-full"></div>
									</div>
								</div>
							{/if}
						</div>
					</div>
				{/if}
			</SettingsSection>

			<!-- Features -->
			<SettingsSection title={$i18n.t('Features')}>
				<Field inline separator label={$i18n.t('Enable Community Sharing')}>
					<Switch bind:state={adminConfig.ENABLE_COMMUNITY_SHARING} />
				</Field>

				<Field inline separator label={$i18n.t('Enable Message Rating')}>
					<Switch bind:state={adminConfig.ENABLE_MESSAGE_RATING} />
				</Field>

				<Field inline separator label={$i18n.t('User Webhooks')}>
					<Switch bind:state={adminConfig.ENABLE_USER_WEBHOOKS} />
				</Field>
			</SettingsSection>

			<!-- URLs & Webhooks (advanced) -->
			<SettingsSection title={$i18n.t('URLs & Webhooks')} open={false}>
				<Field
					class="mb-2.5"
					label={$i18n.t('WebUI URL')}
					helper={$i18n.t(
						'Enter the public URL of your WebUI. This URL will be used to generate links in the notifications.'
					)}
				>
					<Input
						size="sm"
						type="text"
						placeholder="e.g.) &quot;http://localhost:3000&quot;"
						bind:value={adminConfig.BCGPT_URL}
					/>
				</Field>

				<Field label={$i18n.t('Webhook URL')}>
					<Input
						size="sm"
						type="text"
						placeholder="https://example.com/webhook"
						bind:value={webhookUrl}
					/>
				</Field>
			</SettingsSection>

			<!-- About -->
			<SettingsSection title={$i18n.t('About')} open={false}>
				<Field inline label={$i18n.t('Version')}>
					<div class="text-xs text-muted-foreground">
						<div class="flex gap-1 items-center">
							<Tooltip content={APP_BUILD_HASH}>
								v{APP_VERSION}
							</Tooltip>
							{#if updateAvailable}
								<span class="text-amber-500 dark:text-amber-400 font-medium">
									→ v{version.latest}
								</span>
							{/if}
						</div>
					</div>
				</Field>
			</SettingsSection>
		{/if}
	</div>

	<div class="flex justify-end pt-3">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
