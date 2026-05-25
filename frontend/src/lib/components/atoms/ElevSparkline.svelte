<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/ElevSparkline -> ui/elev-sparkline.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch (inkl. stroke/fill/showArea).
	import ElevSparkline from '$lib/components/ui/elev-sparkline/ElevSparkline.svelte';
	let props = $props();
</script>

<ElevSparkline {...props} />
