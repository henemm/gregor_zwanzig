<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: eine Metrik-Zeile des Reiters Wetter (AC-15 bis AC-18).
	// Ampel-Leiste mit Grenzzahlen, Erklaersatz, „grün: …", „Alarm ab" bzw. „kein Alarm",
	// „Grenzen ändern". Keine Aggregationswahl, kein Roh/Einfach (S3b). Trip und Orts-Briefing gleich.
	import type { Ampel, AmpelMetrik } from '$lib/types';
	import { Segmented } from '$lib/components/atoms';
	import { t } from '$lib/i18n';
	import AmpelLeiste from './AmpelLeiste.svelte';
	import GrenzenEditor from './GrenzenEditor.svelte';
	import { alarmAbOptionen, erklaersatz, gruenZeile, type AlarmAb, type Farbe, type KatalogModell, type MetrikEigenschaften } from './ampelModell.ts';

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
		optionen.map((s) => ({ value: s, label: $t(`alarme.alarm_ab.stufe.${s}` as 'alarme.alarm_ab.stufe.never'), testid: `wetter-alarm-ab-${id}-${s}` }))
	);
	const stufe = $derived(eintrag?.alarm_ab ?? 'never');
</script>

<div class="wt-zeile" data-testid="wetter-zeile-{id}">
	<button type="button" class="wt-rm" data-testid="wetter-zeile-entfernen-{id}" aria-label={$t('wetter.zeile.entfernen', { metrik: name })} title={$t('wetter.zeile.entfernen', { metrik: name })} onclick={onEntfernen}>−</button>
	<div class="wt-name">
		<b>{name}</b>
		{#if eig.unit}<small>{eig.unit}</small>{/if}
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
				<span aria-hidden="true">·</span> <span class="wt-gruen" data-testid="wetter-gruen-{id}">{gruen}</span>
			{/if}
		</p>
	</div>
	<div class="wt-act">
		{#if optionen.length > 0}
			<span class="wt-lbl">{$t('alarme.alarm_ab.titel')}</span>
			<div class="wt-seg">
				<Segmented rolle="radio" testid="wetter-alarm-ab-{id}" ariaLabel={$t('wetter.alarm_ab.wert', { stufe: $t(`alarme.alarm_ab.stufe.${stufe}` as 'alarme.alarm_ab.stufe.never') })} options={segmente} value={stufe} onChange={(s: string) => onAlarmAb(s as AlarmAb)} />
			</div>
		{:else}
			<span class="wt-lbl" data-testid="wetter-alarm-ab-{id}">{$t(eig.is_precursor ? 'wetter.alarm_ab.vorbote' : 'wetter.alarm_ab.kein_alarm')}</span>
		{/if}
		{#if !eig.display_only}
			<button type="button" class="wt-btn" data-testid="wetter-grenzen-aendern-{id}" aria-expanded={offen} onclick={onGrenzen}>
				{$t(offen ? 'wetter.grenzen.fertig' : 'wetter.grenzen.aendern')}
			</button>
		{/if}
	</div>
	{#if offen}
		<GrenzenEditor {id} erlaubt={eig.allowed_sides} {eintrag} gewitter={istGewitter ? (thunder ?? {}) : null} {abweichend} {vorlageLabel} {fehler} {onWert} {onGewitter} />
	{/if}
</div>

<style>
	.wt-zeile {
		display: grid;
		grid-template-columns: 44px minmax(120px, 180px) minmax(0, 1fr) auto;
		gap: 8px 14px;
		align-items: center;
		padding: 12px 20px;
		border-top: 1px solid var(--g-rule-soft);
	}
	.wt-rm,
	.wt-btn {
		min-height: 44px;
		min-width: 44px;
		box-sizing: border-box;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
		font-size: 13px;
		cursor: pointer;
	}
	.wt-btn {
		padding: 0 12px;
	}
	.wt-rm {
		font-size: 18px;
		line-height: 1;
	}
	.wt-name {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.wt-name b {
		font-size: 14px;
		color: var(--g-ink);
	}
	.wt-name small,
	.wt-lbl,
	.wt-nur {
		font-size: 12.5px;
		color: var(--g-ink-2);
	}
	.wt-mitte {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}
	.wt-why {
		margin: 0;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--g-ink-2);
	}
	.wt-gruen {
		color: var(--g-ink-3);
	}
	.wt-act {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 8px;
	}
	.wt-seg :global([data-slot='segmented-item']) {
		min-height: 44px;
		min-width: 44px;
		color: var(--g-ink-2);
	}
	.wt-seg :global([data-slot='segmented-item'][data-active='true']) {
		color: var(--g-paper);
	}
	@media (max-width: 899px) {
		.wt-zeile {
			grid-template-columns: 44px minmax(0, 1fr);
			padding: 12px 16px;
		}
		.wt-mitte,
		.wt-act {
			grid-column: 1 / -1;
		}
		.wt-act {
			justify-content: flex-start;
		}
	}
</style>
