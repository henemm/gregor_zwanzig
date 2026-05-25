<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Card -> ui/card (Compound-Root).
	// Compound-Struktur bleibt unangetastet (Epic #368); dies ist nur der
	// einfache padding/accent-Fall, der auf ui/card aufsetzt.
	import { Card } from '$lib/components/ui/card/index.js';
	let props = $props();
</script>

<Card {...props} />
