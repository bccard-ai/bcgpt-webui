<script lang="ts">
	import { Switch } from 'bits-ui';

	/**
	 * Switch — toggle switch built on bits-ui Switch.
	 *
	 * @example
	 * ```svelte
	 * <Switch bind:state onchange={(e) => console.log(e)} />
	 * ```
	 *
	 * @props state - Bindable boolean toggle state
	 */
	interface Props {
		/** Bindable boolean state. Defaults to `true`. */
		state?: boolean;
		/** Called when the switch value changes. */
		onchange?(...args: unknown[]): void;
	}

	let { state = $bindable(true), onchange = () => {} }: Props = $props();
</script>

<Switch.Root
	bind:checked={state}
	onCheckedChange={(e) => {
		onchange?.(e);
	}}
	class="flex h-5 min-h-5 w-9 shrink-0 cursor-pointer items-center rounded-full px-[3px] mx-[1px] transition  {state
		? ' bg-emerald-600'
		: 'bg-gray-200 dark:bg-transparent'} outline outline-1 outline-gray-100 dark:outline-gray-800"
>
	<Switch.Thumb
		class="pointer-events-none block size-4 shrink-0 rounded-full bg-white transition-transform data-[state=checked]:translate-x-3.5 data-[state=unchecked]:translate-x-0 data-[state=unchecked]:shadow-mini "
	/>
</Switch.Root>
