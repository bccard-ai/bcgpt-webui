<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';
	import Switch from './Switch.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Valves — dynamic configuration form rendered from a JSON Schema spec.
	 *
	 * Renders each property in `valvesSpec.properties` with appropriate input
	 * controls (select, switch, text input, textarea) based on the property type.
	 *
	 * @example
	 * ```svelte
	 * <Valves {valvesSpec} bind:valves onchange={save} />
	 * ```
	 *
	 * @props valvesSpec - JSON Schema object describing the configuration
	 * @props valves - Bindable key-value configuration object
	 * @props onchange - Called when any valve value changes
	 */
	interface Props {
		/** JSON Schema object describing the configuration properties. */
		valvesSpec?: Record<string, unknown> | null;
		/** Bindable key-value configuration object. */
		valves?: Record<string, unknown>;
		/** Called when any valve value changes. */
		onchange?: (...args: unknown[]) => void;
	}

	let { valvesSpec = null, valves = $bindable({}), onchange }: Props = $props();
</script>

{#if valvesSpec && Object.keys(valvesSpec?.properties ?? {}).length}
	{#each Object.keys(valvesSpec.properties) as property (property)}
		<div class=" py-0.5 w-full justify-between">
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{valvesSpec.properties[property].title}

					{#if (valvesSpec?.required ?? []).includes(property)}
						<span class=" text-gray-500">*{$i18n.t('required')}</span>
					{/if}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition"
					type="button"
					onclick={() => {
						valves[property] =
							(valves[property] ?? null) === null
								? (valvesSpec.properties[property]?.default ?? '')
								: null;

						onchange?.();
					}}
				>
					{#if (valves[property] ?? null) === null}
						<span class="ml-2 self-center">
							{#if (valvesSpec?.required ?? []).includes(property)}
								{$i18n.t('None')}
							{:else}
								{$i18n.t('Default')}
							{/if}
						</span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>

			{#if (valves[property] ?? null) !== null}
				<div class="flex mt-0.5 mb-1.5 space-x-2">
					<div class=" flex-1">
						{#if valvesSpec.properties[property]?.enum ?? null}
							<select
								class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden border border-gray-100 dark:border-gray-850"
								bind:value={valves[property]}
								onchange={() => {
									onchange?.();
								}}
							>
								{#each valvesSpec.properties[property].enum as option (option)}
									<option value={option} selected={option === valves[property]}>
										{option}
									</option>
								{/each}
							</select>
						{:else if (valvesSpec.properties[property]?.type ?? null) === 'boolean'}
							<div class="flex justify-between items-center">
								<div class="text-xs text-gray-500">
									{valves[property] ? $i18n.t('Enabled') : $i18n.t('Disabled')}
								</div>

								<div class=" pr-2">
									<Switch
										bind:state={valves[property]}
										onchange={() => {
											onchange?.();
										}}
									/>
								</div>
							</div>
						{:else if (valvesSpec.properties[property]?.type ?? null) !== 'string'}
							<input
								class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden border border-gray-100 dark:border-gray-850"
								type="text"
								placeholder={valvesSpec.properties[property].title}
								bind:value={valves[property]}
								autocomplete="off"
								required
								onchange={() => {
									onchange?.();
								}}
							/>
						{:else}
							<textarea
								class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden border border-gray-100 dark:border-gray-850"
								placeholder={valvesSpec.properties[property].title}
								bind:value={valves[property]}
								autocomplete="off"
								required
								aria-label="Value input"
								onchange={() => {
									onchange?.();
								}}
							></textarea>
						{/if}
					</div>
				</div>
			{/if}

			{#if (valvesSpec.properties[property]?.description ?? null) !== null}
				<div class="text-xs text-gray-500">
					{valvesSpec.properties[property].description}
				</div>
			{/if}
		</div>
	{/each}
{:else}
	<div class="text-xs">{$i18n.t('No valves')}</div>
{/if}
