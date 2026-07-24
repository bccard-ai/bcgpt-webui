<script lang="ts">
	import RecursiveFolder from './RecursiveFolder.svelte';

	interface Props {
		/** Map of folder IDs to folder data objects */
		folders?: Record<string, { parent_id: string | null; name: string }>;
		/** Callback invoked when data changes (e.g., chat moved, folder updated) */
		onchange?: (...args: unknown[]) => void;
		/** Callback invoked when items are imported into a folder */
		onimport?: (...args: unknown[]) => void;
		/** Callback invoked when a folder is updated */
		onupdate?: (...args: unknown[]) => void;
	}

	let { folders = {}, onchange, onimport, onupdate }: Props = $props();

	/** Sorted list of root-level folder IDs (no parent), sorted alphabetically with numeric sensitivity */
	let folderList = $derived(
		Object.keys(folders)
			.filter((key) => folders[key].parent_id === null)
			.sort((a, b) =>
				folders[a].name.localeCompare(folders[b].name, undefined, {
					numeric: true,
					sensitivity: 'base'
				})
			)
	);
</script>

{#each folderList as folderId (folderId)}
	<RecursiveFolder
		className=""
		{folders}
		{folderId}
		onImport={(e: CustomEvent) => {
			onimport?.(e.detail);
		}}
		onUpdate={(e: CustomEvent) => {
			onupdate?.(e.detail);
		}}
		onchange={(e: CustomEvent) => {
			onchange?.(e.detail);
		}}
	/>
{/each}
