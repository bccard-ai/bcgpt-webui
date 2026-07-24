<script lang="ts">
	/**
	 * Admin Database Settings
	 *
	 * Provides database backup/restore operations: import/export platform config,
	 * download full database backup, and export all user chats.
	 *
	 * This panel is intentionally flat — it is a small set of one-shot action buttons,
	 * grouped under two static labels (Configuration / Backup & Export) rather than
	 * collapsible sections.
	 */
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { downloadDatabase } from '$lib/apis/utils';
	import { getContext } from 'svelte';
	import { config } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { getAllUserChats } from '$lib/apis/chats';
	import { exportConfig, importConfig } from '$lib/apis/configs';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import { Button } from '$lib/components/ui/button';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Parent save handler (retained for prop compatibility; this panel has no form to save) */
		saveHandler: () => void;
	}

	// This panel has no editable form to save; the prop is kept for parent API compatibility.
	let { saveHandler: _saveHandler }: Props = $props();

	/**
	 * Export all user chats as a downloadable JSON file.
	 */
	const exportAllUserChats = async () => {
		const blob = new Blob([JSON.stringify(await getAllUserChats(''))], {
			type: 'application/json'
		});
		saveAs(blob, `all-chats-export-${Date.now()}.json`);
	};
</script>

<div class="flex flex-col h-full text-sm">
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<InfoCallout variant="warning"
			>{$i18n.t(
				'Import or export the platform configuration and download a full backup of the database. Importing a config overwrites current settings, so handle these files with care.'
			)}</InfoCallout
		>

		<!-- Configuration -->
		<div>
			<div class="mb-2 text-sm font-medium">{$i18n.t('Configuration')}</div>

			<input
				id="config-json-input"
				hidden
				type="file"
				accept=".json"
				onchange={(e: CustomEvent) => {
					const file = e.target?.files[0];
					const reader = new FileReader();

					reader.onload = async (e) => {
						const res = await importConfig('', JSON.parse(e.target?.result)).catch((error) => {
							toast.error(`${error}`);
						});

						if (res) {
							toast.success('Config imported successfully');
						}
						if (e.target) e.target.value = null;
					};

					reader.readAsText(file);
				}}
			/>

			<Button
				variant="ghost"
				size="sm"
				type="button"
				class="w-full justify-start text-destructive hover:bg-destructive/10"
				onclick={async () => {
					document.getElementById('config-json-input').click();
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 16 16"
					fill="currentColor"
					class="w-4 h-4"
				>
					<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
					<path
						fill-rule="evenodd"
						d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 11.25a.75.75 0 0 1-1.5 0V8.66L7.53 9.88a.75.75 0 0 1-1.06-1.06l2.5-2.5a.75.75 0 0 1 1.06 0l2.5 2.5a.75.75 0 1 1-1.06 1.06L8.75 8.56v2.69Z"
						clip-rule="evenodd"
					/>
				</svg>
				{$i18n.t('Import Config from JSON File')}
			</Button>

			<Button
				variant="ghost"
				size="sm"
				type="button"
				class="w-full justify-start"
				onclick={async () => {
					const config = await exportConfig('');
					const blob = new Blob([JSON.stringify(config)], {
						type: 'application/json'
					});
					saveAs(blob, `config-${Date.now()}.json`);
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 16 16"
					fill="currentColor"
					class="w-4 h-4"
				>
					<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
					<path
						fill-rule="evenodd"
						d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
						clip-rule="evenodd"
					/>
				</svg>
				{$i18n.t('Export Config to JSON File')}
			</Button>
		</div>

		{#if $config?.features.enable_admin_export ?? true}
			<!-- Backup & Export -->
			<div>
				<div class="mb-2 text-sm font-medium">{$i18n.t('Backup & Export')}</div>

				<Button
					variant="ghost"
					size="sm"
					type="button"
					class="w-full justify-start"
					onclick={() => {
						downloadDatabase('').catch((error) => {
							toast.error(`${error}`);
						});
					}}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
						<path
							fill-rule="evenodd"
							d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
							clip-rule="evenodd"
						/>
					</svg>
					{$i18n.t('Download Database')}
				</Button>

				<Button
					variant="ghost"
					size="sm"
					type="button"
					class="w-full justify-start"
					onclick={() => {
						exportAllUserChats();
					}}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
						<path
							fill-rule="evenodd"
							d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
							clip-rule="evenodd"
						/>
					</svg>
					{$i18n.t('Export All Chats (All Users)')}
				</Button>
			</div>
		{/if}
	</div>
</div>
