<script lang="ts">
	// Issue #2880 (Epic #2345, ADR-0097): EINE Reiterfläche für Trip und Ortsvergleich.
	// Trägt den einheitlichen Rand der Hub-Reiter ohne eigenen Rand (Übersicht, Etappen/Orte);
	// die Reiter mit eigenem Rand (Wetter-Metriken, Wertebereiche, Alarme) stehen ohne sie.
	// Spec: docs/specs/modules/rework_2880_paritaet_reiterflaeche_anlegefelder.md
	import type { Snippet } from 'svelte';

	interface Props {
		/** Muss auf „-reiterflaeche" enden (PF-3 sucht `[data-testid$="-reiterflaeche"]`). */
		testid: string;
		children?: Snippet;
	}

	let { testid, children }: Props = $props();
</script>

<div class="hub-reiterflaeche" data-testid={testid}>{@render children?.()}</div>

<style>
	.hub-reiterflaeche {
		position: relative;
		padding: 28px 40px 60px;
		max-width: 1480px;
	}
	@media (max-width: 899px) {
		.hub-reiterflaeche {
			padding: 20px 16px 48px;
		}
	}
</style>
