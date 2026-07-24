<script lang="ts">
	import {
		addTagById,
		deleteTagById,
		getAllTags,
		getTagsById,
		updateChatById
	} from '$lib/apis/chats';
	import { tags as globalTags } from '$lib/stores';
	import { onMount } from 'svelte';

	import Tags from '../common/Tags.svelte';
	import { toast } from 'svelte-sonner';

	interface Props {
		/** The chat ID to manage tags for */
		chatId?: string;
		/** Callback when a tag is added */
		onAdd?: (tag: { name: string }) => void;
		/** Callback when a tag is deleted */
		onDelete?: (tag: { name: string }) => void;
	}

	let { chatId = '', onAdd = () => {}, onDelete = () => {} }: Props = $props();

	/** Local list of tags for the current chat */
	let tags = $state<string[]>([]);

	/** Fetch tags associated with the current chat, falling back to an empty array */
	const fetchChatTags = async (): Promise<string[]> => {
		return await getTagsById('', chatId).catch(() => []);
	};

	/** Refresh the global tag store so the sidebar stays in sync */
	const refreshGlobalTags = async (): Promise<void> => {
		await globalTags.set(await getAllTags(''));
	};

	/**
	 * Add a new tag to the current chat and persist the change.
	 * Updates both the local tag list and the global tag store.
	 */
	const addTag = async (tagName: string): Promise<void> => {
		const res = await addTagById('', chatId, tagName).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!res) return;

		tags = await fetchChatTags();
		await updateChatById('', chatId, { tags });
		await refreshGlobalTags();

		onAdd?.({ name: tagName });
	};

	/**
	 * Remove a tag from the current chat and persist the change.
	 * Updates both the local tag list and the global tag store.
	 */
	const deleteTag = async (tagName: string): Promise<void> => {
		await deleteTagById('', chatId, tagName);
		tags = await fetchChatTags();
		await updateChatById('', chatId, { tags });
		await refreshGlobalTags();

		onDelete?.({ name: tagName });
	};

	onMount(async () => {
		if (chatId) {
			tags = await fetchChatTags();
		}
	});
</script>

<Tags
	{tags}
	onDelete={(e: CustomEvent) => {
		deleteTag(e.detail);
	}}
	onAdd={(e: CustomEvent) => {
		addTag(e.detail);
	}}
/>
