<script lang="ts">
	// Epic #1301 Scheibe F2a — /compare/new Anlege-Mount-Punkt.
	// Mountet den Progressive-Tab-Editor CompareNewEditor (struktureller Spiegel
	// von TripNewEditor #622).
	// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
	//
	// Issue #2727 (Epic #2345, DoD-1): kein Zustandsobjekt und kein Context mehr —
	// der Editor haelt seinen Zustand selbst. Die Seite reicht nur Orte und die
	// Vorlage (?from=<id>, #2277 S2c) als Props durch; die Vorbelegung geschieht
	// einmalig im Editor (bewusst KEIN $effect, AC-10).

	import CompareNewEditor from '$lib/components/compare-new/CompareNewEditor.svelte';

	let { data } = $props();
</script>

<CompareNewEditor locations={data.locations} vorlage={data.vorlage} />
