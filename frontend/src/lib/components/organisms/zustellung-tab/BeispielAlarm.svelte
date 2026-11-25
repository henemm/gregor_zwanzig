<script lang="ts">
	// Issue #3036 (Spec rework_3036_uebergangsblock_aufloesen.md, AC-7): Beispiel-Alarm als eigener,
	// letzter Abschnitt des Reiters Zustellung (Trip und Orte). Loest den Uebergangsblock aus #2795 ab;
	// zieht mit #2797 in den Hub-Kopf („Test schicken“).
	import type { ComponentProps } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import AlertPreviewCard from '$lib/components/alerts-tab/AlertPreviewCard.svelte';
	import { t } from '$lib/i18n';
	import type { AlertRule, ComparePreset, Trip } from '$lib/types';

	interface Props {
		context: 'route' | 'vergleich';
		trip?: Trip;
		preset?: ComparePreset;
		/** Orts-Briefing: Regeln des Beispiel-Alarms (aus der Metrik-Auswahl des Hubs). */
		beispielAlarmRegeln?: AlertRule[];
	}
	let { context, trip, preset, beispielAlarmRegeln = [] }: Props = $props();

	// Trip mit seinen Regeln und Etappen, Orte mit den Regeln aus der Metrik-Auswahl und den Orten
	// (Kontext-Unterschied als Daten, Ratsche context_herkunft_zweige_eingefroren).
	const BEISPIEL: Record<'route' | 'vergleich', () => ComponentProps<typeof AlertPreviewCard>> = {
		route: () => ({ kind: 'route', id: trip?.id ?? '', alertRules: trip?.alert_rules ?? [], stages: trip?.stages ?? [] }),
		vergleich: () => ({ kind: 'vergleich', id: preset?.id ?? '', alertRules: beispielAlarmRegeln, locationIds: preset?.location_ids ?? [] })
	};
	const beispiel = $derived(BEISPIEL[context]());
</script>

<section class="zt-beispiel" data-abschnitt="beispiel-alarm" data-testid="zustellung-beispiel-alarm">
	<Eyebrow>{$t('alarme.beispiel_warnung')}</Eyebrow>
	<AlertPreviewCard {...beispiel} />
</section>

<style>
	.zt-beispiel {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
</style>
