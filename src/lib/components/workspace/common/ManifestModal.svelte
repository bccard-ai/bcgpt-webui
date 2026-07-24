<script lang="ts">
	import { getContext } from 'svelte';

	import Modal from '../../common/Modal.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		/** Whether the modal is visible (two-way bindable) */
		show?: boolean;
		/** Tool manifest metadata containing version and funding URL */
		manifest?: {
			version?: string;
			funding_url?: string;
		};
	}

	let { show = $bindable(false), manifest = {} }: Props = $props();
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class=" text-lg font-medium self-center">{$i18n.t('Show your support!')}</div>
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

		<div class="flex flex-col md:flex-row w-full px-5 pb-4 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					onsubmit={(e) => {
						e.preventDefault();
						show = false;
					}}
				>
					<div class="px-1 text-sm">
						<div class="my-2">
							{$i18n.t(
								'The developers behind this plugin are passionate volunteers from the community. If you find this plugin helpful, please consider contributing to its development.'
							)}
						</div>

						<div class="my-2">
							{$i18n.t(
								'Your entire contribution will go directly to the plugin developer; BCGPT does not take any percentage. However, the chosen funding platform might have its own fees.'
							)}
						</div>

						<hr class="dark:border-gray-800 my-3" />
						<div class="my-2">
							{$i18n.t('Support this plugin:')}
							<!-- eslint-disable svelte/no-navigation-without-resolve -- funding_url is an external full URL; resolve() is only for internal paths and throws at runtime on non-absolute pathnames -->
							<a
								href={manifest.funding_url}
								target="_blank"
								class="underline text-blue-400 hover:text-blue-300">{manifest.funding_url}</a
							>
							<!-- eslint-enable svelte/no-navigation-without-resolve -->
						</div>
					</div>

					<div class="flex justify-end pt-3 text-sm font-medium">
						<button
							class=" px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-gray-100 transition rounded-lg flex flex-row space-x-1 items-center"
							type="submit"
						>
							{$i18n.t('Done')}
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
</Modal>
