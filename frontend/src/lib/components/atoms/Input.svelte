<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Input -> ui/input.
	// Compound-Primitive bleibt (Epic #368); reicht alle Props 1:1 durch
	// (inkl. size=lg -> 16px iOS-Zoom-Schutz, data-testid, data-error).
	// Issue #402: value/ref/files explizit als $bindable durchreichen, damit
	// bind:value am Atom-Barrel funktioniert (mustergetreu zu ui/input/input.svelte
	// und zur $bindable-Konvention aus atoms/Switch.svelte).
	import Input from '$lib/components/ui/input/input.svelte';
	let { value = $bindable(), ref = $bindable(null), files = $bindable(), ...rest } = $props();
</script>

<Input bind:value bind:ref bind:files {...rest} />
