<script lang="ts">
	/**
	 * Admin Evaluations Settings
	 *
	 * Manages arena model evaluation configuration. Allows enabling/disabling
	 * the arena feature and adding/editing/deleting custom arena models that
	 * users can compare side-by-side with rating.
	 */
	import { get } from 'svelte/store';
	import { preventDefault } from 'svelte/legacy';

	import { toast } from 'svelte-sonner';
	import { models, settings, user, config } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	import { getModels } from '$lib/apis';
	import { getConfig, updateConfig } from '$lib/apis/evaluations';

	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import InfoCallout from '$lib/components/common/InfoCallout.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Field } from '$lib/components/ui/field';
	import Model from './Evaluations/Model.svelte';
	import ArenaModelModal from './Evaluations/ArenaModelModal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Callback invoked after config is saved */
		onSave?: () => void;
	}

	let { onSave = () => {} }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/** Evaluation configuration from backend */
	let evaluationConfig = $state(null);
	/** Whether the add/edit modal is showing */
	let showAddModel = $state(false);

	/**
	 * Refresh the global models store from the backend.
	 */
	const refreshGlobalModels = async () => {
		models.set(
			await getModels(
				'',
				get(config)?.features?.enable_direct_connections &&
					(get(settings)?.directConnections ?? null)
			)
		);
	};

	/**
	 * Persist the evaluation config to the backend.
	 * Shows a success toast and refreshes the models store on success.
	 */
	const submitHandler = async () => {
		evaluationConfig = await updateConfig('', evaluationConfig).catch((err) => {
			toast.error(err);
			return null;
		});

		if (evaluationConfig) {
			toast.success('Settings saved successfully');
			await refreshGlobalModels();
		}
	};

	/**
	 * Append a new arena model and persist.
	 * @param model - The arena model object to add
	 */
	const addModelHandler = async (model) => {
		evaluationConfig.EVALUATION_ARENA_MODELS.push(model);
		evaluationConfig.EVALUATION_ARENA_MODELS = [...evaluationConfig.EVALUATION_ARENA_MODELS];

		await submitHandler();
		await refreshGlobalModels();
	};

	/**
	 * Update an existing arena model at the given index and persist.
	 * @param model - Updated model data
	 * @param modelIdx - Index of the model to update
	 */
	const editModelHandler = async (model, modelIdx) => {
		evaluationConfig.EVALUATION_ARENA_MODELS[modelIdx] = model;
		evaluationConfig.EVALUATION_ARENA_MODELS = [...evaluationConfig.EVALUATION_ARENA_MODELS];

		await submitHandler();
		await refreshGlobalModels();
	};

	/**
	 * Remove an arena model by index and persist.
	 * @param modelIdx - Index of the model to remove
	 */
	const deleteModelHandler = async (modelIdx) => {
		evaluationConfig.EVALUATION_ARENA_MODELS = evaluationConfig.EVALUATION_ARENA_MODELS.filter(
			(m, mIdx) => mIdx !== modelIdx
		);

		await submitHandler();
		await refreshGlobalModels();
	};

	onMount(async () => {
		if (get(user).role === 'admin') {
			evaluationConfig = await getConfig('').catch((err) => {
				toast.error(err);
				return null;
			});
		}
	});
</script>

<ArenaModelModal
	bind:show={showAddModel}
	onSubmit={async (e: CustomEvent) => {
		addModelHandler(e.detail);
	}}
/>

<form
	class="flex flex-col h-full justify-between text-sm"
	onsubmit={preventDefault(() => {
		submitHandler();
		onSave?.();
	})}
>
	<div class="overflow-y-scroll scrollbar-hidden h-full">
		<InfoCallout
			>{$i18n.t(
				'Enable arena models so users can compare responses side by side, and rate them to build evaluation leaderboard data.'
			)}</InfoCallout
		>
		{#if evaluationConfig !== null}
			<div class="">
				<div class="mb-3">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('General')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<Field inline separator label={$i18n.t('Arena Models')}>
						<Tooltip content={$i18n.t(`Message rating should be enabled to use this feature`)}>
							<Switch bind:state={evaluationConfig.ENABLE_EVALUATION_ARENA_MODELS} />
						</Tooltip>
					</Field>
				</div>

				{#if evaluationConfig.ENABLE_EVALUATION_ARENA_MODELS}
					<div class="mb-3">
						<div class=" mb-2.5 text-base font-medium flex justify-between items-center">
							<div>
								{$i18n.t('Manage')}
							</div>

							<div>
								<Tooltip content={$i18n.t('Add Arena Model')}>
									<Button
										variant="ghost"
										size="icon"
										type="button"
										onclick={() => {
											showAddModel = true;
										}}
									>
										<Plus />
									</Button>
								</Tooltip>
							</div>
						</div>

						<hr class=" border-gray-100 dark:border-gray-850 my-2" />

						<div class="flex flex-col gap-2">
							{#if (evaluationConfig?.EVALUATION_ARENA_MODELS ?? []).length > 0}
								{#each evaluationConfig.EVALUATION_ARENA_MODELS as model, index (index)}
									<Model
										{model}
										onEdit={(e: CustomEvent) => {
											editModelHandler(e.detail, index);
										}}
										onDelete={(_e: CustomEvent) => {
											deleteModelHandler(index);
										}}
									/>
								{/each}
							{:else}
								<div class=" text-center text-xs text-muted-foreground">
									{$i18n.t(
										`Using the default arena model with all models. Click the plus button to add custom models.`
									)}
								</div>
							{/if}
						</div>
					</div>
				{/if}
			</div>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<Button type="submit">{$i18n.t('Save')}</Button>
	</div>
</form>
