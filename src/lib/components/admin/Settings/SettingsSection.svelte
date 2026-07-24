<script lang="ts">
	/**
	 * SettingsSection — standardized collapsible group for admin settings panels.
	 *
	 * Wraps the shared Collapsible with consistent header typography, spacing, and a
	 * subtle card border so every settings panel groups related controls the same way.
	 * This replaces the old flat `<hr>`-separated walls.
	 *
	 * Convention:
	 *  - Everyday groups (master toggles, common controls) → leave `open` at its default (true).
	 *  - Advanced / credentials / integrations / rarely-touched groups → pass `open={false}`.
	 *  - Destructive actions → use a `danger` section near the panel bottom, collapsed.
	 *
	 * @example
	 * ```svelte
	 * <SettingsSection title={$i18n.t('Branding')}>
	 *   ...fields...
	 * </SettingsSection>
	 *
	 * <SettingsSection title={$i18n.t('LDAP Integration')} open={false} description={$i18n.t('Optional enterprise directory login.')}>
	 *   ...fields...
	 * </SettingsSection>
	 * ```
	 */
	import Collapsible from '$lib/components/common/Collapsible.svelte';

	interface Props {
		/** Group header text. */
		title: string;
		/** Bindable expanded state. Defaults to open; pass `open={false}` for advanced groups. */
		open?: boolean;
		/** Optional one-line description shown under the header when expanded. */
		description?: string;
		/** Render with destructive (red) styling for a Danger Zone group. */
		danger?: boolean;
		/** Optional HTML id. */
		id?: string;
		/** Group body. */
		children?: import('svelte').Snippet;
	}

	let {
		title,
		open = $bindable(true),
		description = '',
		danger = false,
		id = '',
		children
	}: Props = $props();
</script>

<div
	{id}
	class="rounded-xl border px-3.5 py-2.5 mb-2.5 {danger
		? 'border-red-200/70 dark:border-red-900/40 bg-red-50/40 dark:bg-red-950/10'
		: 'border-gray-100 dark:border-gray-850'}"
>
	<Collapsible
		bind:open
		{title}
		buttonClassName="w-full text-base font-medium transition {danger
			? 'text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300'
			: 'text-gray-700 dark:text-gray-200 hover:text-black dark:hover:text-white'}"
	>
		{#snippet content()}
			{#if description}
				<div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{description}</div>
			{/if}
			<div class="pt-2.5">
				{@render children?.()}
			</div>
		{/snippet}
	</Collapsible>
</div>
