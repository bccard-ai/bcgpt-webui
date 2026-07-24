<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Whether the current user is an admin (enables admin-only params). */
		admin?: boolean;
		/** Model parameters object, bindable. Keys map to Ollama/OpenAI param names. */
		params?: Record<string, unknown>;
		/** Callback invoked when any parameter changes. */
		onchange?: (...args: unknown[]) => void;
	}

	let {
		admin = false,
		params = $bindable({
			// Advanced
			stream_response: null, // Set stream responses for this model individually
			function_calling: null,
			seed: null,
			stop: null,
			temperature: null,
			reasoning_effort: null,
			verbosity: null,
			logit_bias: null,
			frequency_penalty: null,
			repeat_last_n: null,
			mirostat: null,
			mirostat_eta: null,
			mirostat_tau: null,
			top_k: null,
			top_p: null,
			min_p: null,
			tfs_z: null,
			num_ctx: null,
			num_batch: null,
			num_keep: null,
			max_tokens: null,
			use_mmap: null,
			use_mlock: null,
			num_thread: null,
			num_gpu: null,
			template: null
		})
	}: Props = $props();

	/**
	 * Cycle a parameter between null (default) and a custom value.
	 * Sets to the custom value when null, resets to null otherwise.
	 * @param key - The parameter key in the params object.
	 * @param customValue - The value to set when toggling on.
	 */
	const toggleParam = (key: string, customValue: unknown) => {
		params[key] = (params[key] ?? null) === null ? customValue : null;
	};

	/**
	 * Cycle a tri-state boolean parameter: null → true → false → null.
	 * @param key - The parameter key in the params object.
	 */
	const toggleTriState = (key: string) => {
		const current = params[key] ?? null;
		if (current === null) {
			params[key] = true;
		} else if (current === true) {
			params[key] = false;
		} else {
			params[key] = null;
		}
	};

	$effect(() => {
		if (params) {
			onchange?.(params);
		}
	});
</script>

<div class=" space-y-1 text-xs pb-safe-bottom">
	<div>
		<Tooltip
			content={$i18n.t(
				'When enabled, the model will respond to each chat message in real-time, generating a response as soon as the user sends a message. This mode is useful for live chat applications, but may impact performance on slower hardware.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Stream Chat Response')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition"
					onclick={() => toggleTriState('stream_response')}
					type="button"
				>
					{#if params.stream_response === true}
						<span class="ml-2 self-center">{$i18n.t('On')}</span>
					{:else if params.stream_response === false}
						<span class="ml-2 self-center">{$i18n.t('Off')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>
	</div>

	<div>
		<Tooltip
			content={$i18n.t(
				'Default mode works with a wider range of models by calling tools once before execution. Native mode leverages the model’s built-in tool-calling capabilities, but requires the model to inherently support this feature.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class=" py-0.5 flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Function Calling')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition"
					onclick={() => toggleParam('function_calling', 'native')}
					type="button"
				>
					{#if params.function_calling === 'native'}
						<span class="ml-2 self-center">{$i18n.t('Native')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Sets the random number seed to use for generation. Setting this to a specific number will make the model generate the same text for the same prompt.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Seed')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('seed', 0)}
				>
					{#if (params?.seed ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.seed ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="number"
						placeholder={$i18n.t('Enter Seed')}
						bind:value={params.seed}
						autocomplete="off"
						min="0"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Sets the stop sequences to use. When this pattern is encountered, the LLM will stop generating text and return. Multiple stop patterns may be set by specifying multiple separate stop parameters in a modelfile.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Stop Sequence')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('stop', '')}
				>
					{#if (params?.stop ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.stop ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg py-2 px-1 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="text"
						placeholder={$i18n.t('Enter stop sequence')}
						bind:value={params.stop}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'The temperature of the model. Increasing the temperature will make the model answer more creatively.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Temperature')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('temperature', 0.8)}
				>
					{#if (params?.temperature ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.temperature ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="0.05"
						bind:value={params.temperature}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.temperature}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Constrains effort on reasoning for reasoning models. Only applicable to reasoning models from specific providers that support reasoning effort.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Reasoning Effort')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('reasoning_effort', 'medium')}
				>
					{#if (params?.reasoning_effort ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.reasoning_effort ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg py-2 px-1 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="text"
						placeholder={$i18n.t('Enter reasoning effort')}
						bind:value={params.reasoning_effort}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Controls how many output tokens the model uses for its answer. Only applicable to GPT-5 family models (low, medium, high).'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Verbosity')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('verbosity', 'medium')}
				>
					{#if (params?.verbosity ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.verbosity ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg py-2 px-1 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="text"
						placeholder={$i18n.t('Enter verbosity (low, medium, high)')}
						bind:value={params.verbosity}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Boosting or penalizing specific tokens for constrained responses. Bias values will be clamped between -100 and 100 (inclusive). (Default: none)'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Logit Bias')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('logit_bias', '')}
				>
					{#if (params?.logit_bias ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.logit_bias ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg pl-2 py-2 px-1 text-sm dark:text-gray-300 dark:bg-gray-850 outline-hidden"
						type="text"
						placeholder={$i18n.t(
							'Enter comma-seperated "token:bias_value" pairs (example: 5432:100, 413:-100)'
						)}
						bind:value={params.logit_bias}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Enable Mirostat sampling for controlling perplexity.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Mirostat')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('mirostat', 0)}
				>
					{#if (params?.mirostat ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.mirostat ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="1"
						bind:value={params.mirostat}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.mirostat}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Influences how quickly the algorithm responds to feedback from the generated text. A lower learning rate will result in slower adjustments, while a higher learning rate will make the algorithm more responsive.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Mirostat Eta')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('mirostat_eta', 0.1)}
				>
					{#if (params?.mirostat_eta ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.mirostat_eta ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.mirostat_eta}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.mirostat_eta}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Controls the balance between coherence and diversity of the output. A lower value will result in more focused and coherent text.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Mirostat Tau')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('mirostat_tau', 5.0)}
				>
					{#if (params?.mirostat_tau ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.mirostat_tau ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="10"
						step="0.5"
						bind:value={params.mirostat_tau}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.mirostat_tau}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="10"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Reduces the probability of generating nonsense. A higher value (e.g. 100) will give more diverse answers, while a lower value (e.g. 10) will be more conservative.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Top K')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('top_k', 40)}
				>
					{#if (params?.top_k ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.top_k ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1000"
						step="0.5"
						bind:value={params.top_k}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_k}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="100"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Works together with top-k. A higher value (e.g., 0.95) will lead to more diverse text, while a lower value (e.g., 0.5) will generate more focused and conservative text.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Top P')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('top_p', 0.9)}
				>
					{#if (params?.top_p ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.top_p ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.top_p}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_p}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Alternative to the top_p, and aims to ensure a balance of quality and variety. The parameter p represents the minimum probability for a token to be considered, relative to the probability of the most likely token. For example, with p=0.05 and the most likely token having a probability of 0.9, logits with a value less than 0.045 are filtered out.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Min P')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('min_p', 0.0)}
				>
					{#if (params?.min_p ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.min_p ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.min_p}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.min_p}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Sets a scaling bias against tokens to penalize repetitions, based on how many times they have appeared. A higher value (e.g., 1.5) will penalize repetitions more strongly, while a lower value (e.g., 0.9) will be more lenient. At 0, it is disabled.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Frequency Penalty')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('frequency_penalty', 1.1)}
				>
					{#if (params?.frequency_penalty ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.frequency_penalty ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="2"
						step="0.05"
						bind:value={params.frequency_penalty}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.frequency_penalty}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Sets a flat bias against tokens that have appeared at least once. A higher value (e.g., 1.5) will penalize repetitions more strongly, while a lower value (e.g., 0.9) will be more lenient. At 0, it is disabled.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Presence Penalty')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded transition flex-shrink-0 outline-none"
					type="button"
					onclick={() => toggleParam('presence_penalty', 0.0)}
				>
					{#if (params?.presence_penalty ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.presence_penalty ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="2"
						step="0.05"
						bind:value={params.presence_penalty}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.presence_penalty}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Control the repetition of token sequences in the generated text. A higher value (e.g., 1.5) will penalize repetitions more strongly, while a lower value (e.g., 1.1) will be more lenient. At 1, it is disabled.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Repeat Penalty (Ollama)')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded transition flex-shrink-0 outline-none"
					type="button"
					onclick={() => toggleParam('repeat_penalty', 1.1)}
				>
					{#if (params?.repeat_penalty ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.repeat_penalty ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="2"
						step="0.05"
						bind:value={params.repeat_penalty}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.repeat_penalty}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Sets how far back for the model to look back to prevent repetition.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Repeat Last N')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('repeat_last_n', 64)}
				>
					{#if (params?.repeat_last_n ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.repeat_last_n ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-1"
						max="128"
						step="1"
						bind:value={params.repeat_last_n}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.repeat_last_n}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-1"
						max="128"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Tail free sampling is used to reduce the impact of less probable tokens from the output. A higher value (e.g., 2.0) will reduce the impact more, while a value of 1.0 disables this setting.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Tfs Z')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('tfs_z', 1)}
				>
					{#if (params?.tfs_z ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.tfs_z ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="0.05"
						bind:value={params.tfs_z}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.tfs_z}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Sets the size of the context window used to generate the next token.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Context Length')}
					{$i18n.t('(Ollama)')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('num_ctx', 2048)}
				>
					{#if (params?.num_ctx ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.num_ctx ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-1"
						max="10240000"
						step="1"
						bind:value={params.num_ctx}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div class="">
					<input
						bind:value={params.num_ctx}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-1"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'The batch size determines how many text requests are processed together at once. A higher batch size can increase the performance and speed of the model, but it also requires more memory.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Batch Size (num_batch)')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('num_batch', 512)}
				>
					{#if (params?.num_batch ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.num_batch ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="256"
						max="8192"
						step="256"
						bind:value={params.num_batch}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.num_batch}
						type="number"
						class=" bg-transparent text-center w-14"
						min="256"
						step="256"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'This option controls how many tokens are preserved when refreshing the context. For example, if set to 2, the last 2 tokens of the conversation context will be retained. Preserving context can help maintain the continuity of a conversation, but it may reduce the ability to respond to new topics.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Tokens To Keep On Context Refresh (num_keep)')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('num_keep', 24)}
				>
					{#if (params?.num_keep ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.num_keep ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-1"
						max="10240000"
						step="1"
						bind:value={params.num_keep}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div class="">
					<input
						bind:value={params.num_keep}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-1"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'This option sets the maximum number of tokens the model can generate in its response. Increasing this limit allows the model to provide longer answers, but it may also increase the likelihood of unhelpful or irrelevant content being generated.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div
				class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
			>
				<div class=" self-center text-md font-medium">
					{$i18n.t('Max Tokens (num_predict)')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('max_tokens', 128)}
				>
					{#if (params?.max_tokens ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.max_tokens ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="131072"
						step="1"
						bind:value={params.max_tokens}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.max_tokens}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	{#if admin}
		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t(
					'Enable Memory Mapping (mmap) to load model data. This option allows the system to use disk storage as an extension of RAM by treating disk files as if they were in RAM. This can improve model performance by allowing for faster data access. However, it may not work correctly with all systems and can consume a significant amount of disk space.'
				)}
				placement="top-start"
				className="inline-tooltip"
			>
				<div
					class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">
						{$i18n.t('use_mmap (Ollama)')}
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						onclick={() => toggleTriState('use_mmap')}
					>
						{#if (params?.use_mmap ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.use_mmap ?? null) !== null}
				<div class="flex justify-between items-center mt-1">
					<div class="text-xs text-gray-500">
						{params.use_mmap ? 'Enabled' : 'Disabled'}
					</div>
					<div class=" pr-2">
						<Switch bind:state={() => params.use_mmap === true, (v) => (params.use_mmap = v)} />
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t(
					"Enable Memory Locking (mlock) to prevent model data from being swapped out of RAM. This option locks the model's working set of pages into RAM, ensuring that they will not be swapped out to disk. This can help maintain performance by avoiding page faults and ensuring fast data access."
				)}
				placement="top-start"
				className="inline-tooltip"
			>
				<div
					class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">
						{$i18n.t('use_mlock (Ollama)')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						onclick={() => toggleTriState('use_mlock')}
					>
						{#if (params?.use_mlock ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.use_mlock ?? null) !== null}
				<div class="flex justify-between items-center mt-1">
					<div class="text-xs text-gray-500">
						{params.use_mlock ? 'Enabled' : 'Disabled'}
					</div>

					<div class=" pr-2">
						<Switch bind:state={() => params.use_mlock === true, (v) => (params.use_mlock = v)} />
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t(
					'Set the number of worker threads used for computation. This option controls how many threads are used to process incoming requests concurrently. Increasing this value can improve performance under high concurrency workloads but may also consume more CPU resources.'
				)}
				placement="top-start"
				className="inline-tooltip"
			>
				<div
					class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">
						{$i18n.t('num_thread (Ollama)')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						onclick={() => toggleParam('num_thread', 2)}
					>
						{#if (params?.num_thread ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_thread ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="1"
							max="256"
							step="1"
							bind:value={params.num_thread}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div class="">
						<input
							bind:value={params.num_thread}
							type="number"
							class=" bg-transparent text-center w-14"
							min="1"
							max="256"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t(
					'Set the number of layers, which will be off-loaded to GPU. Increasing this value can significantly improve performance for models that are optimized for GPU acceleration but may also consume more power and GPU resources.'
				)}
				placement="top-start"
				className="inline-tooltip"
			>
				<div
					class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed"
				>
					<div class=" self-center text-md font-medium">
						{$i18n.t('num_gpu (Ollama)')}
					</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						onclick={() => toggleParam('num_gpu', 0)}
					>
						{#if (params?.num_gpu ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_gpu ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="256"
							step="1"
							bind:value={params.num_gpu}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div class="">
						<input
							bind:value={params.num_gpu}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="256"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<!-- <div class=" py-0.5 w-full justify-between">
			<div class="flex w-full justify-between pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed pb-2 border-b-1 border-gray-100 dark:border-gray-700 border-dashed">
				<div class=" self-center text-md font-medium">{$i18n.t('Template')}</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					onclick={() => toggleParam('template', '')}
				>
					{#if (params?.template ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>

			{#if (params?.template ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<textarea
							class="px-3 py-1.5 text-sm w-full bg-transparent border dark:border-gray-600 outline-hidden rounded-lg -mb-1"
							placeholder={$i18n.t('Write your model template content here')}
							rows="4"
							bind:value={params.template}></textarea>
					</div>
				</div>
			{/if}
		</div> -->
	{/if}
</div>
