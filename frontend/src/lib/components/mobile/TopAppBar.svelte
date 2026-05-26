<script lang="ts">
	// Issue #373 — Re-Export-Wrapper: mobile/TopAppBar -> ui/sidebar/TopAppBar.
	//
	// Duenner Bridge-Wrapper (Konsolidierung statt Duplikat, analog #371).
	// Reicht alle Props 1:1 durch — inkl. der additiven mobile-shell-Props
	// (eyebrow, leftIcon, right, dense, scrolled).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-5)
	import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';
	// F001: mobileMenuOpen explizit bindable durchreichen — sonst propagiert der
	// Hamburger-Toggle der ui/sidebar/TopAppBar nicht zurueck zum Konsumenten
	// (MobileShell). Rest der Props 1:1 via {...props}.
	let { mobileMenuOpen = $bindable(false), ...props } = $props();
</script>

<TopAppBar bind:mobileMenuOpen {...props} />
