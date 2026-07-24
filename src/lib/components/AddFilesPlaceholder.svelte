<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * A placeholder component shown when no files have been added yet.
	 * Displays a file icon with customizable title, content, or a custom children snippet.
	 *
	 * @example
	 * ```svelte
	 * <AddFilesPlaceholder
	 *   title="Upload Documents"
	 *   content="Drag and drop files here"
	 * >
	 *   <p>Custom content</p>
	 * </AddFilesPlaceholder>
	 * ```
	 *
	 * @param title - Optional title text (defaults to i18n "Add Files").
	 * @param content - Optional description text (defaults to i18n drop hint).
	 * @param children - Optional snippet for custom content replacement.
	 */
	interface Props {
		title?: string;
		content?: string;
		children?: import('svelte').Snippet;
	}

	let { title = '', content = '', children }: Props = $props();
</script>

<div class="px-3">
	<div class="text-center text-6xl mb-3">📄</div>
	<div class="text-center dark:text-white text-xl font-semibold z-50">
		{#if title}
			{title}
		{:else}
			{$i18n.t('Add Files')}
		{/if}
	</div>

	{#if children}{@render children()}{:else}<div class="px-2 mt-2 text-center text-sm dark:text-gray-200 w-full">
			{#if content}
				{content}
			{:else}
				{$i18n.t('Drop any files here to add to the conversation')}
			{/if}
		</div>
	{/if}
</div>
