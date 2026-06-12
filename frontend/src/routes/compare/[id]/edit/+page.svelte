<script lang="ts">
	// Issue #679 — Compare-Edit-Route: CompareWizard → CompareEditor mode="edit".
	// Spec: docs/specs/modules/issue_679_compare_editor_edit.md
	// Löst: (1) save() traf /api/subscriptions statt /api/compare/presets,
	//        (2) empfaenger wurde beim Speichern gelöscht (fehlender Round-Trip-Spread).
	//
	// State-Initialisierung aus data.preset.* unverändert.
	// data.preset wird zusätzlich als Prop an CompareEditor gegeben (Round-Trip-Spread + Status-Dot).

	import { setContext } from 'svelte';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareEditor from '$lib/components/compare/CompareEditor.svelte';
	import type { IdealRange } from '$lib/components/compare/compareMetricDefs';
	import type { ActivityProfile, ChannelLayouts } from '$lib/types';

	let { data } = $props();

	const state = new CompareWizardState();
	state.isEditMode = true;
	state.subscriptionId = data.preset.id;
	state.name = data.preset.name ?? '';
	state.activityProfile = (data.preset.profil as ActivityProfile | null) ?? null;
	state.pickedIds = data.preset.location_ids ?? [];
	state.subscriptionEnabled = true; // ComparePreset hat kein enabled-Feld
	state.existingDisplayConfig = (data.preset.display_config as Record<string, unknown>) ?? {};
	state.region = (state.existingDisplayConfig.region as string) ?? '';
	state.idealRanges =
		(state.existingDisplayConfig.ideal_ranges as Record<string, IdealRange>) ?? {};

	// Versand-Felder aus preset mappen
	state.schedule = data.preset.schedule ?? 'daily';
	state.weekday = data.preset.weekday ?? 0;
	state.timeWindowStart = data.preset.hour_from ?? 9;
	state.timeWindowEnd = data.preset.hour_to ?? 16;
	state.forecastHours = data.preset.forecast_hours ?? 48; // Issue #764

	// Kanal-Layouts aus display_config
	const savedLayouts = state.existingDisplayConfig.channel_layouts as
		| ChannelLayouts
		| undefined;
	if (savedLayouts) state.channelLayouts = savedLayouts;

	// Issue #680: Slice 3 — active_metrics aus display_config wiederherstellen (AC-10)
	const savedActiveMetrics = state.existingDisplayConfig.active_metrics as string[] | undefined;
	if (savedActiveMetrics && savedActiveMetrics.length > 0) {
		state.activeMetricKeys = savedActiveMetrics;
		state.metricsManuallyEdited = true;
	}

	setContext('compare-wizard-state', state);
	setContext('compare-wizard-profile', data.profile ?? null);
</script>

<CompareEditor mode="edit" locations={data.locations} preset={data.preset} />
