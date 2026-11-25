<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b: Reiter „Zustellung“ nach Mockup Fassung 3 — EIN Code fuer
	// Trip-Hub und Orts-Briefing-Hub (`context="route"|"vergleich"`, ADR-0097).
	// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md (§1–§5).
	// Reihenfolge: Kopf · Briefing-Zeiten (Anker #versand) · Laufzeit · Warnboxen + Kanal-Tabelle ·
	// Stille Stunden/Anpassen · Beispiel-Alarm. Die Organismen liegen unter organisms/zustellung-tab/
	// und speichern nicht selbst: jede Aenderung geht als neuer Stand an den EINEN Speicherer
	// (zustellungSpeicherung.ts, Owner 'versand' und 'alarme', AC-33). Das Profil wird hier EINMAL
	// geladen und an die Kanal-Tabelle gereicht (AC-36).
	// Abgeloest: WetterMetrikenVersandPanel mit Versand-Abschnitt und der Alarm-Baustein im Reiter
	// (Kanaele je Wettergroesse, amtliche Warnungen, „Alarm ab“, zweite Kanalauswahl, AC-27/AC-31).
	// Issue #3154 (#3122 B3b, Spec Teil B Nr. 14): Telegram-Kurzstil, Mehrtages-Trend und die
	// Metrik-Oberflaeche des Uebergangsblocks sind entfernt — sie bedient die Karte „Was steht wo“.
	// Issue #3036: Uebergangsblock aufgeloest — Pausieren/Aktivieren (nur Orte, Snippet `activation`) steht
	// als fester Abschnitt direkt unter dem Kopf, der Beispiel-Alarm als letzter Abschnitt (bis #2797).
	import { onMount, untrack, type Snippet } from 'svelte';
	import { api } from '$lib/api.js';
	import { locale, t } from '$lib/i18n';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { AlertRule, ComparePreset, Trip } from '$lib/types';
	import Bereichskopf from '$lib/components/molecules/Bereichskopf.svelte';
	import BriefingZeiten from '../../organisms/zustellung-tab/BriefingZeiten.svelte';
	import LaufzeitKarte from '../../organisms/zustellung-tab/LaufzeitKarte.svelte';
	import KanalTabelle from '../../organisms/zustellung-tab/KanalTabelle.svelte';
	import StilleStunden from '../../organisms/zustellung-tab/StilleStunden.svelte';
	import BeispielAlarm from '../../organisms/zustellung-tab/BeispielAlarm.svelte';
	import { kanalStatus, standAusPreset, standAusTrip, type ZustellungProfil, type ZustellungStand } from './zustellungModell.ts';
	import { erstelleZustellungAnlegeSpeicherer, erstelleZustellungSpeicherung, type ZustellungAnlegeMeldung } from './zustellungSpeicherung.ts';

	interface Props {
		context: 'route' | 'vergleich';
		trip?: Trip;
		preset?: ComparePreset;
		onTripUpdate?: (t: Trip) => void;
		onCompareUpdate?: (updated: ComparePreset) => void;
		saveController?: SaveStatus;
		enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
		/** Reiter-Sprung aus der Laufzeit-Karte ("Etappen öffnen →"). Nur route. */
		onJump?: (tab: string) => void;
		/** Zaehler: jede Erhoehung scrollt zu den Briefing-Zeiten (Sprung `#versand`). */
		versandSprung?: number;
		/** Orts-Briefing: Pausieren/Aktivieren-Karte des Hubs (fester Abschnitt direkt unter dem Kopf). */
		activation?: Snippet;
		/** Orts-Briefing: Regeln des Beispiel-Alarms (aus der Metrik-Auswahl des Hubs). */
		beispielAlarmRegeln?: AlertRule[];
		/** #3332: Anlege-Seite — kein Speichern, jede Aenderung geht als Meldung an den Editor. */
		createMode?: boolean;
		/** #3332: Startstand vom Editor (Neuaufbau beim Wechsel Desktop/Mobil, Schritte); sonst aus Trip/Preset. */
		zustellungStart?: ZustellungStand;
		/** #3332: Rueckkanal im Anlegen (`{stand, nutzlast}`), fliesst nie in die Eingangs-Props zurueck. */
		onAnlegeStand?: (m: ZustellungAnlegeMeldung) => void;
	}

	let { context, activation, beispielAlarmRegeln = [], versandSprung = 0, onJump, ...panel }: Props = $props();

	// ── Profil: EIN Abruf je Reiter-Aufruf ──────────────────────────────────────
	let profil = $state<ZustellungProfil | null>(null);
	let profilGeladen = $state(false);
	onMount(() => {
		fetch('/api/auth/profile', { credentials: 'same-origin' })
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null)
			.then((p: ZustellungProfil | null) => {
				profil = p;
				profilGeladen = true;
			});
	});
	const status = $derived.by(() => (void $locale, profilGeladen ? kanalStatus(profil) : null));

	// ── Formularstand + EIN Speicherer ──────────────────────────────────────────
	// Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren): Quelle des
	// Stands, Kennung des Abos und Rueckmeldung der Server-Antwort an den Hub.
	const KONTEXT: Record<'route' | 'vergleich', { stand: () => ZustellungStand; id: () => string | undefined; uebernimm: (a: unknown) => void }> = {
		route: { stand: () => standAusTrip(panel.trip as Trip), id: () => panel.trip?.id, uebernimm: (a) => panel.onTripUpdate?.(a as Trip) },
		vergleich: { stand: () => standAusPreset(panel.preset as ComparePreset), id: () => panel.preset?.id, uebernimm: (a) => panel.onCompareUpdate?.(a as ComparePreset) }
	};
	const startStand = untrack(() => panel.zustellungStart ?? KONTEXT[context].stand());
	let stand = $state<ZustellungStand>(startStand);

	const speicherung = untrack(() => {
		// #3332: im Anlegen meldet der Reiter nur nach oben (kein PUT, kein saveController).
		if (panel.createMode) return erstelleZustellungAnlegeSpeicherer({ context, basis: startStand, anlegen: (m) => panel.onAnlegeStand?.(m) });
		const id = KONTEXT[context].id();
		if (!panel.saveController || !id) return null;
		return erstelleZustellungSpeicherung({
			context,
			id,
			client: api,
			saveController: panel.saveController,
			basis: startStand,
			enqueueHubWrite: panel.enqueueHubWrite,
			onAntwort: uebernimmAntwort
		});
	});

	function uebernimmAntwort(antwort: unknown): void {
		KONTEXT[context].uebernimm(antwort);
	}

	function aendern(neu: ZustellungStand): void {
		stand = neu;
		speicherung?.aenderungMelden(neu);
	}

</script>

<div class="zustellung-tab" data-testid="zustellung-tab" data-context={context}>
	<Bereichskopf titel={$t('zustellung.kopf.titel')} erklaerung={$t('zustellung.kopf.erklaer')} testid="zustellung" />
	{#if activation}
		<div class="zt-aktivierung" data-abschnitt="aktivierung" data-testid="zustellung-aktivierung">{@render activation()}</div>
	{/if}
	<BriefingZeiten {context} {stand} onaendern={aendern} {versandSprung} />
	<LaufzeitKarte {context} {stand} onaendern={aendern} stages={panel.trip?.stages ?? []} {onJump} />
	<KanalTabelle {stand} {status} onaendern={aendern} />
	<StilleStunden {stand} onaendern={aendern} />
	<BeispielAlarm {context} trip={panel.trip} preset={panel.preset} {beispielAlarmRegeln} />
</div>

<style>
	.zustellung-tab {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-5);
		max-width: var(--g-size-1100px);
		padding: var(--g-s-6) var(--g-s-10) var(--g-s-12);
	}
	@media (max-width: 899px) {
		.zustellung-tab {
			gap: var(--g-s-4);
			padding: var(--g-s-5) var(--g-s-4) var(--g-s-10);
		}
	}
</style>
