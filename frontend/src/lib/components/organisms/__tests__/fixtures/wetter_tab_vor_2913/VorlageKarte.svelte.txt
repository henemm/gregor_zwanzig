<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: Vorlage-Karte des Reiters Wetter (AC-10 bis AC-13, AC-28, AC-42).
	// Picker mit den Systemvorlagen (Metrikzahl + Stichworte aus /api/templates) und „Eigene"
	// (nur Vorlagen der Art des Kontexts), Rueckfrage vor dem Wechsel (W4), „Auf ‚…‘ zurücksetzen"
	// nur bei Abweichungen, Dialog „Als eigene Vorlage speichern". Trip und Orts-Briefing gleich.
	import type { Ampel, MetricPreset } from '$lib/types';
	import { t, tn } from '$lib/i18n';
	import SavePresetDialog from '../weather-metrics-tab/SavePresetDialog.svelte';
	import type { Kontext } from './ampelModell.ts';
	import type { EigeneVorlage, VorlageEintrag } from './wetterTabLaden.ts';

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
	}
	let { context, vorlageId, liste, eigene, abweichungen, metrikName, aboAmpel, onUebernehmen, onEigene, onZuruecksetzen, onGespeichert }: Props = $props();

	const FRAGE = { route: 'wetter.vorlage.frage_route', vergleich: 'wetter.vorlage.frage_vergleich' } as const;

	let pickerOffen = $state(false);
	let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(null);
	let dialogOffen = $state(false);
	let gespeichert = $state<string | null>(null);

	const label = $derived(liste.find((v) => v.id === vorlageId)?.label ?? vorlageId);
	const status = $derived(abweichungen > 0 ? $tn('wetter.vorlage.abweichungen', abweichungen) : $t('wetter.vorlage.unveraendert'));

	function beschreibung(v: VorlageEintrag): string {
		return [$t('wetter.vorlage.metrikzahl', { count: v.anzahl }), ...v.stichworte.map(metrikName)].join(' · ');
	}
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
	function taste(e: KeyboardEvent): void {
		if (pickerOffen && !dialogOffen && e.key === 'Escape') schliessen();
	}
	function gespeichertMelden(p: MetricPreset): void {
		gespeichert = p.name;
		onGespeichert(p);
	}
</script>

<svelte:window onkeydown={taste} />

<div class="wt-karte">
	<div class="wt-picker-wrap">
		<span class="wt-eyebrow">{$t('wetter.vorlage.titel')}</span>
		<button type="button" class="wt-picker" data-testid="wetter-vorlage-picker" aria-expanded={pickerOffen} aria-haspopup="listbox" onclick={() => (pickerOffen ? schliessen() : (pickerOffen = true))}>
			<span>{label}</span>
			<small>▾ <span data-testid="wetter-vorlage-status">{status}</span></small>
		</button>
		{#if pickerOffen}
			<div class="wt-menue">
				{#if wahl}
					<div class="wt-frage" role="alertdialog" data-testid="wetter-vorlage-wechsel-dialog">
						<p>
							{$t(FRAGE[context], { neu: wahl.name })}
							{#if abweichungen > 0}{$tn('wetter.vorlage.verlust', abweichungen, { alt: label })}{/if}
							{$t('wetter.vorlage.bleibt')}
						</p>
						<div class="wt-reihe">
							<button type="button" class="wt-btn wt-btn--primaer" data-testid="wetter-vorlage-wechsel-uebernehmen" onclick={uebernehmen}>{$t('wetter.vorlage.uebernehmen')}</button>
							<button type="button" class="wt-btn" data-testid="wetter-vorlage-wechsel-abbrechen" onclick={schliessen}>{$t('aktionen.abbrechen')}</button>
						</div>
					</div>
				{/if}
				<div class="wt-gruppe">{$t('wetter.vorlage.systemvorlagen')}</div>
				{#each liste as v (v.id)}
					<button type="button" class="wt-option" class:aktiv={v.id === vorlageId} data-testid="wetter-vorlage-option-{v.id}" onclick={() => waehlen(v.id, v.label, false)}>
						<span>{v.label}</span>
						<small data-testid="wetter-vorlage-beschreibung-{v.id}">{beschreibung(v)}</small>
					</button>
				{/each}
				<div data-testid="wetter-vorlage-eigene">
					<div class="wt-gruppe">{$t('wetter.vorlage.eigene')}</div>
					{#each eigene as e (e.id)}
						<button type="button" class="wt-option" data-testid="wetter-vorlage-eigene-{e.id}" onclick={() => waehlen(e.id, e.name, true)}>
							<span>{e.name}</span>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</div>
	<div class="wt-reihe">
		<button type="button" class="wt-btn" data-testid="wetter-vorlage-als-eigene" onclick={() => ((gespeichert = null), (dialogOffen = true))}>{$t('wetter.vorlage.speichern')}</button>
		{#if abweichungen > 0}
			<button type="button" class="wt-btn" data-testid="wetter-vorlage-zuruecksetzen" onclick={onZuruecksetzen}>{$t('wetter.vorlage.zuruecksetzen', { vorlage: label })}</button>
		{/if}
	</div>
	{#if gespeichert}
		<p class="wt-meldung" role="status" data-testid="wetter-vorlage-gespeichert">{$t('wetter.dialog.gespeichert', { name: gespeichert })}</p>
	{/if}
</div>

<SavePresetDialog bind:open={dialogOffen} kind={context} ampel={aboAmpel} existingNames={eigene.map((e) => e.name)} onClose={() => (dialogOffen = false)} onSaved={gespeichertMelden} />

<style>
	.wt-karte {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		justify-content: space-between;
		gap: 12px 16px;
		padding: 16px 20px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wt-picker-wrap {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.wt-eyebrow {
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--g-ink-3);
	}
	.wt-picker {
		display: inline-flex;
		align-items: baseline;
		gap: 10px;
		min-height: 44px;
		padding: 0 14px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
		font-size: 16px;
		font-weight: 600;
		cursor: pointer;
		align-self: flex-start;
	}
	.wt-picker small {
		font-size: 12.5px;
		font-weight: 400;
		color: var(--g-ink-2);
	}
	.wt-menue {
		position: absolute;
		top: 100%;
		left: 0;
		z-index: 30;
		margin-top: 4px;
		width: min(420px, calc(100vw - 48px));
		max-height: 70vh;
		overflow-y: auto;
		padding: 6px;
		border: 1px solid var(--g-rule);
		border-radius: 8px;
		background: var(--g-card);
		box-shadow: var(--g-shadow-3);
	}
	.wt-gruppe {
		padding: 8px 10px 4px;
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--g-ink-3);
	}
	.wt-option {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		width: 100%;
		min-height: 44px;
		padding: 6px 10px;
		border: none;
		border-radius: var(--g-r-2);
		background: transparent;
		color: var(--g-ink);
		font: inherit;
		font-size: 14px;
		text-align: left;
		cursor: pointer;
	}
	.wt-option.aktiv,
	.wt-option:hover {
		background: var(--g-paper-deep);
	}
	.wt-option small {
		font-size: 12px;
		color: var(--g-ink-2);
	}
	.wt-frage {
		margin: 4px 4px 8px;
		padding: 10px 12px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card-alt);
		font-size: 13px;
		color: var(--g-ink);
	}
	.wt-frage p {
		margin: 0 0 8px;
	}
	.wt-reihe {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.wt-btn {
		min-height: 44px;
		min-width: 44px;
		padding: 0 14px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
		font-size: 13px;
		cursor: pointer;
	}
	.wt-btn--primaer {
		background: var(--g-accent-deep);
		border-color: var(--g-accent-deep);
		color: var(--g-on-accent);
	}
	.wt-meldung {
		flex-basis: 100%;
		margin: 0;
		font-size: 13px;
		color: var(--g-ink-2);
	}
	@media (max-width: 899px) {
		.wt-karte {
			padding: 14px 16px;
		}
	}
</style>
