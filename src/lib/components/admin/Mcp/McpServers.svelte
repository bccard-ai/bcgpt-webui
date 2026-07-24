<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { toast } from 'svelte-sonner';

	import {
		getMcpServersConfig,
		setMcpServersConfig,
		type McpServersConfig
	} from '$lib/apis/configs';
	import { testMcpServer } from '$lib/apis/mcp';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let config = $state<McpServersConfig | null>(null);
	let newHost = $state('');
	// fields for adding a server
	let showAdd = $state(false);
	let sId = $state('');
	let sName = $state('');
	let sUrl = $state('');
	let sToken = $state('');

	const reload = async () => {
		config = await getMcpServersConfig(localStorage.token);
	};

	onMount(reload);

	const save = async () => {
		if (!config) return;
		try {
			await setMcpServersConfig(localStorage.token, config);
			toast.success($i18n.t('MCP settings saved'));
		} catch (e) {
			toast.error(`${e}`);
		}
	};

	const addHost = () => {
		const h = newHost.trim();
		if (h && config && !config.MCP_ALLOWED_HOSTS.includes(h)) {
			config.MCP_ALLOWED_HOSTS = [...config.MCP_ALLOWED_HOSTS, h];
		}
		newHost = '';
	};

	const removeHost = (h: string) => {
		if (!config) return;
		config.MCP_ALLOWED_HOSTS = config.MCP_ALLOWED_HOSTS.filter((x) => x !== h);
	};

	const addServer = () => {
		if (!config || !sId.trim() || !sUrl.trim()) return;
		config.MCP_SERVERS = [
			...config.MCP_SERVERS,
			{
				id: sId.trim(),
				name: sName.trim() || sId.trim(),
				url: sUrl.trim(),
				token: sToken.trim(),
				enabled: true,
				allow_user_override: true
			}
		];
		sId = sName = sUrl = sToken = '';
		showAdd = false;
	};

	const removeServer = (id: string) => {
		if (!config) return;
		config.MCP_SERVERS = config.MCP_SERVERS.filter((s) => s.id !== id);
	};

	const toggleBuiltin = (name: string) => {
		if (!config) return;
		if (config.MCP_BUILTINS_ENABLED.includes(name)) {
			config.MCP_BUILTINS_ENABLED = config.MCP_BUILTINS_ENABLED.filter((n) => n !== name);
		} else {
			config.MCP_BUILTINS_ENABLED = [...config.MCP_BUILTINS_ENABLED, name];
		}
	};

	const test = async (id: string) => {
		try {
			const r = await testMcpServer(localStorage.token, id);
			if (r.ok) toast.success($i18n.t('Connection OK'));
			else toast.error(`${r.error ?? 'failed'}`);
		} catch (e) {
			toast.error(`${e}`);
		}
	};
</script>

{#if config}
	<div class="flex flex-col gap-6">
		<!-- Feature toggle -->
		<div class="flex items-center justify-between">
			<div class="text-sm font-medium">{$i18n.t('Enable MCP servers')}</div>
			<Switch bind:state={config.ENABLE_MCP_SERVERS} onchange={save} />
		</div>

		<!-- Allowed hosts -->
		<div>
			<div class="mb-1 text-sm font-medium">{$i18n.t('Allowed hosts')}</div>
			<div class="flex flex-wrap gap-1.5">
				{#each config.MCP_ALLOWED_HOSTS as h (h)}
					<span
						class="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs dark:bg-gray-800"
					>
						{h}
						<button class="text-red-500" onclick={() => removeHost(h)}>×</button>
					</span>
				{/each}
			</div>
			<div class="mt-2 flex gap-2">
				<input
					class="flex-1 rounded-lg bg-gray-50 px-3 py-1.5 text-sm dark:bg-gray-850"
					placeholder="example.com"
					bind:value={newHost}
					onkeydown={(e) => e.key === 'Enter' && addHost()}
				/>
				<button class="rounded-lg bg-gray-50 px-3 py-1.5 text-sm dark:bg-gray-850" onclick={addHost}
					>+</button
				>
			</div>
		</div>

		<!-- Built-ins -->
		<div>
			<div class="mb-1 text-sm font-medium">{$i18n.t('Built-in MCP servers')}</div>
			<div class="flex gap-3 text-sm">
				{#each ['time', 'fetch'] as b (b)}
					<label class="flex items-center gap-1.5">
						<input
							type="checkbox"
							checked={config.MCP_BUILTINS_ENABLED.includes(b)}
							onchange={() => toggleBuiltin(b)}
						/>
						{b}
					</label>
				{/each}
			</div>
		</div>

		<!-- Server catalog -->
		<div>
			<div class="mb-2 flex items-center justify-between">
				<div class="text-sm font-medium">{$i18n.t('MCP Servers')}</div>
				<button
					class="rounded-lg bg-gray-50 px-3 py-1.5 text-sm dark:bg-gray-850"
					onclick={() => (showAdd = !showAdd)}>+ {$i18n.t('Add server')}</button
				>
			</div>

			{#if showAdd}
				<div class="mb-3 grid grid-cols-2 gap-2 rounded-lg bg-gray-50 p-3 dark:bg-gray-850">
					<input
						class="rounded bg-white px-2 py-1 text-sm dark:bg-gray-900"
						placeholder="id"
						bind:value={sId}
					/>
					<input
						class="rounded bg-white px-2 py-1 text-sm dark:bg-gray-900"
						placeholder="name"
						bind:value={sName}
					/>
					<input
						class="col-span-2 rounded bg-white px-2 py-1 text-sm dark:bg-gray-900"
						placeholder="https://mcp.example.com/mcp"
						bind:value={sUrl}
					/>
					<input
						class="col-span-2 rounded bg-white px-2 py-1 text-sm dark:bg-gray-900"
						placeholder="bearer token (optional)"
						bind:value={sToken}
					/>
					<button class="col-span-2 rounded bg-blue-600 py-1 text-sm text-white" onclick={addServer}
						>{$i18n.t('Add')}</button
					>
				</div>
			{/if}

			<div class="flex flex-col gap-1">
				{#each config.MCP_SERVERS as s (s.id)}
					<div
						class="flex items-center rounded-xl px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5"
					>
						<div class="flex-1">
							<div class="font-semibold">{s.name}</div>
							<div class="text-xs text-gray-500">{s.url}</div>
						</div>
						<Tooltip content={$i18n.t('Test connection')}>
							<button class="p-1.5 text-sm" onclick={() => test(s.id)}><Pencil /></button>
						</Tooltip>
						<div class="mx-1">
							<Switch
								bind:state={s.enabled}
								onchange={() => {
									if (config) {
										config.MCP_SERVERS = [...config.MCP_SERVERS];
									}
									save();
								}}
							/>
						</div>
						<Tooltip content={$i18n.t('Delete')}>
							<button class="p-1.5 text-red-500" onclick={() => removeServer(s.id)}>
								<GarbageBin />
							</button>
						</Tooltip>
					</div>
				{:else}
					<div class="text-sm text-gray-500">{$i18n.t('No MCP servers configured')}.</div>
				{/each}
			</div>
		</div>

		<div class="flex justify-end">
			<button class="rounded-lg bg-blue-600 px-4 py-1.5 text-sm text-white" onclick={save}>
				{$i18n.t('Save')}
			</button>
		</div>
	</div>
{/if}
