<script lang="ts">
	// Epic #1301 Scheibe F2a — /compare/new Anlege-Mount-Punkt.
	// Mountet den Progressive-Tab-Editor CompareNewEditor (struktureller Spiegel
	// von TripNewEditor #622) statt des Alt-Editors CompareEditor mode="create".
	// Der Alt-Editor bleibt als Rollback-Punkt im Repo (Löschung ist F2b, AC-10).
	// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
	//
	// Factory-Pattern: State im script-Block instanziiert (NICHT Top-Level-Modul-Singleton),
	// damit Svelte-5-Runes in Safari die Reaktivitaet behalten. Beide Contexts bleiben
	// gesetzt (Namen unverändert, damit Step2Orte/Organismen weiterlaufen):
	// 'compare-wizard-state' (Editor + gemountete Steps) und
	// 'compare-wizard-profile' (CorridorEditor/VersandTab-Profil-Hints).

	import { setContext } from 'svelte';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareNewEditor from '$lib/components/compare-new/CompareNewEditor.svelte';

	let { data } = $props();
	const state = new CompareWizardState();
	setContext('compare-wizard-state', state);
	setContext('compare-wizard-profile', data.profile ?? null);
</script>

<CompareNewEditor locations={data.locations} />
