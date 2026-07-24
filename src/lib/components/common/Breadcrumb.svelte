<script lang="ts">
	import { getContext } from 'svelte';
	import { resolve } from '$app/paths';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Breadcrumb — admin navigation breadcrumb trail.
	 *
	 * Always starts with "Admin" and renders provided items after it.
	 * The last item is rendered as plain text (current page), others as links.
	 *
	 * @example
	 * ```svelte
	 * <Breadcrumb items={[{ label: 'Settings', href: '/admin/settings' }]} />
	 * ```
	 *
	 * @props items - Array of { label, href? } objects
	 */
	interface Props {
		/** Array of breadcrumb items. Last item is rendered as text. */
		items?: { label: string; href?: string }[];
	}

	let { items = [] }: Props = $props();
</script>

<nav
	aria-label={$i18n.t('Breadcrumb')}
	class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-2"
>
	<a href={resolve('/admin')} class="hover:text-gray-700 dark:hover:text-white transition"
		>{$i18n.t('Admin')}</a
	>

	{#each items as item, i (i)}
		<span class="text-gray-400 dark:text-gray-600">/</span>
		{#if item.href && i < items.length - 1}
			<a
				href={resolve(item.href as unknown as '/')}
				class="hover:text-gray-700 dark:hover:text-white transition">{$i18n.t(item.label)}</a
			>
		{:else}
			<span class="text-gray-900 dark:text-white font-medium">{$i18n.t(item.label)}</span>
		{/if}
	{/each}
</nav>
