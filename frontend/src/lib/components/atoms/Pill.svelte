<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Pill -> ui/pill.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch (inkl. Sandbox-Tone-Aliase).
	import Pill from '$lib/components/ui/pill/Pill.svelte';
	let props = $props();
</script>

<Pill {...props} />
