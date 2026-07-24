<script lang="ts">
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';

	import { onMount, getContext } from 'svelte';
	import { getToolServersData } from '$lib/apis';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { settings, toolServers } from '$lib/stores';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Connection from './Tools/Connection.svelte';

	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	type ToolServer = {
		url: string;
		key: string;
		config?: Record<string, unknown>;
	};

	interface Props {
		saveSettings: (settings: { toolServers: ToolServer[] | null }) => void | Promise<void>;
	}

	let { saveSettings }: Props = $props();

	let servers: ToolServer[] | null = $state(null);
	let showConnectionModal = $state(false);

	const addConnectionHandler = async (server: ToolServer) => {
		if (!servers) {
			servers = [];
		}

		servers = [...servers, server];
		await updateHandler();
	};

	const updateHandler = async () => {
		await saveSettings({
			toolServers: servers
		});

		toolServers.set(await getToolServersData($i18n, get(settings)?.toolServers ?? []));
	};

	onMount(async () => {
		servers = get(settings)?.toolServers ?? [];
	});
</script>

<AddConnectionModal simple bind:show={showConnectionModal} onSubmit={addConnectionHandler} />

<form
	class="flex flex-col h-full justify-between text-sm"
	onsubmit={preventDefault(() => {
		updateHandler();
	})}
>
	<div class=" overflow-y-scroll scrollbar-hidden h-full">
		{#if servers !== null}
			<div class="">
				<div class="pr-1.5">
					<!-- {$i18n.t(`Failed to connect to {{URL}} OpenAPI tool server`, {
						URL: 'server?.url'
					})} -->
					<div class="">
						<div class="flex justify-between items-center mb-0.5">
							<div class="font-medium">{$i18n.t('Manage Tool Servers')}</div>

							<Tooltip content={$i18n.t(`Add Connection`)}>
								<button
									class="px-1"
									onclick={() => {
										showConnectionModal = true;
									}}
									type="button"
								>
									<Plus />
								</button>
							</Tooltip>
						</div>

						<div class="flex flex-col gap-1.5">
							{#each servers as server, idx (server.url)}
								<Connection
									bind:url={server.url}
									bind:key={server.key}
									bind:config={server.config}
									onSubmit={() => {
										updateHandler();
									}}
									onDelete={() => {
										servers = servers.filter((_, i) => i !== idx);
										updateHandler();
									}}
								/>
							{/each}
						</div>
					</div>

					<div class="my-1.5">
						<div class="text-xs text-gray-500">
							{$i18n.t('Connect to your own OpenAPI compatible external tool servers.')}
							<br />
							{$i18n.t(
								'CORS must be properly configured by the provider to allow requests from BCGPT.'
							)}
						</div>
					</div>
				</div>
			</div>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
