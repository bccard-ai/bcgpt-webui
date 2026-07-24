<script lang="ts">
	import { get } from 'svelte/store';

	import { models, settings, user } from '$lib/stores';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Selector from './ModelSelector/Selector.svelte';
	import Tooltip from '../common/Tooltip.svelte';

	import { updateUserSettings } from '$lib/apis/users';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Currently selected model IDs, bindable for two-way binding. */
		selectedModels?: string[];
		/** When true, model selection buttons are disabled. */
		disabled?: boolean;
		/** Whether to show the "Set as default" link below the selector. */
		showSetDefault?: boolean;
	}

	let {
		selectedModels = $bindable(['']),
		disabled = false,
		showSetDefault = true
	}: Props = $props();

	/**
	 * Persist the current model selection as the user's default.
	 * Validates that no empty slots exist before saving.
	 */
	const saveDefaultModel = async () => {
		const hasEmptyModel = selectedModels.some((it) => it === '');
		if (hasEmptyModel) {
			toast.error($i18n.t('Choose a model before saving...'));
			return;
		}
		settings.set({ ...get(settings), models: selectedModels });
		await updateUserSettings('', { ui: get(settings) });
		toast.success($i18n.t('Default model updated'));
	};

	/** Append an empty model slot so the user can pick another model. */
	const addModelSlot = () => {
		selectedModels = [...selectedModels, ''];
	};

	/**
	 * Remove the model slot at the given index.
	 * @param index - Position of the slot to remove.
	 */
	const removeModelSlot = (index: number) => {
		selectedModels = selectedModels.filter((_, i) => i !== index);
	};

	/**
	 * Keep selectedModels in sync with the available model list.
	 * Replaces any selected model ID that no longer exists with an empty string,
	 * but only writes back when the array actually changes to avoid infinite loops.
	 */
	$effect(() => {
		const availableModels = get(models);
		if (selectedModels.length > 0 && availableModels.length > 0) {
			const ids = new Set(availableModels.map((m: { id: string }) => m.id));
			const normalized = selectedModels.map((model: string) => (ids.has(model) ? model : ''));
			if (normalized.some((model: string, i: number) => model !== selectedModels[i])) {
				selectedModels = normalized;
			}
		}
	});
</script>

<div class="flex flex-col w-full items-start">
	{#each selectedModels as _selectedModel, selectedModelIdx (selectedModelIdx)}
		<div class="flex w-full max-w-fit">
			<div class="overflow-hidden w-full">
				<div class="mr-1 max-w-full">
					<Selector
						id={`${selectedModelIdx}`}
						placeholder={$i18n.t('Select a model')}
						items={$models.map((model) => ({
							value: model.id,
							label: model.name,
							model: model
						}))}
						showTemporaryChatControl={$user.role === 'user'
							? ($user?.permissions?.chat?.temporary ?? true) &&
								!($user?.permissions?.chat?.temporary_enforced ?? false)
							: true}
						bind:value={selectedModels[selectedModelIdx]}
					/>
				</div>
			</div>

			{#if selectedModelIdx === 0}
				<div
					class="  self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]"
				>
					<Tooltip content={$i18n.t('Add Model')}>
					<button
						class=" "
						{disabled}
						onclick={addModelSlot}
						aria-label={$i18n.t('Add Model')}
					>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="size-3.5"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{:else}
				<div
					class="  self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]"
				>
					<Tooltip content={$i18n.t('Remove Model')}>
					<button
						{disabled}
						onclick={() => removeModelSlot(selectedModelIdx)}
						aria-label={$i18n.t('Remove Model')}
					>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="2"
								stroke="currentColor"
								class="size-3"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{/if}
		</div>
	{/each}
</div>

{#if showSetDefault}
	<div class=" absolute text-left mt-[1px] ml-1 text-[0.7rem] text-gray-500 font-primary">
		<button onclick={saveDefaultModel}> {$i18n.t('Set as default')}</button>
	</div>
{/if}
