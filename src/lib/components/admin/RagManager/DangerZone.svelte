<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	import { resetVectorDB, resetUploadDir } from '$lib/apis/retrieval';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';

	interface Props {
		onRefresh: () => void;
		collectionsCount?: number;
		kbCount?: number;
	}
	let { onRefresh, collectionsCount = 0, kbCount = 0 }: Props = $props();
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let showResetDBConfirm = $state(false);
	let showResetUploadsConfirm = $state(false);

	const handleResetDB = async (typed: string) => {
		if ((typed ?? '').trim().toUpperCase() !== 'RESET') {
			toast.error($i18n.t('Type RESET to confirm.'));
			return;
		}
		try {
			await resetVectorDB('');
			toast.success($i18n.t('Vector DB reset successfully'));
			onRefresh();
		} catch (e) {
			toast.error(`${e}`);
		}
		showResetDBConfirm = false;
	};

	const handleResetUploads = async (typed: string) => {
		if ((typed ?? '').trim().toUpperCase() !== 'RESET') {
			toast.error($i18n.t('Type RESET to confirm.'));
			return;
		}
		try {
			await resetUploadDir('');
			toast.success($i18n.t('Upload directory reset successfully'));
		} catch (e) {
			toast.error(`${e}`);
		}
		showResetUploadsConfirm = false;
	};
</script>

<div class="space-y-4">
	<div class="text-base font-medium text-red-500">{$i18n.t('Danger Zone')}</div>
	<hr class="border-red-200 dark:border-red-900/50 my-2" />

	<InfoCallout variant="warning"
		>{$i18n.t(
			'These actions permanently delete data across the entire RAG system and cannot be undone. Proceed with caution.'
		)}</InfoCallout
	>

	<div class="p-4 rounded-lg border border-red-200 dark:border-red-900/50">
		<div class="flex items-center justify-between">
			<div>
				<div class="font-medium text-sm">{$i18n.t('Reset Vector DB')}</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
					{$i18n.t(
						'Delete all {{collections}} collections and documents from the vector database, unlinking all {{kbs}} knowledge bases. This cannot be undone.',
						{ collections: collectionsCount, kbs: kbCount }
					)}
				</div>
			</div>
			<button
				class="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition"
				onclick={() => (showResetDBConfirm = true)}
			>
				{$i18n.t('Reset')}
			</button>
		</div>
	</div>

	<div class="p-4 rounded-lg border border-red-200 dark:border-red-900/50">
		<div class="flex items-center justify-between">
			<div>
				<div class="font-medium text-sm">{$i18n.t('Reset Upload Directory')}</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
					{$i18n.t('Delete all uploaded files from the upload directory. This cannot be undone.')}
				</div>
			</div>
			<button
				class="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition"
				onclick={() => (showResetUploadsConfirm = true)}
			>
				{$i18n.t('Reset')}
			</button>
		</div>
	</div>
</div>

<ConfirmDialog
	bind:show={showResetDBConfirm}
	title={$i18n.t('Reset Vector DB')}
	message={$i18n.t(
		'This permanently deletes ALL {{collections}} collections and unlinks all {{kbs}} knowledge bases. This cannot be undone.',
		{ collections: collectionsCount, kbs: kbCount }
	)}
	input={true}
	inputPlaceholder={$i18n.t('Type RESET to confirm')}
	confirmLabel={$i18n.t('Reset')}
	onconfirm={handleResetDB}
/>

<ConfirmDialog
	bind:show={showResetUploadsConfirm}
	title={$i18n.t('Reset Upload Directory')}
	message={$i18n.t(
		'This permanently deletes ALL uploaded files from the upload directory. This cannot be undone. Type RESET to confirm.'
	)}
	input={true}
	inputPlaceholder={$i18n.t('Type RESET to confirm')}
	confirmLabel={$i18n.t('Reset')}
	onconfirm={handleResetUploads}
/>
