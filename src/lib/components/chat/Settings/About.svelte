<script lang="ts">
	import { getVersionUpdates } from '$lib/apis';
	import { getOllamaVersion } from '$lib/apis/ollama';
	import { APP_BUILD_HASH, APP_VERSION } from '$lib/constants';
	import { APP_NAME_STORE, config } from '$lib/stores';
	import { compareVersion } from '$lib/utils';
	import { onMount, getContext } from 'svelte';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let ollamaVersion = $state('');

	let updateAvailable = $state<boolean | null>(null);
	let version = $state<{ current: string; latest: string }>({ current: '', latest: '' });

	const checkForVersionUpdates = async () => {
		updateAvailable = null;
		version = await getVersionUpdates('').catch((_error) => {
			return {
				current: APP_VERSION,
				latest: APP_VERSION
			};
		});

		updateAvailable = compareVersion(version.latest, version.current);
	};

	onMount(async () => {
		// Only fetch version when Ollama API is enabled (prevents 500 when not running).
		if ($config?.features?.enable_ollama_api ?? false) {
			ollamaVersion = await getOllamaVersion('').catch((_error) => {
				return '';
			});
		}

		checkForVersionUpdates();
	});
</script>

<div class="flex flex-col h-full justify-between space-y-3 text-sm mb-6">
	<div class=" space-y-3 overflow-y-scroll max-h-[28rem] lg:max-h-full">
		<div>
			<div class=" mb-2.5 text-sm font-medium flex space-x-2 items-center">
				<div>
					{$APP_NAME_STORE}
					{$i18n.t('Version')}
				</div>
			</div>
			<div class="flex w-full justify-between items-center">
				<div class="flex flex-col text-xs text-gray-700 dark:text-gray-200">
					<div class="flex gap-1 items-center">
						<Tooltip content={APP_BUILD_HASH}>
							v{APP_VERSION}
						</Tooltip>
						{#if updateAvailable}
							<span class="text-amber-500 dark:text-amber-400 font-medium">
								→ v{version.latest}
							</span>
						{/if}
					</div>
				</div>
			</div>
		</div>

		{#if ollamaVersion}
			<hr class=" border-gray-100 dark:border-gray-850" />

			<div>
				<div class=" mb-2.5 text-sm font-medium">{$i18n.t('Ollama Version')}</div>
				<div class="flex w-full">
					<div class="flex-1 text-xs text-gray-700 dark:text-gray-200">
						{ollamaVersion ?? 'N/A'}
					</div>
				</div>
			</div>
		{/if}

		<hr class=" border-gray-100 dark:border-gray-850" />

		<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
			Emoji graphics provided by
			<a href="https://github.com/jdecked/twemoji" target="_blank">Twemoji</a>, licensed under
			<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">CC-BY 4.0</a>.
		</div>

		<div>
			<pre class="text-xs text-gray-400 dark:text-gray-500">Copyright 2026 BC Card

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

For third-party attributions, see the NOTICE file included with this distribution.
</pre>
		</div>
	</div>
</div>
