<script lang="ts">
	/**
	 * OpenAI Connection Row
	 *
	 * A single OpenAI-compatible API connection entry with base URL, API key,
	 * and optional configuration (tags, prefix, model filtering).
	 * Supports pipeline badge indicator and inline config modal.
	 */
	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';

	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface ConnectionConfig {
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
		config?: ConnectionConfig;
	}

	interface Props {
		/** Called when user confirms deletion */
		onDelete?: () => void;
		/** Called after connection is edited and saved */
		onSubmit?: (connection: Connection) => void;
		/** Whether this URL hosts pipelines (shows badge) */
		pipeline?: boolean;
		/** API base URL (two-way bindable) */
		url?: string;
		/** API key (two-way bindable) */
		key?: string;
		/** Per-connection config (two-way bindable) */
		config?: ConnectionConfig;
	}

	let {
		onDelete = () => {},
		onSubmit = () => {},
		pipeline = false,
		url = $bindable(''),
		key = $bindable(''),
		config = $bindable({})
	}: Props = $props();

	/** UI state for modals */
	let showConfigModal = $state(false);
	let showDeleteConfirmDialog = $state(false);
</script>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	onconfirm={() => {
		onDelete();
	}}
/>

<AddConnectionModal
	edit
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

<div class="flex w-full gap-2 items-start" class:opacity-50={!(config?.enable ?? true)}>
	<Tooltip
		className="w-full relative"
		content={$i18n.t(`WebUI will make requests to "{{url}}/chat/completions"`, {
			url
		})}
		placement="top-start"
	>
		<div class="flex w-full flex-col gap-3">
			<div class="flex flex-col gap-1">
				<div class="text-xs font-medium text-muted-foreground">{$i18n.t('API Base URL')}</div>
				<div class="relative">
					<Input
						mono
						class={pipeline ? 'pr-8' : ''}
						placeholder={$i18n.t('API Base URL')}
						bind:value={url}
						autocomplete="off"
					/>

					{#if pipeline}
						<div class=" absolute top-0.5 right-2.5">
							<Tooltip content="Pipelines">
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 24 24"
									fill="currentColor"
									class="size-4"
								>
									<path
										d="M11.644 1.59a.75.75 0 0 1 .712 0l9.75 5.25a.75.75 0 0 1 0 1.32l-9.75 5.25a.75.75 0 0 1-.712 0l-9.75-5.25a.75.75 0 0 1 0-1.32l9.75-5.25Z"
									/>
									<path
										d="m3.265 10.602 7.668 4.129a2.25 2.25 0 0 0 2.134 0l7.668-4.13 1.37.739a.75.75 0 0 1 0 1.32l-9.75 5.25a.75.75 0 0 1-.71 0l-9.75-5.25a.75.75 0 0 1 0-1.32l1.37-.738Z"
									/>
									<path
										d="m10.933 19.231-7.668-4.13-1.37.739a.75.75 0 0 0 0 1.32l9.75 5.25c.221.12.489.12.71 0l9.75-5.25a.75.75 0 0 0 0-1.32l-1.37-.738-7.668 4.13a2.25 2.25 0 0 1-2.134-.001Z"
									/>
								</svg>
							</Tooltip>
						</div>
					{/if}
				</div>
			</div>
			<div class="flex flex-col gap-1">
				<div class="text-xs font-medium text-muted-foreground">{$i18n.t('API Key')}</div>

				<SensitiveInput mono placeholder={$i18n.t('API Key')} bind:value={key} />
			</div>
		</div>
	</Tooltip>

	<div class="flex gap-1 pt-5">
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
