<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { fade, slide } from 'svelte/transition';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let {
		show = $bindable(false),
		onconfirm = (_url: string) => {},
		onCancel = () => {}
	}: {
		show?: boolean;
		onconfirm?: (url: string) => void;
		onCancel?: () => void;
	} = $props();

	let url = $state('');
	let acknowledged = $state(false);

	const close = () => {
		show = false;
		url = '';
		acknowledged = false;
	};
</script>

{#if show}
	<div class="fixed inset-0 z-50 flex items-center justify-center" transition:fade>
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div
			class="absolute inset-0 bg-black/60"
			onclick={() => {
				onCancel();
				close();
			}}
		></div>
		<div
			class="relative m-2 max-h-[40rem] max-w-96 rounded-2xl bg-white p-5 dark:bg-gray-900"
			transition:slide
		>
			<div class="mb-3 text-lg font-semibold text-red-500">
				⚠ {$i18n.t('Trust Required')}
			</div>
			<p class="mb-3 text-sm text-gray-600 dark:text-gray-300">
				{$i18n.t(
					'Only import skills from sources you fully trust. Skills contain prompt instructions that the model will follow.'
				)}
			</p>
			<input
				class="mb-3 w-full rounded-lg bg-gray-50 px-3 py-2 text-sm dark:bg-gray-800"
				placeholder="https://raw.githubusercontent.com/..."
				bind:value={url}
			/>
			<label class="mb-4 flex items-start gap-2 text-xs text-gray-600 dark:text-gray-300">
				<input type="checkbox" bind:checked={acknowledged} class="mt-0.5" />
				<span>{$i18n.t('I acknowledge the risks of importing third-party content.')}</span>
			</label>
			<div class="flex justify-end gap-2">
				<button
					class="rounded-lg px-3 py-1.5 text-sm hover:bg-black/5 dark:hover:bg-white/5"
					onclick={() => {
						onCancel();
						close();
					}}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-40"
					disabled={!acknowledged || !url.trim()}
					onclick={() => {
						if (acknowledged && url.trim()) {
							onconfirm(url.trim());
							close();
						}
					}}
				>
					{$i18n.t('Import')}
				</button>
			</div>
		</div>
	</div>
{/if}
