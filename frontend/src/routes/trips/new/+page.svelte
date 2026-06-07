<script lang="ts">
	// Issue #622 (AC-8): /trips/new nutzt den neuen Progressive Tab Editor.
	// TripWizardShell (alter 5-Schritt-Wizard) ist deprecated für diese Route.
	import TripNewEditor from '$lib/components/trip-new/TripNewEditor.svelte';

	let { data } = $props();
</script>

<TripNewEditor />
