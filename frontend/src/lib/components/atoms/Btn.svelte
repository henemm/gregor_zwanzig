<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Btn -> ui/btn.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch (inkl. quiet-Variante).
	import Btn from '$lib/components/ui/btn/Btn.svelte';
	let props = $props();
</script>

<Btn {...props} />
