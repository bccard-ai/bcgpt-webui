<script lang="ts">
	/**
	 * Checkbox — tri-state checkbox (unchecked / checked / indeterminate).
	 *
	 * @example
	 * ```svelte
	 * <Checkbox bind:state={myState} indeterminate={hasPartial} onChange={handleChange} />
	 * ```
	 *
	 * @props state - Current state: 'unchecked' | 'checked'
	 * @props indeterminate - Whether the checkbox supports indeterminate mode
	 * @props disabled - Whether the checkbox is disabled
	 */
	interface Props {
		/** Current state: `'unchecked'` or `'checked'`. */
		state?: string;
		/** Enable indeterminate (partial) mode. */
		indeterminate?: boolean;
		/** Disable the checkbox. */
		disabled?: boolean;
		/** Called with the new state string when toggled. */
		onChange?: (state: string) => void;
	}

	let {
		state = 'unchecked',
		indeterminate = false,
		disabled = false,
		onChange = () => {}
	}: Props = $props();

	let currentState = $derived(state);

	function handleChange() {
		if (disabled) return;

		if (currentState === 'unchecked') {
			currentState = 'checked';
			onChange?.(currentState);
		} else if (currentState === 'checked') {
			currentState = 'unchecked';
			if (!indeterminate) {
				onChange?.(currentState);
			}
		} else if (indeterminate) {
			currentState = 'checked';
			onChange?.(currentState);
		}
	}
</script>

<button
	class=" outline -outline-offset-1 outline-[1.5px] outline-gray-200 dark:outline-gray-600 {state !==
	'unchecked'
		? 'bg-black outline-black '
		: 'hover:outline-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800'} text-white transition-all rounded-sm inline-block w-3.5 h-3.5 relative {disabled
		? 'opacity-50 cursor-not-allowed'
		: ''}"
	onclick={handleChange}
	type="button"
	{disabled}
>
	<div class="top-0 left-0 absolute w-full flex justify-center">
		{#if currentState === 'checked'}
			<svg
				class="w-3.5 h-3.5"
				aria-hidden="true"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
			>
				<path
					stroke="currentColor"
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="3"
					d="m5 12 4.7 4.5 9.3-9"
				/>
			</svg>
		{:else if indeterminate}
			<svg
				class="w-3 h-3.5 text-gray-800 dark:text-white"
				aria-hidden="true"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
			>
				<path
					stroke="currentColor"
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="3"
					d="M5 12h14"
				/>
			</svg>
		{/if}
	</div>
</button>
