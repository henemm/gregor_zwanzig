<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: Vorlage-Karte des Reiters Wetter (AC-10 bis AC-13, AC-28, AC-42).
	// Picker mit den Systemvorlagen (Metrikzahl + Stichworte aus /api/templates) und „Eigene"
	// (nur Vorlagen der Art des Kontexts), Rueckfrage vor dem Wechsel (W4), „Auf ‚…‘ zurücksetzen"
	// nur bei Abweichungen, Dialog „Als eigene Vorlage speichern". Trip und Orts-Briefing gleich.
	import type { Ampel, MetricPreset } from '$lib/types';
	// #2913 Teil 2 (K-6): alle Knöpfe aus dem Atom Btn (Größe tap, Touch-Ziel >= 44px).
	import { Btn } from '$lib/components/atoms';
	import { locale, t, tn, type MessageKey } from '$lib/i18n';
	import SavePresetDialog from '../../shared/weather-metrics-tab/SavePresetDialog.svelte';
	import { pickerSchliesstPerTaste, speicherKarteAusloeser } from '$lib/utils/vorlageSpeichernKarte.js';
	import type { Kontext } from '../../shared/wetter-tab/ampelModell.ts';
	import { vorlageKurzbeschreibung, type EigeneVorlage, type VorlageEintrag } from '../../shared/wetter-tab/wetterTabLaden.ts';
	// #2981: Systemvorlagen-Namen sprachabhaengig aus dem Katalog (Fallback Server-Label, dann ID).
	import { vorlageAnzeigename } from '../../shared/wetter-tab/vorlageName.ts';

	interface Props {
		context: Kontext;
		vorlageId: string;
		liste: VorlageEintrag[];
		eigene: EigeneVorlage[];
		abweichungen: number;
		/** Anzeigename einer Metrik (Stichworte der Kurzbeschreibung). */
		metrikName: (id: string) => string;
		/** Aufgeloeste Abo-Ampel fuer den Dialog. */
		aboAmpel: Ampel;
		onUebernehmen: (id: string) => void;
		onEigene: (id: string) => void;
		onZuruecksetzen: () => void;
		onGespeichert: (preset: MetricPreset) => void;
		/** #3111 AC-6: Zahl der Orte (nur Orte), waehlt „für diesen Ort“ bzw. „für diese Orte“. */
		ortAnzahl?: number;
		/** #3189: Herkunft fuer „Als eigene Vorlage speichern“ (Trip bzw. Orts-Vergleich; fehlt im Anlege-Modus). */
		herkunft?: { id: string; name: string };
	}
	let { context, vorlageId, liste, eigene, abweichungen, metrikName, aboAmpel, onUebernehmen, onEigene, onZuruecksetzen, onGespeichert, ortAnzahl, herkunft }: Props = $props();

	// #3111 AC-6 (Mockup Fassung 4): Bestätigung zweiteilig, fetter Titel plus EIN Rumpf-Text.
	const ERSETZT: Record<Kontext, () => MessageKey> = {
		route: () => 'wetter.vorlage.ersetzt_route',
		vergleich: () => (ortAnzahl === 1 ? 'wetter.vorlage.ersetzt_vergleich_ein' : 'wetter.vorlage.ersetzt_vergleich')
	};

	let pickerOffen = $state(false);
	let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(null);
	let dialogOffen = $state(false);
	let gespeichert = $state<string | null>(null);
	// #3190: Speichern-Karte als Umschalter (aria-expanded/aria-controls); Fokus kehrt nach dem Schließen
	// auf den Auslöser zurück (gemerkt beim Klick, das Btn-Atom reicht keine Referenz durch). Logik geteilt
	// mit dem Alt-Editor (WeatherMetricsTab): $lib/utils/vorlageSpeichernKarte.ts.
	const kartenId = $props.id();
	const ausloeser = speicherKarteAusloeser();

	const label = $derived(vorlageAnzeigename($locale, vorlageId, liste.find((v) => v.id === vorlageId)?.label));
	/** Anzeigename einer Systemvorlage; reaktiv auf den Sprachwechsel ueber `$locale`. */
	function name(v: VorlageEintrag): string {
		return vorlageAnzeigename($locale, v.id, v.label);
	}
	const status = $derived(abweichungen > 0 ? $tn('wetter.vorlage.abweichungen', abweichungen) : $t('wetter.vorlage.unveraendert'));

	function beschreibung(v: VorlageEintrag): string {
		return vorlageKurzbeschreibung(v, $t, metrikName);
	}
	/** #3111 AC-3: „Name · aktiv“ als ein Text (kein Kind-Element). */
	function optionName(v: VorlageEintrag): string {
		return v.id === vorlageId ? `${name(v)} ${$t('wetter.vorlage.aktiv_marker')}` : name(v);
	}
	/** #3111 AC-5 / #3189 AC-4: Unterzeile „eigene“ + Beschreibung, sonst + Herkunft, sonst nur „eigene“. */
	function eigeneUnterzeile(e: EigeneVorlage): string {
		const zusatz = e.beschreibung
			? [e.beschreibung]
			: e.herkunftName
				? [$t('wetter.vorlage.eigene_aus_herkunft', { name: e.herkunftName })]
				: [];
		return [$t('wetter.vorlage.eigene_unterzeile'), ...zusatz].join(' · ');
	}
	/** #3111 AC-6: Rumpf der Bestätigung als ein Text: Ersetzt-Satz, ggf. Verlust-Satz, Bleibt-Satz. */
	const rumpf = $derived(
		[$t(ERSETZT[context]()), abweichungen > 0 ? $tn('wetter.vorlage.verlust', abweichungen, { alt: label }) : '', $t('wetter.vorlage.bleibt')]
			.filter(Boolean)
			.join(' ')
	);
	function waehlen(id: string, name: string, eigen: boolean): void {
		wahl = { id, name, eigen };
	}
	function schliessen(): void {
		pickerOffen = false;
		wahl = null;
	}
	function uebernehmen(): void {
		if (wahl) (wahl.eigen ? onEigene : onUebernehmen)(wahl.id);
		schliessen();
	}
	// #3190: Escape in der Speichern-Karte endet dort (SavePresetDialog); hier nur noch der Picker.
	function taste(e: KeyboardEvent): void {
		if (pickerSchliesstPerTaste(e.key, pickerOffen)) schliessen();
	}
	function umschalten(e: MouseEvent): void {
		gespeichert = null;
		dialogOffen = ausloeser.umschalten(e.currentTarget as HTMLElement, dialogOffen);
	}
	function dialogZu(): void {
		dialogOffen = false;
		ausloeser.zurueck();
	}
	function gespeichertMelden(p: MetricPreset): void {
		gespeichert = p.name;
		onGespeichert(p);
		ausloeser.zurueck();
	}
</script>

<svelte:window onkeydown={taste} />

<div class="wt-karte" data-abschnitt="vorlage">
	<div class="wt-picker-wrap">
		<span class="wt-eyebrow">{$t('wetter.vorlage.titel')}</span>
		<div class="wt-picker">
			<Btn variant="ghost" size="tap" data-testid="wetter-vorlage-picker" aria-expanded={pickerOffen} aria-haspopup="listbox" onclick={() => (pickerOffen ? schliessen() : (pickerOffen = true))}>
				<span>{label}</span>
				<small>▾ <span data-testid="wetter-vorlage-status">{status}</span></small>
			</Btn>
		</div>
		{#if pickerOffen}
			<div class="wt-menue" data-abschnitt="vorlage-auswahl">
				{#if wahl}
					<div class="wt-frage" role="alertdialog" data-testid="wetter-vorlage-wechsel-dialog" data-abschnitt="vorlage-bestaetigung">
						<b>{$t('wetter.vorlage.frage_titel', { neu: wahl.eigen ? wahl.name : vorlageAnzeigename($locale, wahl.id, wahl.name) })}</b>
						<span class="wt-frage-rumpf">{rumpf}</span>
						<div class="wt-reihe">
							<Btn variant="accent" size="tap" data-testid="wetter-vorlage-wechsel-uebernehmen" onclick={uebernehmen}>{$t('wetter.vorlage.uebernehmen')}</Btn>
							<Btn variant="ghost" size="tap" data-testid="wetter-vorlage-wechsel-abbrechen" onclick={schliessen}>{$t('aktionen.abbrechen')}</Btn>
						</div>
					</div>
				{/if}
				<div class="wt-gruppe">{$t('wetter.vorlage.systemvorlagen')}</div>
				{#each liste as v (v.id)}
					<div class="wt-option">
						<Btn variant="quiet" size="tap" data-aktiv={v.id === vorlageId ? 'true' : undefined} data-testid="wetter-vorlage-option-{v.id}" onclick={() => waehlen(v.id, v.label, false)}>
							<span>{optionName(v)}</span>
							<small data-testid="wetter-vorlage-beschreibung-{v.id}">{beschreibung(v)}</small>
						</Btn>
					</div>
				{/each}
				<div data-testid="wetter-vorlage-eigene">
					<div class="wt-gruppe">{$t('wetter.vorlage.eigene')}</div>
					{#each eigene as e (e.id)}
						<div class="wt-option">
							<Btn variant="quiet" size="tap" data-testid="wetter-vorlage-eigene-{e.id}" onclick={() => waehlen(e.id, e.name, true)}>
								<span>{e.name}</span>
								<small>{eigeneUnterzeile(e)}</small>
							</Btn>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
	<div class="wt-reihe wt-aktionen">
		<Btn variant="ghost" size="tap" data-testid="wetter-vorlage-als-eigene" aria-expanded={dialogOffen} aria-controls={kartenId} onclick={umschalten}>{$t('wetter.vorlage.speichern')}</Btn>
		{#if abweichungen > 0}
			<Btn variant="ghost" size="tap" data-testid="wetter-vorlage-zuruecksetzen" onclick={onZuruecksetzen}>{$t('wetter.vorlage.zuruecksetzen', { vorlage: label })}</Btn>
		{/if}
	</div>
	{#if gespeichert}
		<p class="wt-meldung" role="status" data-testid="wetter-vorlage-gespeichert">{$t('wetter.dialog.gespeichert', { name: gespeichert })}</p>
	{/if}
</div>

<!-- #3190: Inline-Karte direkt unter der Vorlage-Karte (vor der Metrik-Karte in WetterTabInhalt). -->
<SavePresetDialog id={kartenId} bind:open={dialogOffen} kind={context} ampel={aboAmpel} existingNames={eigene.map((e) => e.name)} {herkunft} onClose={dialogZu} onSaved={gespeichertMelden} />

<style>
	.wt-karte {
		display: flex;
		flex-wrap: wrap;
		/* #2980 AC-27 (Mockup .vorlage): Aktion „Als eigene Vorlage speichern" vertikal mittig. */
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-3) var(--g-s-4);
		padding: var(--g-s-4) var(--g-s-5);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wt-picker-wrap {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: var(--g-size-6px);
	}
	.wt-eyebrow {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		color: var(--g-ink-3);
	}
	.wt-picker {
		align-self: flex-start;
	}
	/* #2980 AC-26 (Mockup .picker): Rahmen --g-rule (Btn ghost), Grund --g-paper, Name 15 px/600. */
	/* #3003 AC-32 (Mockup .picker: padding 8px 12px, align-items center): Inhalt mittig,
	   seitlich 12 px. Höhe nach Bedienart, nicht nach Breite: bei Maus keine 44-px-Mindesthöhe
	   (Mockup ca. 38 px aus Polster + Zeilenhöhe), Finger-Regel unten unter pointer: coarse. */
	.wt-picker :global([data-slot='btn']) {
		align-items: center;
		padding: var(--g-s-2) var(--g-s-3);
		min-height: 0;
		gap: var(--g-size-10px);
		background: var(--g-paper);
		font-size: var(--g-text-md);
		font-weight: 600;
	}
	/* #3003 AC-32 / K-5 (#2284): Fingerbedienung behält die 44-px-Tippfläche. */
	@media (pointer: coarse) {
		.wt-picker :global([data-slot='btn']) {
			min-height: var(--g-tap-min);
		}
	}
	.wt-picker :global([data-slot='btn']:hover) {
		background: var(--g-surface-2);
	}
	/* #2980 AC-26 (Mockup .picker small): „▾ unverändert" Mono 11 px in --g-ink-3. */
	.wt-picker small {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		font-weight: 500;
		color: var(--g-ink-3);
	}
	.wt-menue {
		position: absolute;
		top: 100%;
		left: 0;
		z-index: 30;
		margin-top: var(--g-s-1);
		width: min(var(--g-size-420px), calc(100vw - var(--g-s-12)));
		max-height: 70vh;
		overflow-y: auto;
		padding: var(--g-size-6px);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-radius-md);
		background: var(--g-card);
		box-shadow: var(--g-shadow-3);
	}
	.wt-gruppe {
		padding: var(--g-s-2) var(--g-size-10px) var(--g-s-1);
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		letter-spacing: var(--g-size-0-08em);
		text-transform: uppercase;
		color: var(--g-ink-3);
	}
	.wt-option :global([data-slot='btn']) {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		justify-content: center;
		gap: var(--g-size-2px);
		width: 100%;
		padding: var(--g-size-6px) var(--g-size-10px);
		border: none;
		color: var(--g-ink);
		font-size: var(--g-size-14px);
		font-weight: 400;
		text-align: left;
		white-space: normal;
	}
	.wt-option :global([data-slot='btn'][data-aktiv='true']),
	.wt-option :global([data-slot='btn']:hover) {
		background: var(--g-paper-deep);
	}
	.wt-option small {
		font-size: var(--g-text-12px);
		color: var(--g-ink-2);
	}
	.wt-frage {
		margin: var(--g-s-1) var(--g-s-1) var(--g-s-2);
		padding: var(--g-size-10px) var(--g-s-3);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card-alt);
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	/* Titel ohne eigene Klasse (Mockup .confirm b); :global, damit kein Scope-Attribut am <b> landet. */
	.wt-frage :global(b),
	.wt-frage-rumpf {
		display: block;
		margin: 0 0 var(--g-s-2);
	}
	.wt-reihe {
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-2);
	}
	.wt-aktionen :global([data-slot='btn']),
	.wt-frage :global([data-slot='btn'][data-variant='ghost']) {
		background: var(--g-card);
		font-weight: 400;
	}
	.wt-aktionen :global([data-slot='btn']:hover),
	.wt-frage :global([data-slot='btn'][data-variant='ghost']:hover) {
		background: var(--g-surface-2);
	}
	.wt-meldung {
		flex-basis: 100%;
		margin: 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
	@media (max-width: 899px) {
		.wt-karte {
			padding: var(--g-size-14px) var(--g-s-4);
		}
	}
</style>
