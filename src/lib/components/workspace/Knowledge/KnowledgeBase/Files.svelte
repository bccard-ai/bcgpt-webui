<script lang="ts">
	import FileItem from '$lib/components/common/FileItem.svelte';

	interface KnowledgeFile {
		id?: string;
		name?: string;
		size?: number | string;
		status?: string;
		meta?: { name?: string; size?: number | string };
		file?: { data?: { content?: string } };
		[key: string]: unknown;
	}

	interface Props {
		/** Currently selected file ID for highlighting */
		selectedFileId?: string | null;
		/** Array of knowledge files to display */
		files?: KnowledgeFile[];
		/** Whether to render in compact mode */
		small?: boolean;
		/** Callback when a file is clicked */
		onClick?: (...args: unknown[]) => void;
		/** Callback when a file's dismiss button is clicked */
		onDelete?: (...args: unknown[]) => void;
	}

	let {
		selectedFileId = null,
		files = [],
		small = false,
		onClick = () => {},
		onDelete = () => {}
	}: Props = $props();
</script>

<div class=" max-h-full flex flex-col w-full">
	{#each files as file, i (file.id)}
		<div class="mt-1 px-2">
			<FileItem
				className="w-full"
				colorClassName="{selectedFileId === file.id
					? ' bg-gray-50 dark:bg-gray-850'
					: 'bg-transparent'} hover:bg-gray-50 dark:hover:bg-gray-850 transition"
				{small}
				item={files[i]}
				name={(file?.name ?? file?.meta?.name) as string}
				type="file"
				size={(file?.size ?? file?.meta?.size ?? '') as number}
				loading={file.status === 'uploading'}
				dismissible
				onClick={() => {
					if (file.status === 'uploading') {
						return;
					}

					onClick?.(file.id);
				}}
				onDismiss={() => {
					if (file.status === 'uploading') {
						return;
					}

					onDelete?.(file.id);
				}}
			/>
		</div>
	{/each}
</div>
