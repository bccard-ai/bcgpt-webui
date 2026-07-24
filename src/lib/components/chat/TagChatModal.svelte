<script lang="ts">
	import Modal from '../common/Modal.svelte';
	import Tags from '../common/Tags.svelte';

	/** A single tag with a name property */
	interface TagEntry {
		name: string;
	}

	interface Props {
		/** Current tags to display */
		tags: TagEntry[];
		/** Handler to delete a tag */
		deleteTag: (detail: unknown) => void;
		/** Handler to add a new tag */
		addTag: (detail: unknown) => void;
		/** Controls modal visibility */
		show?: boolean;
	}

	let { tags, deleteTag, addTag, show = $bindable(false) }: Props = $props();
</script>

<Modal bind:show size="xs">
	<div class="px-4 pt-4 pb-5 w-full flex flex-col justify-center">
		<Tags
			{tags}
			onDelete={(e: CustomEvent) => {
				deleteTag(e.detail);
			}}
			onAdd={(e: CustomEvent) => {
				addTag(e.detail);
			}}
		/>
	</div>
</Modal>
