<script lang="ts">
	/**
	 * SensitiveInput — text input with an inline show/hide eye toggle for
	 * sensitive values (API keys, tokens, passwords).
	 *
	 * Token-driven and h-8 to match the Input/Select Settings kit. The wrapper
	 * is the styled surface (border/bg/focus ring) and the <input> is transparent
	 * inside it, so the eye toggle sits neatly within the field. An optional
	 * `mono` variant renders identifier-style secrets (API keys) in monospace.
	 *
	 * @example
	 * ```svelte
	 * <SensitiveInput bind:value placeholder="API Key" mono />
	 * ```
	 */
	import { cn } from '$lib/utils/cn';

	interface Props {
		/** Bindable text value. */
		value?: string;
		/** Input placeholder. */
		placeholder?: string;
		/** HTML required attribute. Defaults to `true`. */
		required?: boolean;
		/** Make the input read-only (no toggle, value disabled). */
		readOnly?: boolean;
		/** Render the value in monospace — for API keys, tokens. */
		mono?: boolean;
		/** Extra classes on the wrapper (the styled surface). */
		outerClassName?: string;
		/** Extra classes on the inner <input>. */
		inputClassName?: string;
		/** Extra classes on the show/hide toggle button. */
		showButtonClassName?: string;
	}

	let {
		value = $bindable(''),
		placeholder = '',
		required = true,
		readOnly = false,
		mono = false,
		outerClassName = '',
		inputClassName = '',
		showButtonClassName = ''
	}: Props = $props();

	let show = $state(false);
</script>

<div
	class={cn(
		'relative flex h-8 w-full items-center rounded-md border border-input bg-background pl-3 pr-1.5 text-sm shadow-xs transition-colors focus-within:border-ring focus-within:outline-none focus-within:ring-2 focus-within:ring-ring',
		mono && 'font-mono text-[13px]',
		readOnly && 'opacity-60',
		outerClassName
	)}
>
	<input
		class={cn(
			'flex-1 bg-transparent outline-none placeholder:text-muted-foreground',
			inputClassName,
			show ? '' : 'password'
		)}
		{placeholder}
		bind:value
		required={required && !readOnly}
		disabled={readOnly}
		autocomplete="off"
		type="text"
	/>
	<button
		class={cn('p-1 text-muted-foreground transition hover:text-foreground', showButtonClassName)}
		type="button"
		tabindex={-1}
		aria-label="toggle visibility"
		onclick={(e: MouseEvent) => {
			e.preventDefault();
			show = !show;
		}}
	>
		{#if show}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 16 16"
				fill="currentColor"
				class="size-4"
			>
				<path
					fill-rule="evenodd"
					d="M3.28 2.22a.75.75 0 0 0-1.06 1.06l10.5 10.5a.75.75 0 1 0 1.06-1.06l-1.322-1.323a7.012 7.012 0 0 0 2.16-3.11.87.87 0 0 0 0-.567A7.003 7.003 0 0 0 4.82 3.76l-1.54-1.54Zm3.196 3.195 1.135 1.136A1.502 1.502 0 0 1 9.45 8.389l1.136 1.135a3 3 0 0 0-4.109-4.109Z"
					clip-rule="evenodd"
				/>
				<path
					d="m7.812 10.994 1.816 1.816A7.003 7.003 0 0 0 1.38 8.28a.87.87 0 0 1 0-.566 6.985 6.985 0 0 1 1.113-2.039l2.513 2.513a3 3 0 0 0 2.806 2.806Z"
				/>
			</svg>
		{:else}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 16 16"
				fill="currentColor"
				class="size-4"
			>
				<path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" />
				<path
					fill-rule="evenodd"
					d="M1.38 8.28a.87.87 0 0 1 0-.566 7.003 7.003 0 0 1 13.238.006.87.87 0 0 1 0 .566A7.003 7.003 0 0 1 1.379 8.28ZM11 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
					clip-rule="evenodd"
				/>
			</svg>
		{/if}
	</button>
</div>
