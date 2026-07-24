<script lang="ts">
	import { getContext } from 'svelte';
	import { toolServers } from '$lib/stores';

	import Modal from '../common/Modal.svelte';
	import Collapsible from '../common/Collapsible.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Controls modal visibility */
		show?: boolean;
	}

	let { show = $bindable(false) }: Props = $props();

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');
</script>

<Modal bind:show size="md">
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-0.5">
			<div class=" text-lg font-medium self-center">{$i18n.t('Available Tool Servers')}</div>
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

		<div class="px-5 pb-5 w-full flex flex-col justify-center">
			<div class=" text-sm dark:text-gray-300 mb-2">
				{$i18n.t('BCGPT can use tools provided by any OpenAPI server.')} <br /><a
					class="underline"
					href="https://github.com/bccard-ai/openapi-servers"
					target="_blank">{$i18n.t('Learn more about OpenAPI tool servers.')}</a
				>
			</div>
			<div class=" text-sm dark:text-gray-300 mb-1">
				{#each $toolServers as toolServer (toolServer?.url)}
					<Collapsible buttonClassName="w-full" chevron>
						<div>
							<div class="text-base font-medium dark:text-gray-100 text-gray-800">
								{toolServer?.openapi?.info?.title} - v{toolServer?.openapi?.info?.version}
							</div>

							<div class="text-sm text-gray-500">
								{toolServer?.openapi?.info?.description}
							</div>

							<div class="text-sm text-gray-500">
								{toolServer?.url}
							</div>
						</div>

						{#snippet content()}
							<div>
								{#each toolServer?.specs ?? [] as toolSpec (toolSpec?.name)}
									<div class="my-1">
										<div class="font-medium text-gray-800 dark:text-gray-100">
											{toolSpec?.name}
										</div>

										<div>
											{toolSpec?.description}
										</div>
									</div>
								{/each}
							</div>
						{/snippet}
					</Collapsible>
				{/each}
			</div>
		</div>
	</div>
</Modal>
