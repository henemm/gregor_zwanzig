<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3 (Stufe 3.2): Reiter „Wetter" fuer Trip (`route`) und
	// Orts-Briefing (`vergleich`) — Hub und Anlege-Kette, EIN Code (Trip/Ortsvergleich-Teilung, #1170).
	// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md §4 (Mockup Fassung 3), AC-9 bis AC-21, AC-38 bis AC-42.
	//
	// Kopf mit Lade-/Fehlerzustand (W1), Vorlage-Karte (W4), „Alarm ab für alle" (A3, A5),
	// Metrik-Zeilen in fuenf Gruppen, „Nicht im Briefing", Amtliche Warnungen & Radar, Anpassen.
	// Genau EIN Speicherer (AC-38): Trip zwei disjunkte PUTs, Orts-Briefing ein Eintrag in der
	// Hub-Schreibschlange (wetterTabSpeicherung.ts); beim Anlegen geht der Stand an die Anlege-Seite.
	// Der Reiter liest das Abo nur beim ersten Laden (Seitenneuaufbau nach Konflikt-Retry, #2317).
	// #2913 Teil 2 (K-1, K-6): Organismus mit Zustand, Laden und Speichern; die Seite ist
	// shared/WetterTab.svelte. Ladeanzeige aus dem Atom Skelett, „Erneut laden“ als Btn.
	import { onMount } from 'svelte';
	import { Btn, Skelett } from '$lib/components/atoms';
	import { api } from '$lib/api';
	import type { ComparePreset, MetricPreset, Trip } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { t, locale } from '$lib/i18n';
	import { metricLabel } from '$lib/i18n/metricLabel';
	import { loadCompareSelectionEntries } from '../../shared/corridor-editor/compareMetricCatalogLoader.ts';
	import type { CompareSelectionEntry } from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
	import VorlageKarte from './VorlageKarte.svelte';
	import AlarmAbKopf from './AlarmAbKopf.svelte';
	import MetrikZeile from './MetrikZeile.svelte';
	import NichtImBriefing from './NichtImBriefing.svelte';
	import WarnungenRadarKarte from './WarnungenRadarKarte.svelte';
	import AnpassenKarte from './AnpassenKarte.svelte';
	import { alarmZaehler, altSchluesselAusKatalog, eigeneVorlageAmpel, gewitterFehler, grenzenFehler, verschmelzen, zeilenGruppen } from '../../shared/wetter-tab/ampelModell.ts';
	import type { AlarmAb, AltSchluessel, Farbe, Kontext } from '../../shared/wetter-tab/ampelModell.ts';
	import { ladeWetterDaten, type WetterDaten } from '../../shared/wetter-tab/wetterTabLaden.ts';
	import { SPEICHERER, anlegeSpeicherer, type SpeicherOptionen } from '../../shared/wetter-tab/wetterTabSpeicherung.ts';
	import * as Z from '../../shared/wetter-tab/wetterZustand.ts';

	interface Props {
		context: Kontext;
		trip?: Trip;
		preset?: ComparePreset | Record<string, unknown>;
		/** Anlege-Kette: kein PUT, der Stand geht per `onAnlegeStand` an die Anlege-Seite. */
		createMode?: boolean;
		saveController?: SaveStatus;
		enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
		onTripUpdate?: (t: Trip) => void;
		onCompareUpdate?: (p: ComparePreset) => void;
		onAnlegeStand?: (nutzlast: unknown) => void;
	}
	let { context, trip, preset, createMode = false, saveController, enqueueHubWrite, onTripUpdate, onCompareUpdate, onAnlegeStand }: Props = $props();

	/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). */
	const MIT_RADAR: Record<Kontext, boolean> = { route: false, vergleich: true };
	// Vergleichs-Katalog: Auswertung neuer Metriken und Altformat-Schluessel von `active_metrics`
	// (Fix-Loop 3, C2 — muss VOR der Erst-Hydration da sein). Scheitert er, ist das ein Ladefehler
	// wie beim Metrik-Katalog (Fix-Loop 4, F001): Fehlerzustand AC-9, keine Hydration, kein Speichern;
	// „Erneut laden" fragt ihn neu an (der Lader cacht keinen Fehler). Der Trip braucht ihn nicht.
	const VERGLEICHS_KATALOG: Record<Kontext, () => Promise<CompareSelectionEntry[]>> = {
		route: async () => [],
		vergleich: () => loadCompareSelectionEntries()
	};

	let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');
	let daten = $state<WetterDaten | null>(null);
	let stand = $state<Z.WetterStand | null>(null);
	let offen = $state<string | null>(null);
	let entwurf = $state<Z.Entwurf | null>(null);
	let fehler = $state<string[]>([]);
	let hinzu = $state<string | null>(null);
	let aggregation: (id: string) => string = () => 'max';
	let altSchluessel: AltSchluessel = {};
	let gemeldet = '';

	const abo = (): Z.AboSicht => (trip ?? preset ?? {}) as Z.AboSicht;
	const uebernahme: Record<Kontext, (a: unknown) => void> = {
		route: (a) => onTripUpdate?.(a as Trip),
		vergleich: (a) => onCompareUpdate?.(a as ComparePreset)
	};

	function optionen(): SpeicherOptionen {
		return {
			client: api,
			stand: () => stand!,
			vorlagen: () => daten!.vorlagen,
			abo,
			saveController,
			enqueueHubWrite,
			uebernehmen: (a) => uebernahme[context](a),
			neuGeladen,
			anlegen: onAnlegeStand,
			aggregationFuer: (id) => aggregation(id),
			altSchluessel
		};
	}
	const melden = () => (createMode ? anlegeSpeicherer(optionen(), context) : SPEICHERER[context](optionen())).melden();
	const signatur = (s: Z.WetterStand) => JSON.stringify([Z.mengeVon(s, daten!.vorlagen), s.auswahl, s.warnungenAn, s.radarAn, s.tagesfenster]);

	async function laden(): Promise<void> {
		phase = 'laedt';
		try {
			const [d, katalog] = await Promise.all([ladeWetterDaten(api, context), VERGLEICHS_KATALOG[context]()]);
			aggregation = (id) => katalog.find((e) => e.metric_id === id)?.aggregation ?? 'max';
			altSchluessel = altSchluesselAusKatalog(katalog);
			daten = d;
			if (!stand) {
				stand = Z.standAusAbo(context, abo(), d.vorlagen, altSchluessel);
				gemeldet = signatur(stand);
				if (createMode) melden();
			}
			phase = 'bereit';
		} catch {
			phase = 'fehler';
		}
	}
	onMount(() => {
		void laden();
	});

	/** Jede Aenderung: neuer Stand; nur wenn sich Gespeichertes aendert, meldet der Speicherer. */
	function aendern(neu: Z.WetterStand): void {
		stand = neu;
		const sig = signatur(neu);
		if (sig === gemeldet) return;
		gemeldet = sig;
		melden();
	}
	function neuGeladen(frisch: Z.AboSicht): void {
		if (!daten) return;
		stand = Z.standAusAbo(context, frisch, daten.vorlagen, altSchluessel);
		gemeldet = signatur(stand);
		offen = null;
		entwurf = null;
		fehler = [];
	}

	// ── Grenzen ändern (AC-16, AC-17, AC-18) ──────────────────────────────────
	function entwurfFehler(e: Z.Entwurf): string[] {
		return e.thunder ? gewitterFehler({ ...(stand!.ampel.thunder ?? {}), ...e.thunder }) : grenzenFehler(e);
	}
	function fertig(): boolean {
		if (!stand || !offen) return true;
		const f = entwurf ? entwurfFehler(entwurf) : [];
		if (f.length) return ((fehler = f), false);
		const neu = Z.mitEntwurf(stand, entwurf);
		offen = null;
		entwurf = null;
		fehler = [];
		aendern(neu);
		return true;
	}
	function grenzenUmschalten(id: string): void {
		if (offen === id) return void fertig();
		if (offen && !fertig()) return;
		offen = id;
		entwurf = null;
		fehler = [];
	}
	function grenzWert(id: string, seite: 'lower' | 'upper', farbe: Farbe, w: number | null): void {
		const z = stand!.ampel.metrics?.[id] ?? {};
		const basis: Z.Entwurf = entwurf?.id === id ? entwurf : { id, lower: { ...(z.lower ?? {}) }, upper: { ...(z.upper ?? {}) } };
		entwurf = { ...basis, [seite]: { ...(basis[seite] ?? {}), [farbe]: w } };
	}
	function gewitterWahl(stufe: 'mittel' | 'hoch', farbe: Farbe): void {
		const basis: Z.Entwurf = entwurf?.thunder ? entwurf : { id: 'thunder', thunder: {} };
		entwurf = { ...basis, thunder: { ...basis.thunder, [stufe]: farbe } };
	}

	// ── Auswahl, Vorlage, Karten ─────────────────────────────────────────────
	function entfernen(id: string): void {
		if (offen === id) ((offen = null), (entwurf = null), (fehler = []));
		hinzu = null;
		aendern(Z.ohneMetrik(stand!, id));
	}
	function hinzufuegen(id: string): void {
		aendern(Z.mitMetrik(stand!, id));
		hinzu = name(id);
	}
	function vorlageSetzen(neu: Z.WetterStand): void {
		offen = null;
		entwurf = null;
		fehler = [];
		aendern(neu);
	}
	function eigeneUebernehmen(id: string): void {
		const e = daten!.eigene.find((x) => x.id === id);
		if (e) vorlageSetzen(Z.mitEigenerVorlage(stand!, e.ampel, daten!.vorlagen));
	}
	function vorlageGespeichert(p: MetricPreset): void {
		if (!daten) return;
		const neu = { id: p.id, name: p.name, ampel: eigeneVorlageAmpel(p, daten.vorlagen) };
		if ((p.kind ?? context) === context) daten = { ...daten, eigene: [neu, ...daten.eigene] };
	}

	function name(id: string): string {
		const e = daten?.eig[id];
		return metricLabel({ label: e?.label_de ?? id, label_de: e?.label_de, label_en: e?.label_en }, $locale);
	}

	const anzeige = $derived(stand ? Z.mitEntwurf(stand, entwurf, true) : null);
	const vorlagen = $derived(daten?.vorlagen ?? {});
	const abweichungen = $derived(anzeige && daten ? Z.abweichungenVon(anzeige, vorlagen) : 0);
	const anzeigeMenge = $derived(anzeige && daten ? Z.mengeVon(anzeige, vorlagen) : null);
	const gruppen = $derived(anzeige && daten ? zeilenGruppen(anzeige.auswahl, daten.eig) : []);
	const zaehler = $derived(anzeige && daten ? alarmZaehler(anzeige.ampel, anzeige.auswahl, daten.eig) : null);
	const nichtIm = $derived(
		anzeige && daten
			? zeilenGruppen(Object.keys(daten.eig), daten.eig).flatMap((g) => g.metriken).filter((id) => !anzeige.auswahl.includes(id)).map((id) => ({ id, name: name(id) }))
			: []
	);
	const aboAmpel = $derived(stand && daten ? verschmelzen(vorlagen[stand.vorlageId], Z.mengeVon(stand, vorlagen)) : {});
	const vorlageLabel = $derived(daten?.liste.find((v) => v.id === stand?.vorlageId)?.label ?? stand?.vorlageId ?? '');

	/** Weicht die Zeile in Grenzen (bzw. Gewitterfarben) von der Vorlage ab? */
	function grenzenAbweichend(id: string): boolean {
		if (daten?.eig[id]?.allowed_sides === 'level') return Object.keys(anzeigeMenge?.thunder ?? {}).length > 0;
		const z = anzeigeMenge?.metrics?.[id];
		return !!z && ('lower' in z || 'upper' in z);
	}
	// i18n-dynamic: wetter.gruppe.
	const gruppenTitel = (g: string) => $t(`wetter.gruppe.${g}` as 'wetter.gruppe.wind');
</script>

<section class="wt" data-testid="wetter-tab" data-context={context}>
	<header class="wt-kopf">
		<h2 data-testid="wetter-tab-titel">{$t('wetter.kopf.titel')}</h2>
		<p data-testid="wetter-tab-erklaer">{$t('wetter.kopf.erklaerung')}</p>
	</header>

	{#if phase === 'laedt'}
		<div class="wt-karte wt-laden" data-testid="wetter-tab-laden" aria-busy="true">
			<span aria-hidden="true">{$t('wetter.kopf.laden')}</span>
			<Skelett label={$t('wetter.kopf.laden')} />
		</div>
	{:else if phase === 'fehler'}
		<div class="wt-karte wt-fehler" role="alert" data-testid="wetter-tab-fehler">
			<p>{$t('wetter.kopf.fehler')}</p>
			<Btn variant="accent" size="tap" data-testid="wetter-tab-erneut-laden" onclick={() => void laden()}>{$t('wetter.kopf.erneut_laden')}</Btn>
		</div>
	{:else if stand && daten && anzeige && zaehler}
		<VorlageKarte
			{context}
			vorlageId={stand.vorlageId}
			liste={daten.liste}
			eigene={daten.eigene}
			{abweichungen}
			metrikName={name}
			{aboAmpel}
			onUebernehmen={(id) => vorlageSetzen(Z.mitVorlage(stand!, id, vorlagen))}
			onEigene={eigeneUebernehmen}
			onZuruecksetzen={() => vorlageSetzen(Z.mitVorlage(stand!, stand!.vorlageId, vorlagen))}
			onGespeichert={vorlageGespeichert}
		/>
		<div class="wt-karte wt-metriken">
			<AlarmAbKopf {zaehler} onAlle={(s: AlarmAb) => aendern(Z.mitAlarmAbFuerAlle(stand!, s, daten!.eig))} />
			{#each gruppen as g (g.gruppe)}
				<div class="wt-gruppe" data-testid="wetter-gruppe-{g.gruppe}">
					<div class="wt-gh">{gruppenTitel(g.gruppe)}</div>
					{#each g.metriken as id (id)}
						<MetrikZeile
							{id}
							name={name(id)}
							eig={daten.eig[id]}
							eintrag={anzeige.ampel.metrics?.[id]}
							thunder={anzeige.ampel.thunder}
							offen={offen === id}
							abweichend={grenzenAbweichend(id)}
							{vorlageLabel}
							fehler={offen === id ? fehler : []}
							onEntfernen={() => entfernen(id)}
							onAlarmAb={(s) => aendern(Z.mitAlarmAb(stand!, id, s))}
							onGrenzen={() => grenzenUmschalten(id)}
							onWert={(seite, farbe, w) => grenzWert(id, seite, farbe, w)}
							onGewitter={gewitterWahl}
						/>
					{/each}
				</div>
			{/each}
			<NichtImBriefing metriken={nichtIm} hinzugefuegt={hinzu} onHinzufuegen={hinzufuegen} />
		</div>
		<WarnungenRadarKarte
			warnungenAn={stand.warnungenAn}
			radarAn={stand.radarAn}
			mitRadar={MIT_RADAR[context]}
			onWarnungen={(an) => aendern({ ...stand!, warnungenAn: an })}
			onRadar={(an) => aendern({ ...stand!, radarAn: an })}
		/>
		<AnpassenKarte
			tagesfenster={stand.tagesfenster}
			onStart={(h) => aendern({ ...stand!, tagesfenster: { ...stand!.tagesfenster, start: h } })}
			onEnde={(h) => aendern({ ...stand!, tagesfenster: { ...stand!.tagesfenster, end: h } })}
		/>
	{/if}
</section>

<style>
	.wt {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-4);
		box-sizing: border-box;
		max-width: var(--g-size-1100px);
		padding: var(--g-size-28px) var(--g-s-10) var(--g-size-60px);
		color: var(--g-ink);
	}
	.wt-kopf h2 {
		margin: 0 0 var(--g-s-1);
		font-size: var(--g-size-22px);
		font-weight: 600;
		color: var(--g-ink);
	}
	.wt-kopf p {
		margin: 0;
		font-size: var(--g-size-14px);
		color: var(--g-ink-2);
	}
	.wt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wt-metriken {
		overflow: hidden;
	}
	.wt-laden {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		padding: var(--g-s-5);
		color: var(--g-ink-2);
	}
	.wt-fehler {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--g-size-10px);
		padding: var(--g-s-4) var(--g-s-5);
		border-color: var(--g-danger);
	}
	.wt-fehler p {
		margin: 0;
		font-size: var(--g-size-14px);
		color: var(--g-ink);
	}
	.wt-fehler :global([data-slot='btn']) {
		font-size: var(--g-size-14px);
	}
	.wt-gh {
		padding: var(--g-size-14px) var(--g-s-5) var(--g-s-1);
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		letter-spacing: var(--g-size-0-1em);
		text-transform: uppercase;
		color: var(--g-ink-3);
		border-top: 1px solid var(--g-rule-soft);
	}
	@media (max-width: 899px) {
		.wt {
			padding: var(--g-s-4) var(--g-s-4) var(--g-s-10);
		}
		.wt-gh {
			padding: var(--g-size-14px) var(--g-s-4) var(--g-s-1);
		}
	}
</style>
