<script lang="ts">
	// Issue #492 — Thin-Wrapper auf CompareTile (Block A, #488).
	// Spec: docs/specs/modules/issue_492_home_umbau_wizard_feinschliff.md
	//
	// Delegiert Rendering und Aktionen vollständig an CompareTile.
	// Klick navigiert zur Compare-Detail-Seite, Kebab "Bearbeiten" zur Edit-Route.

	import { goto } from '$app/navigation';
	import CompareTile from '$lib/components/compare/CompareTile.svelte';
	import type { ComparePreset } from '$lib/types.js';

	let { sub }: { sub: ComparePreset } = $props();
</script>

<CompareTile
	{sub}
	compact
	onclick={() => goto('/compare/' + sub.id)}
	onAction={(id) => {
		// Epic #1273 S3: Ziel ist der Hub, nicht mehr die alte /edit-Route.
		if (id === 'edit') goto('/compare/' + sub.id);
	}}
/>
