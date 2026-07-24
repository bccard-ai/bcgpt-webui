<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import Modal from '$lib/components/common/Modal.svelte';
	import AccessControl from './AccessControl.svelte';

	interface Props {
		/** Whether the modal is visible (two-way bindable) */
		show?: boolean;
		/** Access control configuration (two-way bindable) */
		accessControl?: unknown;
		/** Which access roles to enable (e.g. ['read', 'write']) */
		accessRoles?: string[];
		/** Whether public visibility is allowed */
		allowPublic?: boolean;
		/** Callback when access control changes */
		onChange?: (...args: unknown[]) => void;
	}

	let {
		show = $bindable(false),
		accessControl = $bindable(null),
		accessRoles = ['read'],
		allowPublic = true,
		onChange = () => {}
	}: Props = $props();
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-100 px-5 pt-3 pb-1">
			<div class=" text-lg font-medium self-center font-primary">
				{$i18n.t('Access Control')}
			</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				onclick={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		<div class="w-full px-5 pb-4 dark:text-white">
			<AccessControl bind:accessControl {onChange} {accessRoles} {allowPublic} />
		</div>
	</div>
</Modal>
