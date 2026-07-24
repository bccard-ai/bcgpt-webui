<!-- BCGPT WebUI - Channel View: Real-time channel conversation by ID -->
<script lang="ts">
	import { page } from '$app/state';

	import Channel from '$lib/components/channel/Channel.svelte';
</script>

<Channel id={page.params.id} />
