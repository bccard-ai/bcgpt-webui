<script lang="ts">
	import TagInput from './Tags/TagInput.svelte';
	import TagList from './Tags/TagList.svelte';
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Tags — combined tag list + tag input component.
	 *
	 * @example
	 * ```svelte
	 * <Tags {tags} onAdd={addTag} onDelete={removeTag} />
	 * ```
	 *
	 * @props tags - Array of { name: string } tag objects
	 * @props onAdd - Called with the tag name when a tag is added
	 * @props onDelete - Called with the tag name when a tag is removed
	 */
	let { tags = $bindable([]), onDelete = () => {}, onAdd = () => {} } = $props();
</script>

<div class="flex flex-row flex-wrap gap-1 line-clamp-1">
	<TagList
		{tags}
		onDelete={(e: CustomEvent) => {
			onDelete?.(e.detail);
		}}
	/>

	<TagInput
		label={tags.length == 0 ? $i18n.t('Add Tags') : ''}
		onAdd={(name: string) => {
			onAdd?.((name as unknown as CustomEvent).detail);
		}}
	/>
</div>
