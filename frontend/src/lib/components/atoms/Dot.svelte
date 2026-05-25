<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Dot -> ui/dot.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch (inkl. numerischer size).
	import Dot from '$lib/components/ui/dot/Dot.svelte';
	let props = $props();
</script>

<Dot {...props} />
