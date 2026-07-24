<!-- BCGPT WebUI - Workspace Function Create: Redirects to admin function editor -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	onMount(() => {
		goto(resolve('/admin/functions/create'));
	});
</script>
