<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Input -> ui/input.
	// Compound-Primitive bleibt (Epic #368); dies reicht alle Props 1:1 durch
	// (inkl. size=lg -> 16px iOS-Zoom-Schutz, data-testid, data-error).
	import Input from '$lib/components/ui/input/input.svelte';
	let props = $props();
</script>

<Input {...props} />
