<!-- BCGPT WebUI - Personalization Settings: User profile and memory preferences -->
<script lang="ts">
	import { get } from 'svelte/store';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { settings, models, config } from '$lib/stores';
	import { getModels as _getModels } from '$lib/apis';
	import { updateUserSettings } from '$lib/apis/users';
	import Personalization from '$lib/components/chat/Settings/Personalization.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const saveSettings = async (updated: Record<string, unknown>) => {
		await settings.set({ ...get(settings), ...updated });
		await models.set(await getModels());
		await updateUserSettings('', { ui: get(settings) });
	};

	const getModels = async () => {
		return await _getModels(
			'',
			get(config)?.features?.enable_direct_connections && (get(settings)?.directConnections ?? null)
		);
	};
</script>

<div class="flex flex-col h-full">
	<Personalization
		{saveSettings}
		onSave={() => {
			toast.success($i18n.t('Settings saved successfully!'));
		}}
	/>
</div>
