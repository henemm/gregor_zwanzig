<script lang="ts">
	// Issue #373 — Re-Export-Wrapper: mobile/BottomNav -> ui/sidebar/BottomNav.
	//
	// Duenner Bridge-Wrapper (Konsolidierung statt Duplikat, analog #371).
	// Reicht alle Props 1:1 durch — inkl. der additiven mobile-shell-Props
	// (active, onChange).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-5)
	import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';
	let props = $props();
</script>

<BottomNav {...props} />
