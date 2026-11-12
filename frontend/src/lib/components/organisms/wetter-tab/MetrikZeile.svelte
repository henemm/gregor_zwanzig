<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: eine Metrik-Zeile des Reiters Wetter (AC-15 bis AC-18).
	// Ampel-Leiste mit Grenzzahlen, Erklaersatz, „grün: …", „Alarm ab" bzw. „kein Alarm",
	// „Grenzen ändern". Keine Aggregationswahl, kein Roh/Einfach (S3b). Trip und Orts-Briefing gleich.
	import type { Ampel, AmpelMetrik } from '$lib/types';
	// #2913 Teil 2 (K-6): Knöpfe als Btn (Größe tap), „Alarm ab“-Stufen mit Farbpunkt.
	import { Btn, Segmented } from '$lib/components/atoms';
	import { t } from '$lib/i18n';
	import AmpelLeiste from './AmpelLeiste.svelte';
	import GrenzenEditor from './GrenzenEditor.svelte';
	import { alarmAbOptionen, erklaersatz, gruenZeile, untertitel, type AlarmAb, type Farbe, type KatalogModell, type MetrikEigenschaften } from '../../shared/wetter-tab/ampelModell.ts';

	interface Props {
		id: string;
		name: string;
		eig: MetrikEigenschaften;
		eintrag: AmpelMetrik | undefined;
		thunder: Ampel['thunder'];
		offen: boolean;
		abweichend: boolean;
		vorlageLabel: string;
		fehler: string[];
		onEntfernen: () => void;
		onAlarmAb: (stufe: AlarmAb) => void;
		onGrenzen: () => void;
		onWert: (seite: 'lower' | 'upper', farbe: Farbe, wert: number | null) => void;
		onGewitter: (stufe: 'mittel' | 'hoch', farbe: Farbe) => void;
	}
	let { id, name, eig, eintrag, thunder, offen, abweichend, vorlageLabel, fehler, onEntfernen, onAlarmAb, onGrenzen, onWert, onGewitter }: Props = $props();

	const istGewitter = $derived(eig.allowed_sides === 'level');
	const optionen = $derived(alarmAbOptionen(id, eig));

	/** Katalogtext; Roh-Token (Farbe, Gewitter-Stufe) als Katalogwort einsetzen. */
	// i18n-dynamic: wetter.farbe.
	function text(m: KatalogModell): string {
		const w: Record<string, string | number> = { ...m.werte };
		if (typeof w.stufe === 'string') w.stufe = $t(`wetter.farbe.${w.stufe}` as 'wetter.farbe.red');
		if (typeof w.gewitter_stufe === 'string') w.gewitter_stufe = $t(`wetter.gewitter.${w.gewitter_stufe}` as 'wetter.gewitter.mittel');
		return $t(m.schluessel as 'wetter.gruen.immer', w).replace(/\s+/g, ' ').trim();
	}
	const erklaer = $derived(text(erklaersatz(id, eintrag ?? {}, eig, thunder)));
	const gruen = $derived(text(gruenZeile(eintrag ?? {}, eig)));
	// i18n-dynamic: alarme.alarm_ab.stufe.
	const segmente = $derived(
		optionen.map((s) => ({
			value: s,
			label: $t(`alarme.alarm_ab.stufe.${s}` as 'alarme.alarm_ab.stufe.never'),
			testid: `wetter-alarm-ab-${id}-${s}`,
			farbe: s === 'never' ? undefined : s
		}))
	);
	const stufe = $derived(eintrag?.alarm_ab ?? 'never');
	// #2913 Fix Metrik-Liste (AC-5): Untertitel `Einheit · Hinweis` (Mockup Z. ~434), Hinweis aus dem Katalog.
	// i18n-dynamic: wetter.hinweis.
	const unter = $derived(untertitel(id, eig, (k) => $t(k as 'wetter.untertitel.vorbote')));
</script>

<div class="wt-zeile" data-testid="wetter-zeile-{id}">
	<div class="wt-rm">
		<Btn variant="ghost" size="tap" data-tap="true" data-testid="wetter-zeile-entfernen-{id}" aria-label={$t('wetter.zeile.entfernen', { metrik: name })} title={$t('wetter.zeile.entfernen', { metrik: name })} onclick={onEntfernen}>−</Btn>
	</div>
	<div class="wt-name">
		<b>{name}</b>
		{#if unter}<small>{unter}</small>{/if}
	</div>
	<div class="wt-mitte">
		{#if eig.display_only}
			<span class="wt-nur">{$t('wetter.zeile.nur_anzeige')}</span>
		{:else}
			<AmpelLeiste {id} {eintrag} gewitter={istGewitter ? thunder : null} />
		{/if}
		<p class="wt-why">
			<span data-testid="wetter-erklaersatz-{id}">{erklaer}</span>
			{#if !istGewitter && !eig.display_only}
				<span class="wt-gruen" data-testid="wetter-gruen-{id}"><span aria-hidden="true">·</span> {gruen}</span>
			{/if}
		</p>
	</div>
	<div class="wt-act">
		{#if optionen.length > 0}
			<span class="wt-lbl">{$t('alarme.alarm_ab.titel')}</span>
			<div class="wt-seg">
				<Segmented variant="kompakt" rolle="radio" testid="wetter-alarm-ab-{id}" ariaLabel={$t('wetter.alarm_ab.wert', { stufe: $t(`alarme.alarm_ab.stufe.${stufe}` as 'alarme.alarm_ab.stufe.never') })} options={segmente} value={stufe} onChange={(s: string) => onAlarmAb(s as AlarmAb)} />
			</div>
		{:else}
			<span class="wt-lbl" data-testid="wetter-alarm-ab-{id}">{$t(eig.is_precursor ? 'wetter.alarm_ab.vorbote' : 'wetter.alarm_ab.kein_alarm')}</span>
		{/if}
		{#if !eig.display_only}
			<Btn variant="ghost" size="tap" data-tap="true" data-testid="wetter-grenzen-aendern-{id}" aria-expanded={offen} onclick={onGrenzen}>
				{$t(offen ? 'wetter.grenzen.fertig' : 'wetter.grenzen.aendern')}
			</Btn>
		{/if}
	</div>
	{#if offen}
		<GrenzenEditor {id} erlaubt={eig.allowed_sides} {eintrag} gewitter={istGewitter ? (thunder ?? {}) : null} {abweichend} {vorlageLabel} {fehler} {onWert} {onGewitter} />
	{/if}
</div>

<style>
	/* #2913 Fix Metrik-Liste: Raster nach Mockup Fassung 3 `.mr` (Z. ~97). Die Mittelspalte hat eine
	   harte Untergrenze (160 px) und fällt nicht mehr auf 0; der Umbruch hängt an der Kartenbreite
	   (Container `.wt-metriken` in WetterTabInhalt), nicht am Viewport. */
	.wt-zeile {
		display: grid;
		grid-template-columns: var(--g-s-8) minmax(var(--g-size-130px), var(--g-size-190px)) minmax(var(--g-size-160px), 1fr) auto;
		gap: var(--g-s-2) var(--g-size-18px);
		align-items: center;
		padding: var(--g-s-3) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.wt-zeile :global([data-slot='btn']) {
		background: var(--g-card);
		font-weight: 400;
	}
	.wt-zeile :global([data-slot='btn']:hover) {
		background: var(--g-surface-2);
	}
	/* Kompakte Knöpfe (Mockup `.btn.sm` / `.rm`, 28 px sichtbar); Trefferfläche 44 px über data-tap (app.css). */
	.wt-zeile :global([data-slot='btn'][data-tap='true']) {
		height: var(--g-size-28px);
		min-height: var(--g-size-28px);
		font-size: var(--g-s-3);
	}
	.wt-rm :global([data-slot='btn']) {
		width: var(--g-size-28px);
		padding: 0;
		font-size: var(--g-size-18px);
		line-height: 1;
	}
	.wt-name {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.wt-name b {
		font-size: var(--g-size-14px);
		color: var(--g-ink);
	}
	.wt-name small,
	.wt-lbl {
		font-size: var(--g-s-3);
		color: var(--g-ink-3);
	}
	.wt-nur {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.wt-mitte {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
		min-width: 0;
	}
	/* AC-4: Zeilenhöhe 1,4 statt Mockup 1,5. Mit Seitenleiste ist die Karte bei 1280 nur 1012 px breit
	   (Mockup ohne Seitenleiste 1068), die Mittelspalte daher ca. 280 statt 337 px und die Erklärung
	   „Temperatur“ 4 statt 3 Zeilen; mit 1,4 bleibt die Zeile in der Toleranz (≤ 124 px). */
	.wt-why {
		margin: 0;
		font-size: var(--g-s-3);
		line-height: 1.4;
		color: var(--g-ink-2);
	}
	/* Mockup `.why .gr`: „grün: …“ grün, Gewicht 600, Trennpunkt in der Span. Text-Token --g-ok-fg statt
	   --g-ampel-gruen (Grafik-Token, nur ≥ 3:1; dunkel 3,37:1): Text braucht 4,5:1 in Hell UND Dunkel (AC-13). */
	.wt-gruen {
		color: var(--g-ok-fg);
		font-weight: 600;
	}
	.wt-act {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		/* AC-8: Bricht die Aktionsspalte um (1024/1100, Handy), liegen Segmente und „Grenzen ändern“
		   untereinander. Ihre unsichtbaren 44-px-Trefferflächen (::before) dürfen sich nicht überdecken:
		   Segment 29 + Knopf 28 sichtbar ⇒ Zeilenabstand ≥ 16 px. */
		gap: var(--g-s-4) var(--g-size-10px);
	}
	/* #2913 Runde 2 (Befund 2): Mit Seitenleiste ist die Karte bei 1024/1100 px nur 756/832 px breit. Das Raster
	   braucht für eine einzeilige Aktionsspalte (≈ 420 px DE, ≈ 450 px EN) mindestens ≈ 834 px Karte; darunter fiel
	   die Mitte auf 160 px und die Aktionen brachen dreizeilig um (im Mockup bei gleicher Kartenbreite ebenso).
	   Bis 960 px Karte stehen die Aktionen daher einzeilig UNTER der Mitte (Spalte 3 bis Ende); das Raster selbst
	   (AC-1) bleibt, ab 961 px (1280 px Viewport: 1012) gilt das Mockup-Bild mit Aktionen rechts. */
	@container (max-width: 960px) {
		.wt-mitte,
		.wt-act {
			grid-column: 3 / -1;
		}
		.wt-act {
			flex-wrap: nowrap;
			justify-content: flex-start;
		}
	}
	@container (max-width: 700px) {
		.wt-zeile {
			grid-template-columns: var(--g-s-10) 1fr;
			padding: var(--g-s-3) var(--g-s-4);
		}
		.wt-mitte,
		.wt-act {
			grid-column: 1 / -1;
		}
		.wt-act {
			flex-wrap: wrap;
			justify-content: flex-start;
		}
	}
</style>
