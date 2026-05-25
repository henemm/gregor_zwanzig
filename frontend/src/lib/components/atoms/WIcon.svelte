<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/WIcon -> ui/wicon.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch (kind-Default cloud).
	import WIcon from '$lib/components/ui/wicon/WIcon.svelte';
	let props = $props();
</script>

<WIcon {...props} />
