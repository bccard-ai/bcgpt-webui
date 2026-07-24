<script lang="ts">
	import { getContext } from 'svelte';
	import Checkbox from '$lib/components/common/Checkbox.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { marked } from 'marked';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const helpText = {
		vision: $i18n.t('Agent accepts image inputs'),
		usage: $i18n.t(
			'Sends `stream_options: { include_usage: true }` in the request.\nSupported providers will return token usage information in the response when set.'
		),
		citations: $i18n.t('Displays citations in the response'),
		web_search: $i18n.t(
			'Performs a web search by default and includes the results as context (combined with RAG)'
		)
	};

	interface Props {
		/** Map of capability flags to enable/disable */
		capabilities?: {
			vision?: boolean;
			usage?: boolean;
			citations?: boolean;
			web_search?: boolean;
		};
	}

	let { capabilities = $bindable({}) }: Props = $props();
</script>

<div>
	<div class="flex w-full justify-between mb-1">
		<div class=" self-center text-sm font-semibold">{$i18n.t('Capabilities')}</div>
	</div>
	<div class="flex">
		{#each Object.keys(capabilities) as capability (capability)}
			<div class=" flex items-center gap-2 mr-3">
				<Checkbox
					state={capabilities[capability] ? 'checked' : 'unchecked'}
					onchange={(e: CustomEvent) => {
						capabilities[capability] = e.detail === 'checked';
					}}
				/>

				<div class=" py-0.5 text-sm capitalize">
					<Tooltip content={marked.parse(helpText[capability]) as string}>
						{$i18n.t(capability)}
					</Tooltip>
				</div>
			</div>
		{/each}
	</div>
</div>
