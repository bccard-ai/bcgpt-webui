<!-- BCGPT WebUI - Admin Users: User management with roles and permissions -->
<script>
	import Users from '$lib/components/admin/Users.svelte';
	import Breadcrumb from '$lib/components/common/Breadcrumb.svelte';
</script>

<Breadcrumb items={[{ label: 'Users' }]} />
<Users />
