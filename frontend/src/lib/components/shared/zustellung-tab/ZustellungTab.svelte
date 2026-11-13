<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b: Reiter „Zustellung“ nach Mockup Fassung 3 — EIN Code fuer
	// Trip-Hub und Orts-Briefing-Hub (`context="route"|"vergleich"`, ADR-0097).
	// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md (§1–§5).
	// Reihenfolge: Kopf · Briefing-Zeiten (Anker #versand) · Laufzeit · Warnboxen + Kanal-Tabelle ·
	// Stille Stunden/Anpassen · Uebergangsblock. Die Organismen liegen unter organisms/zustellung-tab/
	// und speichern nicht selbst: jede Aenderung geht als neuer Stand an den EINEN Speicherer
	// (zustellungSpeicherung.ts, Owner 'versand' und 'alarme', AC-33). Das Profil wird hier EINMAL
	// geladen und an Tabelle und Uebergangsblock gereicht (AC-36).
	// Abgeloest: WetterMetrikenVersandPanel mit Versand-Abschnitt und der Alarm-Baustein im Reiter
	// (Kanaele je Wettergroesse, amtliche Warnungen, „Alarm ab“, zweite Kanalauswahl, AC-27/AC-31).
	import { onMount, untrack, type ComponentProps, type Snippet } from 'svelte';
	import { api } from '$lib/api.js';
	import { locale } from '$lib/i18n';
	import type { AlertRule, ComparePreset, Trip } from '$lib/types';
	import ZustellungKopf from '../../organisms/zustellung-tab/ZustellungKopf.svelte';
	import BriefingZeiten from '../../organisms/zustellung-tab/BriefingZeiten.svelte';
	import LaufzeitKarte from '../../organisms/zustellung-tab/LaufzeitKarte.svelte';
	import KanalTabelle from '../../organisms/zustellung-tab/KanalTabelle.svelte';
	import StilleStunden from '../../organisms/zustellung-tab/StilleStunden.svelte';
	import UebergangBlock from '../../organisms/zustellung-tab/UebergangBlock.svelte';
	import WetterMetrikenVersandPanel from '../WetterMetrikenVersandPanel.svelte';
	import { kanalStatus, standAusPreset, standAusTrip, type ZustellungProfil, type ZustellungStand } from './zustellungModell.ts';
	import { erstelleZustellungSpeicherung } from './zustellungSpeicherung.ts';
	import { erstelleKanalStilSpeicherung, kanalStilStart, type KanalStilStand } from './kanalStilSpeicherung.ts';

	type PanelProps = ComponentProps<typeof WetterMetrikenVersandPanel>;

	interface Props extends Omit<PanelProps, 'context' | 'bereich' | 'mitVersandAbschnitt'> {
		context: 'route' | 'vergleich';
		/** Orts-Briefing: Pausieren/Aktivieren-Karte des Hubs (steht im Uebergangsblock). */
		activation?: Snippet;
		/** Orts-Briefing: Regeln des Beispiel-Alarms (aus der Metrik-Auswahl des Hubs). */
		beispielAlarmRegeln?: AlertRule[];
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
	const startStand = untrack(() => KONTEXT[context].stand());
	let stand = $state<ZustellungStand>(startStand);

	const speicherung = untrack(() => {
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

	// ── Uebergangsblock: Telegram-Kurzstil + Mehrtages-Trend (eigene Felder, bis Teil 2) ─────────
	let kanalStil = $state<KanalStilStand>(untrack(() => kanalStilStart(context, panel.trip, panel.preset)));
	const kanalStilSpeicherung = untrack(() => {
		const id = KONTEXT[context].id();
		if (!panel.saveController || !id) return null;
		return erstelleKanalStilSpeicherung({
			context,
			id,
			client: api,
			saveController: panel.saveController,
			enqueueHubWrite: panel.enqueueHubWrite,
			onAntwort: uebernimmAntwort
		});
	});
	function aendernKanalStil(neu: KanalStilStand): void {
		kanalStil = neu;
		kanalStilSpeicherung?.aenderungMelden(neu);
	}
</script>

<div class="zustellung-tab" data-testid="zustellung-tab" data-context={context}>
	<ZustellungKopf />
	<BriefingZeiten {context} {stand} onaendern={aendern} {versandSprung} />
	<LaufzeitKarte {context} {stand} onaendern={aendern} stages={panel.trip?.stages ?? []} {onJump} />
	<KanalTabelle {stand} {status} onaendern={aendern} />
	<StilleStunden {stand} onaendern={aendern} />
	<UebergangBlock
		{context}
		{...panel}
		{onJump}
		profil={profilGeladen ? profil : null}
		telegramAn={stand.briefing.telegram || stand.alarme.telegram}
		{activation}
		{beispielAlarmRegeln}
		{kanalStil}
		onKanalStil={aendernKanalStil}
	/>
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
