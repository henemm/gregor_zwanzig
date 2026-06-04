<script lang="ts">
	// Issue #582 — Compare-Edit-Route: auf ComparePreset umgestellt (war: Subscription).
	// Fix: data.preset.* statt data.subscription.*

	import { setContext } from 'svelte';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareWizard from '$lib/components/compare/CompareWizard.svelte';
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

	// Kanal-Layouts aus display_config
	const savedLayouts = state.existingDisplayConfig.channel_layouts as
		| ChannelLayouts
		| undefined;
	if (savedLayouts) state.channelLayouts = savedLayouts;

	setContext('compare-wizard-state', state);
	setContext('compare-wizard-profile', data.profile ?? null);
</script>

<CompareWizard locations={data.locations} />
