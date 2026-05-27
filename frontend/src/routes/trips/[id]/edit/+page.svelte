<script lang="ts">
	import WaypointEditorPage from '$lib/components/edit/WaypointEditorPage.svelte';

	let { data } = $props();
</script>

<WaypointEditorPage trip={data.trip} />
