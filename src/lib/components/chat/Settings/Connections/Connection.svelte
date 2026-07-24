<script lang="ts">
	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		onDelete?: () => void;
		onSubmit?: (connection: unknown) => void;
		pipeline?: boolean;
		url?: string;
		key?: string;
		config?: Record<string, unknown>;
	}

	let {
		onDelete = () => {},
		onSubmit = () => {},
		pipeline = false,
		url = $bindable(''),
		key = $bindable(''),
		config = $bindable({})
	}: Props = $props();

	let showConfigModal = $state(false);
	let showDeleteConfirmDialog = $state(false);
</script>

<AddConnectionModal
	edit
	direct
	bind:show={showConfigModal}
	connection={{
		url,
		key,
		config
	}}
	onDelete={() => {
		showDeleteConfirmDialog = true;
	}}
	onSubmit={(connection) => {
		url = connection.url;
		key = connection.key;
		config = connection.config ?? {};
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

<div class="flex w-full gap-2 items-center">
	<Tooltip
		className="w-full relative"
		content={$i18n.t(`WebUI will make requests to "{{url}}/chat/completions"`, {
			url
		})}
		placement="top-start"
	>
		{#if !(config?.enable ?? true)}
			<div
				class="absolute top-0 bottom-0 left-0 right-0 opacity-60 bg-white dark:bg-gray-900 z-10"
			></div>
		{/if}
		<div class="flex w-full">
			<div class="flex-1 relative">
				<input
					class=" border-1 border-gray-100 focus:text-blue-700 w-full p-1 px-2 rounded-md{pipeline
						? 'pr-8'
						: ''}"
					placeholder={$i18n.t('API Base URL')}
					bind:value={url}
					autocomplete="off"
				/>
			</div>

			<SensitiveInput
				inputClassName=" outline-hidden bg-transparent w-full"
				placeholder={$i18n.t('API Key')}
				bind:value={key}
			/>
		</div>
	</Tooltip>

	<div class="flex gap-1">
		<Tooltip content={$i18n.t('Configure')} className="self-start">
			<button
				class="self-center p-1 bg-transparent hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-850 rounded-lg transition"
				onclick={() => {
					showConfigModal = true;
				}}
				type="button"
			>
				<Cog6 />
			</button>
		</Tooltip>
	</div>
</div>
