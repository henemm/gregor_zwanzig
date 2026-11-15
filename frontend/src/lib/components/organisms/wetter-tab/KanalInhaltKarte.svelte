<script lang="ts">
	// Issue #3031 (Inhalt je Kanal A1): Karte „Inhalt je Kanal und Fläche“ im Reiter Wetter
	// (Mockup Fassung 3). Trip und Orts-Briefing derselbe Code; die Karte kennt nur
	// `KanalZeile[]` je Kanal (kanalInhalt.ts), Laden/Speichern macht der Reiter.
	// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md, AC-1 bis AC-6, AC-9, AC-12.
	//
	// Segment E-Mail · Telegram · SMS · Premium-SMS; je Zeile Griff (SortableList + DragHandle,
	// ADR-0024), Name „Spaltenname (Spaltenkopf | Kürzel)“, Roh/Einfach mit Beispiel (nur bei Wahl
	// laut Katalog), Schalter. „Amtliche Warnungen“ ist eine feste Anzeigezeile ausserhalb der
	// Sortierzone. Premium-SMS zeigt die SMS-Liste schreibgeschuetzt (ADR-0049, bis S9).
	import { untrack } from 'svelte';
	import { Segmented, Switch } from '$lib/components/atoms';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import { t, locale, type MessageKey } from '$lib/i18n';
	import {
		KANAELE,
		hatFormatWahl,
		istSchreibgeschuetzt,
		mitFormat,
		mitReihenfolge,
		mitSchalter,
		warnungsPosition,
		zeilenFuerKanal,
		zeilenName,
		type Format,
		type Kanal,
		type KanalListen,
		type KanalZeile,
		type KatalogEintrag,
		type Kontext,
		type ListenKanal
	} from './kanalInhalt.ts';
	import { beispiel } from './kanalInhaltBeispiele.ts';

	interface Props {
		context: Kontext;
		listen: KanalListen;
		metriken: Record<string, KatalogEintrag>;
		/** Anfangs gewaehltes Segment. */
		kanal?: Kanal;
		onAendern: (listen: KanalListen) => void;
	}
	let { context, listen, metriken, kanal, onAendern }: Props = $props();

	const KANAL_NAME: Record<Kanal, MessageKey> = {
		email: 'zustellung.kanal.email',
		telegram: 'zustellung.kanal.telegram',
		sms: 'zustellung.kanal.sms',
		premium_sms: 'zustellung.kanal.premium_sms'
	};

	let gewaehlt = $state<Kanal>(untrack(() => kanal) ?? 'email');

	const zeilen = $derived(zeilenFuerKanal(listen, gewaehlt));
	const gesperrt = $derived(istSchreibgeschuetzt(gewaehlt));
	const warnungOben = $derived(warnungsPosition(gewaehlt) === 'oben');
	const kanalName = $derived($t(KANAL_NAME[gewaehlt]));
	const sprache = $derived($locale === 'en' ? 'en' : 'de');
	const nachId = $derived(new Map(zeilen.map((z) => [z.id, z])));

	function eintrag(id: string): KatalogEintrag {
		return metriken[id] ?? { label: id };
	}
	/** Nur bedienbare Segmente schreiben; Premium-SMS ist gesperrt (kein ListenKanal). */
	function listenKanal(): ListenKanal | null {
		return gesperrt ? null : (gewaehlt as ListenKanal);
	}
	function umsortieren(ids: string[]): void {
		const k = listenKanal();
		if (k) onAendern(mitReihenfolge(listen, k, ids));
	}
	function schalten(id: string, an: boolean): void {
		const k = listenKanal();
		if (k) onAendern(mitSchalter(listen, k, id, an));
	}
	function formatSetzen(id: string, f: string): void {
		const k = listenKanal();
		if (k && (f === 'roh' || f === 'einfach')) onAendern(mitFormat(listen, k, id, f as Format));
	}
	const formatItems = $derived([
		{ id: 'roh', label: $t('wetter.kanal_inhalt.roh') },
		{ id: 'einfach', label: $t('wetter.kanal_inhalt.einfach') }
	]);
	const segmentItems = $derived(KANAELE.map((k) => ({ id: k, label: $t(KANAL_NAME[k]), testid: `kanal-inhalt-segment-${k}` })));
</script>

{#snippet warnungen()}
	<div class="ki-zeile ki-fest" data-testid="kanal-inhalt-warnungen">
		<span class="ki-griff" aria-hidden="true"></span>
		<span class="ki-name">
			{$t('wetter.kanal_inhalt.warnungen')}
			<span class="ki-leise">· {warnungOben ? $t('wetter.kanal_inhalt.warnungen_oben') : $t('wetter.kanal_inhalt.warnungen_unten')}</span>
		</span>
	</div>
{/snippet}

{#snippet zeile(z: KanalZeile)}
	{@const e = eintrag(z.id)}
	{@const name = zeilenName(e)}
	{@const ex = hatFormatWahl(e) ? beispiel(z.id, z.format, sprache) : null}
	<div class="ki-zeile" class:ki-aus={!z.enabled} data-testid="kanal-inhalt-zeile-{z.id}" data-enabled={z.enabled ? 'true' : 'false'}>
		<DragHandle disabled={gesperrt} label={$t('wetter.kanal_inhalt.griff_aria', { name: e.label })} />
		<span class="ki-name">{name}</span>
		{#if hatFormatWahl(e)}
			{#if gesperrt}
				<span class="ki-format-fest" data-testid="kanal-inhalt-format-{z.id}">{z.format === 'einfach' ? $t('wetter.kanal_inhalt.einfach') : $t('wetter.kanal_inhalt.roh')}</span>
			{:else}
				<Segmented size="sm" rolle="radio" ariaLabel={$t('wetter.kanal_inhalt.kopf_darstellung')} testid="kanal-inhalt-format-{z.id}" value={z.format} items={formatItems} onChange={(f: string) => formatSetzen(z.id, f)} />
			{/if}
		{/if}
		{#if ex}<span class="ki-beispiel" data-testid="kanal-inhalt-beispiel-{z.id}">{ex}</span>{/if}
		<span class="ki-schalter">
			<Switch
				checked={z.enabled}
				disabled={gesperrt}
				tap
				testid="kanal-inhalt-schalter-{z.id}"
				aria-label={$t('wetter.kanal_inhalt.schalter_aria', { name: e.label, kanal: kanalName })}
				onchange={(an: boolean) => schalten(z.id, an)}
			/>
		</span>
	</div>
{/snippet}

<div class="ki" data-testid="kanal-inhalt-karte" data-abschnitt="kanal-inhalt" data-context={context}>
	<div class="ki-kopf">
		<div class="ki-text">
			<b>{$t('wetter.kanal_inhalt.titel')}</b>
			<small>{$t('wetter.kanal_inhalt.untertitel')}</small>
		</div>
		<Segmented rolle="radio" ariaLabel={$t('wetter.kanal_inhalt.segment_aria')} value={gewaehlt} items={segmentItems} onChange={(k: string) => (gewaehlt = k as Kanal)} />
	</div>
	{#if gesperrt}
		<p class="ki-hinweis" data-testid="kanal-inhalt-premium-hinweis">{$t('wetter.kanal_inhalt.premium_folgt_sms')}</p>
	{/if}
	<div class="ki-liste" data-testid="kanal-inhalt-liste" data-kanal={gewaehlt}>
		<div class="ki-zeile ki-spaltenkopf" aria-hidden="true">
			<span class="ki-griff"></span>
			<span class="ki-name">{$t('wetter.kanal_inhalt.kopf_metrik')} <span class="ki-leise">{$t('wetter.kanal_inhalt.kopf_metrik_hinweis')}</span></span>
			<span class="ki-kopfzelle">{$t('wetter.kanal_inhalt.kopf_darstellung')}<br /><span class="ki-leise">{$t('wetter.kanal_inhalt.kopf_darstellung_hinweis')}</span></span>
			<span class="ki-kopfzelle">{$t('wetter.kanal_inhalt.kopf_kanal', { kanal: kanalName })}<br /><span class="ki-leise">{$t('wetter.kanal_inhalt.kopf_kanal_hinweis')}</span></span>
		</div>
		{#if warnungOben}{@render warnungen()}{/if}
		{#if gesperrt}
			{#each zeilen as z (z.id)}{@render zeile(z)}{/each}
		{:else}
			<SortableList
				items={zeilen.map((z) => z.id)}
				onDndReorder={umsortieren}
				ariaLabel={$t('wetter.kanal_inhalt.liste_aria', { kanal: kanalName })}
				itemLabel={(id: string) => zeilenName(eintrag(id))}
			>
				{#snippet row(id: string)}
					{@const z = nachId.get(id)}
					{#if z}{@render zeile(z)}{/if}
				{/snippet}
			</SortableList>
		{/if}
		{#if !warnungOben}{@render warnungen()}{/if}
	</div>
</div>

<style>
	.ki {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.ki-kopf {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-size-10px) var(--g-s-4);
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.ki-text {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
		flex: 1 1 var(--g-size-420px);
		min-width: 0;
	}
	.ki-text small {
		font-size: var(--g-text-sm);
		color: var(--g-ink-3);
	}
	.ki-hinweis {
		margin: 0;
		padding: var(--g-size-10px) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
		background: var(--g-card-alt);
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
	.ki-liste {
		display: flex;
		flex-direction: column;
	}
	.ki-zeile {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-2) var(--g-s-3);
		padding: var(--g-s-2) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.ki-griff {
		display: inline-block;
		width: var(--g-size-18px);
	}
	.ki-name {
		flex: 1 1 var(--g-size-180px);
		min-width: 0;
	}
	.ki-aus .ki-name {
		color: var(--g-ink-3);
		text-decoration: line-through;
	}
	.ki-leise {
		color: var(--g-ink-3);
		font-size: var(--g-text-xs);
	}
	.ki-spaltenkopf {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-2);
	}
	.ki-kopfzelle {
		min-width: var(--g-size-120px);
	}
	.ki-fest {
		background: var(--g-card-alt);
	}
	.ki-fest .ki-name {
		color: var(--g-ink-2);
	}
	.ki-beispiel,
	.ki-format-fest {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-3);
	}
	.ki-schalter {
		display: inline-flex;
		margin-left: auto;
	}
</style>
