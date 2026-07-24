<!-- BCGPT WebUI - Workspace Redirect: Routes to first permitted workspace section -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { user } from '$lib/stores';
	import { get } from 'svelte/store';
	import { onMount } from 'svelte';

	onMount(() => {
		if (get(user)?.role !== 'admin') {
			if (get(user)?.permissions?.workspace?.models) {
				goto(resolve('/workspace/agents'));
			} else if (get(user)?.permissions?.workspace?.knowledge) {
				goto(resolve('/workspace/knowledge'));
			} else if (get(user)?.permissions?.workspace?.prompts) {
				goto(resolve('/workspace/prompts'));
			} else if (get(user)?.permissions?.workspace?.tools) {
				goto(resolve('/workspace/tools'));
			} else {
				goto(resolve('/'));
			}
		} else {
			goto(resolve('/workspace/agents'));
		}
	});
</script>
