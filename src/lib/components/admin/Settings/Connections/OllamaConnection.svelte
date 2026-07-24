<script lang="ts">
	/**
	 * Ollama Connection Row
	 *
	 * A single Ollama API connection entry with base URL and optional config.
	 * Provides manage (pull/delete models) and configure modals.
	 */
	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ManageOllamaModal from './ManageOllamaModal.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface OllamaConnectionConfig {
		/** Whether this connection is active */
		enable?: boolean;
		/** Tags for categorization */
		tags?: { name: string }[];
		/** Optional model ID prefix */
		prefix_id?: string;
		/** Explicit list of allowed model IDs */
		model_ids?: string[];
	}

	interface Connection {
		url: string;
		key: string;
		config?: OllamaConnectionConfig;
	}

	interface Props {
		/** Called when user confirms deletion */
		onDelete?: () => void;
		/** Called after connection is edited and saved */
		onSubmit?: (connection: Connection) => void;
		/** Ollama base URL (two-way bindable) */
		url?: string;
		/** Index of this connection in the parent array */
		idx?: number;
		/** Per-connection config (two-way bindable) */
		config?: Record<string, unknown>;
	}

	let {
		onDelete = () => {},
		onSubmit = () => {},
		url = $bindable(''),
		idx = 0,
		config = $bindable({})
	}: Props = $props();

	/** UI state for modals */
	let showManageModal = $state(false);
	let showConfigModal = $state(false);
	let showDeleteConfirmDialog = $state(false);
</script>

<AddConnectionModal
	ollama
	edit
	bind:show={showConfigModal}
	connection={{
		url,
		key: (config?.key as string | undefined) ?? '',
		config: config
	}}
	onDelete={() => {
		showDeleteConfirmDialog = true;
	}}
	onSubmit={(connection) => {
		url = connection.url;
		config = { ...connection.config, key: connection.key };
		onSubmit(connection);
	}}
/>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	onconfirm={() => {
		onDelete();
		showConfigModal = false;
	}}
/>

<ManageOllamaModal bind:show={showManageModal} urlIdx={idx} />

<div class="flex gap-1.5 items-center" class:opacity-50={!(config?.enable ?? true)}>
	<Tooltip
		className="w-full relative"
		content={$i18n.t(`WebUI will make requests to "{{url}}/api/chat"`, {
			url
		})}
		placement="top-start"
	>
		<Input mono placeholder={$i18n.t('Enter URL (e.g. http://localhost:11434)')} bind:value={url} />
	</Tooltip>

	<div class="flex gap-1">
		<Tooltip content={$i18n.t('Manage')} className="self-start">
			<Button
				variant="ghost"
				size="icon"
				type="button"
				class="self-center"
				onclick={() => {
					showManageModal = true;
				}}
			>
				<ArrowDownTray />
			</Button>
		</Tooltip>

		<Tooltip content={$i18n.t('Configure')} className="self-start">
			<Button
				variant="ghost"
				size="icon"
				type="button"
				class="self-center"
				onclick={() => {
					showConfigModal = true;
				}}
			>
				<Cog6 />
			</Button>
		</Tooltip>
	</div>
</div>
