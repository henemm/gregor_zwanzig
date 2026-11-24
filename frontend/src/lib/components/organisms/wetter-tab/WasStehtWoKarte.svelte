<script lang="ts">
	// Issue #3122 B3b — Karte „Was steht wo“ im Reiter Wetter, zwischen „Amtliche Warnungen / Radar“ und
	// „Anpassen“ (Spec docs/specs/modules/feat_3122_was_steht_wo.md Teil B Nr. 10 bis 13, ADR-0124).
	// EIN Code für Trip und Orte (`context="route"|"vergleich"`); alle Kontext-Unterschiede kommen als Daten aus
	// der Antwort (Spalten, Unterzeilen, Blöcke, Zahl der Orte) bzw. aus Tabellen unten. Nur aus Bausteinen:
	// EinstellTabelle (Haken, RohEinfachKnopf, Ziehen über SortableList), Einstellungszeile, Switch, Segmented,
	// Aufklapper, Btn, Skelett.
	//   Lesen: GET /api/briefings/{id}/placements?kind=…; Speichern der Tabelle: wasStehtWoSpeicherung.ts
	//   (vollständiger Stand, If-Match, Reihenfolge der Vorgänge, Konflikt). Schalter unter der Tabelle speichern
	//   an ihrem heutigen Ort; der 3-Tages-Ausblick schreibt `outlook_reports` mit der Tabelle.
	//   „−“/„+“ der Grundauswahl ruft der Reiter über die exportierten Funktionen; ohne gespeicherte Tabelle
	//   (`stored: false`) ändern sie nichts an der Tabelle (sonst wechselte das Abo unbemerkt den Eingang).
	//   #3305 Anlege-Modus (`createMode`): Laden über die Vorschau des Entwurfs, kein PUT; jede Bedienung meldet
	//   den Stand per `onAnlegeStand` (auch bei `stored: false`), der Anlege-POST trägt ihn. Eine Vorschau-Antwort
	//   ersetzt nur die Ansicht, nie den lokalen Stand.
	import { onMount, untrack } from 'svelte';
	import { Btn, Skelett, Switch, Segmented } from '$lib/components/atoms';
	import { Aufklapper, EinstellTabelle, Einstellungszeile } from '$lib/components/molecules';
	import { api } from '$lib/api';
	import { t, tn } from '$lib/i18n';
	import type { MessageKey } from '$lib/i18n';
	import type { Trip } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { klon } from '../../shared/wetter-tab/klon.ts';
	import * as S from '../../shared/wetter-tab/wasStehtWoStand.ts';
	import type { Placements, PlacementsAntwort, Form } from '../../shared/wetter-tab/wasStehtWoStand.ts';
	import { festeZeileAus, legendeAus, metrikenAus, smsAus, stellenAus } from '../../shared/wetter-tab/wasStehtWoAnsicht.ts';
	import { erstelleFelderSpeicherung, erstelleTabellenSpeicherung, felderAusAntwort, type Felder, type KarteAnlegeStand } from '../../shared/wetter-tab/wasStehtWoSpeicherung.ts';

	type Kontext = 'route' | 'vergleich';
	interface Props {
		context: Kontext;
		id: string;
		saveController?: SaveStatus;
		enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
		/** Antwort eines Schalter-PUT an die Seite (Trip bzw. Orte). */
		onUebernahme?: (abo: unknown) => void;
		/** #3305: Anlegen — kein PUT, Stand geht über `onAnlegeStand` an die Anlege-Seite. */
		createMode?: boolean;
		/** #3305: Anlege-Entwurf für die Vorschau (gelesen erst beim Senden). */
		entwurf?: () => Trip;
		/** #3305: zuletzt gemeldeter Stand (Neuaufbau der Ansicht, Wechsel Desktop/Mobil). */
		start?: KarteAnlegeStand;
		onAnlegeStand?: (s: KarteAnlegeStand) => void;
	}
	let { context, id, saveController, enqueueHubWrite, onUebernahme, createMode = false, entwurf, start, onAnlegeStand }: Props = $props();

	/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). */
	const KONTEXT: Record<Kontext, { text: MessageKey; ausblick: MessageKey; stundenverlauf: boolean; tripBloecke: boolean }> = {
		route: { text: 'wetter.wsw.text_route', ausblick: 'wetter.wsw.bloecke.ausblick_hinweis_route', stundenverlauf: false, tripBloecke: true },
		vergleich: { text: 'wetter.wsw.text_vergleich', ausblick: 'wetter.wsw.bloecke.ausblick_hinweis_vergleich', stundenverlauf: true, tripBloecke: false }
	};
	const k = $derived(KONTEXT[context]);
	const TRIP_BLOECKE: { feld: 'show_stage_stats' | 'show_yesterday_comparison' | 'show_night_block' | 'show_compact_summary' | 'show_stability'; titel: MessageKey; hinweis: MessageKey }[] = [
		{ feld: 'show_stage_stats', titel: 'wetter.wsw.bloecke.etappen', hinweis: 'wetter.wsw.bloecke.etappen_hinweis' },
		{ feld: 'show_yesterday_comparison', titel: 'wetter.wsw.bloecke.vortag', hinweis: 'wetter.wsw.bloecke.vortag_hinweis' },
		{ feld: 'show_night_block', titel: 'wetter.wsw.bloecke.nacht', hinweis: 'wetter.wsw.bloecke.nacht_hinweis' },
		// #3036: Kurz-Zusammenfassung und Großwetterlage (report_config, nur ausführliche E-Mail)
		{ feld: 'show_compact_summary', titel: 'wetter.wsw.bloecke.kurz', hinweis: 'wetter.wsw.bloecke.kurz_hinweis' },
		{ feld: 'show_stability', titel: 'wetter.wsw.bloecke.grosswetterlage', hinweis: 'wetter.wsw.bloecke.grosswetterlage_hinweis' }
	];
	const BERICHTE: { id: 'morning' | 'evening'; titel: MessageKey; name: MessageKey }[] = [
		{ id: 'morning', titel: 'wetter.wsw.bloecke.morgen', name: 'wetter.wsw.bloecke.ausblick_morgen' },
		{ id: 'evening', titel: 'wetter.wsw.bloecke.abend', name: 'wetter.wsw.bloecke.ausblick_abend' }
	];
	const MELDUNG: Record<'konflikt' | 'fehler', MessageKey> = { konflikt: 'wetter.wsw.konflikt', fehler: 'wetter.wsw.speicherfehler' };

	let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');
	let antwort = $state<PlacementsAntwort | null>(null);
	/** Lokaler Stand der Tabelle (Grundlage jedes PUT; gelesen erst beim Senden). */
	let lokal = $state<Placements | null>(untrack(() => (start ? klon(start.placements) : null)));
	let felder = $state<Felder | null>(untrack(() => (start ? { ...start.felder } : null)));
	/** #3305: Schalter beim Start der Karte (erste Vorschau-Antwort bzw. `start`). */
	let felderStart: Felder | null = untrack(() => (start ? { ...start.felderStart } : null));
	/** #3305: erst nach einer Bedienung meldet die Karte (unbedient = POST wie heute, ohne Tabelle). */
	let bedient = untrack(() => Boolean(start));
	let meldung = $state<'konflikt' | 'fehler' | null>(null);
	let telegramVerbunden = $state(false);

	function uebernehmen(a: PlacementsAntwort): void {
		antwort = a;
		// #3305: im Anlegen ersetzt die Vorschau nur die Ansicht; der lokale Stand bleibt.
		if (!createMode || !lokal) lokal = klon(a.placements);
		if (createMode) felderStart ??= felderAusAntwort(a);
		phase = 'bereit';
	}
	/** #3305: Stand an die Anlege-Seite (Haken, Formate, Reihenfolge, Ausblick, Schalter). */
	function melde(): void {
		const f = felder ?? aktFelder;
		if (!createMode || !lokal || !f) return;
		bedient = true;
		onAnlegeStand?.({ placements: klon(lokal), felder: { ...f }, felderStart: { ...(felderStart ?? f) } });
	}
	const tabelle = untrack(() =>
		erstelleTabellenSpeicherung({
			client: api,
			kind: context,
			id,
			saveController,
			placements: () => (lokal ? klon(lokal) : null),
			entwurf: createMode ? () => (entwurf?.() ?? {}) as Record<string, unknown> : undefined,
			uebernehmen,
			// #3305: ohne Antwort sichtbarer Fehler wie beim ersten Laden; sonst bleibt die alte Ansicht.
			vorschauFehler: () => {
				if (!antwort) phase = 'fehler';
			},
			gemeldet: (art) => (meldung = art)
		})
	);
	let schalter: ReturnType<typeof erstelleFelderSpeicherung> | null = null;

	async function laden(): Promise<void> {
		phase = 'laedt';
		try {
			await tabelle.laden();
		} catch {
			phase = 'fehler';
		}
	}
	onMount(() => {
		void laden();
		fetch('/api/auth/profile', { credentials: 'same-origin' })
			.then((r) => (r.ok ? r.json() : null))
			.then((p: { telegram_chat_id?: string } | null) => (telegramVerbunden = Boolean(p?.telegram_chat_id)))
			.catch(() => {});
	});

	// ── Änderungen in der Tabelle ─────────────────────────────────────────────
	const anzeige = () => antwort?.rows.map((r) => r.metric_id) ?? [];
	function aendern(neuLokal: Placements, neuAntwort: PlacementsAntwort): void {
		lokal = neuLokal;
		antwort = neuAntwort;
		meldung = null;
		tabelle.aenderung();
		melde();
	}
	function haken(e: { metrik: string; stelle: string; an: boolean }): void {
		if (antwort && lokal) aendern(S.mitHaken(lokal, anzeige(), e.metrik, e.stelle, e.an), S.antwortMitHaken(antwort, e.metrik, e.stelle, e.an));
	}
	function format(e: { metrik: string; stelle: string; format: Form }): void {
		if (antwort && lokal) aendern(S.mitFormat(lokal, anzeige(), e.metrik, e.stelle, e.format), S.antwortMitFormat(antwort, e.metrik, e.stelle, e.format));
	}
	function reihenfolge(ids: string[]): void {
		if (antwort && lokal) aendern(S.mitReihenfolge(lokal, ids), S.antwortMitReihenfolge(antwort, ids));
	}
	function ausblick(bericht: 'morning' | 'evening', an: boolean): void {
		if (!antwort || !lokal) return;
		const jetzt = new Set(ausblickBerichte);
		if (an) jetzt.add(bericht);
		else jetzt.delete(bericht);
		const neu = S.mitAusblick(lokal, { morning: jetzt.has('morning'), evening: jetzt.has('evening') });
		aendern(neu, { ...antwort, outlook_reports: neu.outlook_reports ?? [] });
	}

	// ── Schalter an ihrem heutigen Ort ────────────────────────────────────────
	function feld<K extends keyof Felder>(name: K, wert: Felder[K]): void {
		if (!aktFelder) return;
		felder = { ...aktFelder, [name]: wert };
		if (createMode) return melde();
		schalter ??= erstelleFelderSpeicherung({
			client: api,
			kind: context,
			id,
			saveController,
			enqueueHubWrite,
			start: felderAusAntwort(antwort!),
			onAntwort: (abo) => {
				onUebernahme?.(abo);
				tabelle.nachFremdemSpeichern();
			},
			// Fix-Loop F1: wie bei den Haken — Anzeige zurück auf den gespeicherten Stand, Meldung; bei 412 neu laden.
			onFehler: (e, gespeichert) => {
				felder = gespeichert;
				const konflikt = (e as { status?: number })?.status === 412;
				meldung = konflikt ? 'konflikt' : 'fehler';
				if (konflikt) void tabelle.laden().catch(() => {});
			}
		});
		schalter.melden(felder);
	}

	// ── Schnittstelle für den Reiter (Grundauswahl „−“/„+“, Speichern des Reiters) ──
	/** „−“, „+“ oder Vorlagenwechsel (Fix-Loop F2): Zeilen weggefallener Metriken entfallen, neue stehen hinten,
	 *  überall angehakt — im selben Speichervorgang wie die Grundauswahl. Nur bei gespeicherter Tabelle. */
	export function grundauswahlGeaendert(vorher: readonly string[], nachher: readonly string[]): void {
		if (!createMode && (!antwort?.stored || !lokal)) return;
		const weg = vorher.filter((m) => !nachher.includes(m));
		if (!weg.length && nachher.every((m) => vorher.includes(m))) return;
		// #3237 Runde 13: kein eigener Tabellen-PUT — der PUT des Reiters trägt den Stand (placementsZumMitspeichern).
		// #3305 F007: im Anlegen auch vor der ersten Vorschau-Antwort — die Version zählt hoch, eine ältere
		// Antwort mit den alten Metriken verfällt; ein Startstand folgt der Auswahl sofort.
		if (lokal) lokal = S.mitGrundauswahl(lokal, vorher, nachher);
		if (antwort) antwort = weg.reduce((a, m) => S.antwortOhneZeile(a, m), antwort);
		meldung = null;
		tabelle.mitgefuehrt();
		if (bedient) melde();
	}
	/** #3305: Metrikwechsel im Anlegen — Vorschau entprellt nachladen (Zeilen neuer Metriken, Beispielwerte). */
	export function vorschauNachMetrik(): void {
		tabelle.vorschauNachMetrik();
	}
	/** Für den PUT des Reiters: der vollständige Stand, nur wenn die Tabelle schon gespeichert ist (Anlegen: immer). */
	export function placementsZumMitspeichern(): Placements | undefined {
		return tabelle.zumMitsenden(createMode || Boolean(antwort?.stored));
	}
	/** Der Reiter hat gespeichert (`gesendet` = placements dieses PUT): Beispielwerte, Marken, feste Zeile neu holen. */
	export function nachFremdemSpeichern(gesendet: unknown): void {
		tabelle.nachReiterSpeichern(gesendet);
	}

	// ── Anzeige ───────────────────────────────────────────────────────────────
	const ausblickBerichte = $derived(lokal?.outlook_reports ?? antwort?.outlook_reports ?? []);
	const aktFelder = $derived(felder ?? (antwort ? felderAusAntwort(antwort) : null));
	const lage = $derived({
		kurzstil: aktFelder?.telegram_style === 'kurzform',
		stundenverlaufAn: aktFelder?.hourly_enabled !== false,
		ausblickAn: ausblickBerichte.length > 0
	});
	const stellen = $derived(antwort ? stellenAus(antwort, lage, $t) : []);
	const metriken = $derived(antwort ? metrikenAus(antwort, $t) : []);
	const festeZeile = $derived(antwort ? festeZeileAus(antwort, $t) : undefined);
	const sms = $derived(antwort ? smsAus(antwort, $t, $tn) : null);
	const legende = $derived(antwort ? legendeAus(antwort, $t) : []);
	const einOrt = $derived(antwort?.location_count === 1);
	/** #3154: Etappen-Kennzahlen, Vortag-Vergleich, Nacht-Stundentabelle wirken in der Kompakt-Mail nicht. */
	const nurAusfuehrlich = $derived(aktFelder?.email_format === 'compact');
	const kurzstilGesperrt = $derived(!telegramVerbunden && aktFelder?.telegram_style !== 'kurzform');
</script>

<section class="wsw" data-abschnitt="was-steht-wo" data-testid="was-steht-wo" data-context={context}>
	<Einstellungszeile titel={$t('wetter.wsw.titel')} hinweis={$t(k.text)} />
	{#if phase === 'laedt'}
		<div class="wsw-laden" data-testid="was-steht-wo-laden" aria-busy="true">
			<span role="status">{$t('wetter.wsw.laden')}</span>
			<div aria-hidden="true"><Skelett label={$t('wetter.wsw.laden')} /></div>
		</div>
	{:else if phase === 'fehler' || !antwort || !aktFelder}
		<div class="wsw-fehler" role="alert" data-testid="was-steht-wo-fehler">
			<p>{$t('wetter.wsw.fehler')}</p>
			<Btn variant="accent" size="tap" data-testid="was-steht-wo-erneut-laden" onclick={() => void laden()}>{$t('wetter.kopf.erneut_laden')}</Btn>
		</div>
	{:else}
		{#if meldung}
			<p class="wsw-meldung" role="alert" data-testid="was-steht-wo-meldung" data-art={meldung}>{$t(MELDUNG[meldung])}</p>
		{/if}
		{#if metriken.length === 0}
			<p class="wsw-leer" data-testid="was-steht-wo-leer">{$t('wetter.wsw.leer')}</p>
		{:else}
			<EinstellTabelle testid="was-steht-wo-tabelle" metrikTitel={$t('wetter.wsw.metrik')} {stellen} {metriken} {festeZeile} onHaken={haken} onFormat={format} onReihenfolge={reihenfolge} />
			{#if sms}
				<p class="wsw-sms" data-testid="was-steht-wo-sms">
					{$t('wetter.wsw.sms.beispiel')} <b data-testid="was-steht-wo-sms-text">{sms.text}</b> · <span data-testid="was-steht-wo-sms-zeichen">{sms.zeichen}</span>
					{#if sms.hinweis}<span class="wsw-sms-hinweis" data-testid="was-steht-wo-sms-hinweis">{sms.hinweis}</span>{/if}
				</p>
			{/if}
			<Aufklapper titel={$t('wetter.wsw.legende.titel')} testid="was-steht-wo-legende" summaryTestid="was-steht-wo-legende-auf">
				<dl class="wsw-legende">
					{#each legende as e, i (i)}
						<div class="wsw-legende-eintrag" data-legende={e.token}><dt>{e.token}</dt>{#if e.text}<dd>{e.text}</dd>{/if}</div>
					{/each}
				</dl>
			</Aufklapper>
		{/if}

		<div class="wsw-sub">{$t('wetter.wsw.bloecke.titel')}</div>
		{#if k.stundenverlauf}
			<Einstellungszeile titel={$t('wetter.wsw.bloecke.stundenverlauf')} hinweis={$t(einOrt ? 'wetter.wsw.bloecke.stundenverlauf_hinweis_ein_ort' : 'wetter.wsw.bloecke.stundenverlauf_hinweis')}>
				<Switch checked={aktFelder.hourly_enabled} tap testid="was-steht-wo-stundenverlauf" aria-label={$t('wetter.wsw.bloecke.stundenverlauf')} onchange={(an) => feld('hourly_enabled', an)} />
			</Einstellungszeile>
		{/if}
		<Einstellungszeile titel={$t('wetter.wsw.bloecke.ausblick')} hinweis={$t(k.ausblick)}>
			{#each BERICHTE as b (b.id)}
				<span class="wsw-wahl">
					<Switch checked={ausblickBerichte.includes(b.id)} tap testid="was-steht-wo-ausblick-{b.id}" aria-label={$t(b.name)} onchange={(an) => ausblick(b.id, an)} />
					<span aria-hidden="true">{$t(b.titel)}</span>
				</span>
			{/each}
		</Einstellungszeile>
		{#if k.tripBloecke}
			<!-- #3154: die drei Blöcke wirken nur in der ausführlichen E-Mail (Kompakt-Renderer liest sie nicht) —
			     bei „Kompakt“ gesperrt mit Grund, gespeicherter Wert bleibt stehen. -->
			{#each TRIP_BLOECKE as b (b.feld)}
				<Einstellungszeile titel={$t(b.titel)} hinweis={nurAusfuehrlich ? `${$t(b.hinweis)}. ${$t('wetter.wsw.bloecke.nur_ausfuehrlich')}` : $t(b.hinweis)}>
					<Switch checked={aktFelder[b.feld]} disabled={nurAusfuehrlich} tap testid="was-steht-wo-{b.feld}" aria-label={$t(b.titel)} onchange={(an) => feld(b.feld, an)} />
				</Einstellungszeile>
			{/each}
		{/if}

		<div class="wsw-sub">{$t('wetter.wsw.kanal.titel')}</div>
		{#if k.tripBloecke}
			<Einstellungszeile titel={$t('wetter.wsw.kanal.email_format')} hinweis={$t('wetter.wsw.kanal.email_format_hinweis')}>
				<Segmented
					variant="kompakt"
					rolle="radio"
					testid="was-steht-wo-email-format"
					ariaLabel={$t('wetter.wsw.kanal.email_format')}
					items={[
						{ id: 'full', label: $t('wetter.wsw.kanal.ausfuehrlich'), testid: 'was-steht-wo-email-format-full' },
						{ id: 'compact', label: $t('wetter.wsw.kanal.kompakt'), testid: 'was-steht-wo-email-format-compact' }
					]}
					value={aktFelder.email_format}
					onChange={(v: string) => feld('email_format', v === 'compact' ? 'compact' : 'full')}
				/>
			</Einstellungszeile>
		{/if}
		<Einstellungszeile titel={$t('wetter.wsw.kanal.kurzstil')} hinweis={$t('wetter.wsw.kanal.kurzstil_hinweis')}>
			<Switch
				checked={aktFelder.telegram_style === 'kurzform'}
				disabled={kurzstilGesperrt}
				tap
				testid="was-steht-wo-kurzstil"
				aria-label={$t('wetter.wsw.kanal.kurzstil_name')}
				onchange={(an) => feld('telegram_style', an ? 'kurzform' : 'rich')}
			/>
		</Einstellungszeile>
		<Einstellungszeile titel={$t('wetter.wsw.kanal.premium')} hinweis={$t('wetter.wsw.kanal.premium_hinweis')} />
	{/if}
</section>

<style>
	.wsw {
		min-width: 0;
		overflow: hidden;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wsw-laden {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		padding: var(--g-s-4) var(--g-s-5);
		color: var(--g-ink-2);
	}
	.wsw-fehler {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--g-size-10px);
		padding: var(--g-s-4) var(--g-s-5);
		border-top: 1px solid var(--g-danger);
	}
	.wsw-fehler p,
	.wsw-meldung,
	.wsw-leer {
		margin: 0;
		font-size: var(--g-size-13px);
		color: var(--g-ink);
	}
	.wsw-meldung {
		padding: var(--g-s-3) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
		color: var(--g-bad);
	}
	.wsw-leer {
		padding: var(--g-s-4) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
		color: var(--g-ink-2);
	}
	/* Mockup `.budget`: SMS-Beispiel unter der Tabelle. */
	.wsw-sms {
		margin: 0;
		padding: var(--g-size-10px) var(--g-s-5);
		border-top: 1px dashed var(--g-rule);
		color: var(--g-ink-2);
		font-family: var(--g-font-mono);
		font-size: var(--g-size-11-5px);
		overflow-wrap: anywhere;
	}
	.wsw-sms b {
		color: var(--g-ink);
		font-weight: 500;
	}
	.wsw-sms-hinweis {
		display: block;
		margin-top: var(--g-size-3px);
		color: var(--g-bad);
		font-family: var(--g-font-ui);
		font-size: var(--g-size-12-5px);
	}
	/* #3283 B7 (Mockup Fassung 4): Kürzel und Erklärung in zwei Spalten, die Hülle je Eintrag ist
	   für das Raster unsichtbar (display: contents), damit dt und dd direkt im Grid liegen. */
	.wsw-legende {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--g-s-1) var(--g-size-14px);
		margin: 0;
		padding: 0 var(--g-s-5) var(--g-s-4);
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.wsw-legende-eintrag {
		display: contents;
	}
	/* Feste Spalten: ein Eintrag ohne Erklärung verschiebt die folgenden Kürzel nicht. */
	.wsw-legende dt {
		grid-column: 1;
		color: var(--g-ink);
		font-family: var(--g-font-mono);
		font-weight: 400;
	}
	.wsw-legende dd {
		grid-column: 2;
		margin: 0;
	}
	/* Mockup `.sub`: Zwischentitel unter der Tabelle. */
	.wsw-sub {
		padding: var(--g-size-14px) var(--g-s-5) var(--g-s-1);
		border-top: 1px solid var(--g-rule-soft);
		color: var(--g-ink-2);
		font-family: var(--g-font-mono);
		font-size: var(--g-size-10-5px);
		letter-spacing: var(--g-size-0-1em);
		text-transform: uppercase;
	}
	.wsw-wahl {
		display: inline-flex;
		align-items: center;
		gap: var(--g-s-2);
		font-size: var(--g-size-13px);
		color: var(--g-ink);
	}
	@media (max-width: 899px) {
		.wsw-sms,
		.wsw-sub,
		.wsw-meldung,
		.wsw-leer,
		.wsw-legende {
			padding-inline: var(--g-s-3);
		}
	}
</style>
