<script lang="ts">
	// Issue #1895 S3b1 — Kanäle je Wettergröße (Spec alert_metric_channels.md AC-41..AC-53).
	// EIN Baustein für alle vier Flächen (über AlarmeTab); Änderungen nur über onChange,
	// der Speicherweg liegt beim Halter des Zustands.
	import { onMount, untrack } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { t, locale } from '$lib/i18n';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import { alertMetricLabel } from '$lib/utils/alertMetricLabels';
	import type { PremiumSmsAlarmGate } from '../shared/alarme-tab/premiumSmsAlarmGate.ts';
	import {
		KANAELE,
		KANAL_NAMEN,
		hinweise,
		kanalZeilen,
		ladeKanalSchluessel,
		normalisiereEintrag,
		type Kanal,
		type KanalEintrag,
		type KanalSchluessel
	} from '../shared/alarme-tab/alertMetricChannels.ts';

	interface Props {
		aktiveMetriken: string[];
		eintraege: Record<string, KanalEintrag> | null | undefined;
		aboKanaele: Partial<Record<Kanal, boolean>>;
		premiumSmsGate: PremiumSmsAlarmGate;
		/** Testhaken (Muster profileOverride): Objekt = Antwort, null = Abruf gescheitert. */
		schluesselOverride?: KanalSchluessel | null;
		onChange: (schluessel: string, eintrag: KanalEintrag) => void;
	}
	let { aktiveMetriken, eintraege, aboKanaele, premiumSmsGate, schluesselOverride, onChange }: Props = $props();

	// undefined = lädt, null = nicht verfügbar (F3: nichts raten, nichts schreiben).
	let antwort = $state<KanalSchluessel | null | undefined>(untrack(() => schluesselOverride));
	onMount(() => {
		if (schluesselOverride === undefined) void ladeKanalSchluessel().then((a) => (antwort = a));
	});
	const zeilen = $derived(antwort ? kanalZeilen(aktiveMetriken, antwort.keys, antwort.accepted) : []);
	/** Alarm-Zeilen, deren Kanalwahl dieser Schlüssel trägt (Zeilentitel). */
	const metrikenVon = (k: string) => aktiveMetriken.filter((m) => antwort?.keys[m]?.includes(k));

	// „Eigene Wahl" ohne gewählten Kanal (leerer Abo-Satz, AC-51) bleibt nur hier offen;
	// gespeichert bleibt null, bis ein Kanal an ist (E5).
	let offen = $state<string[]>([]);
	export function schalterSichtbar(k: string): boolean {
		return !!eintraege?.[k] || offen.includes(k);
	}
	export function kanalSetzen(k: string, kanal: Kanal, an: boolean): void {
		const e = normalisiereEintrag({ ...(eintraege?.[k] ?? {}), [kanal]: an });
		if (!e) offen = offen.filter((o) => o !== k);
		onChange(k, e);
	}
	export function eigeneWahl(k: string, an: boolean): void {
		const e = an ? normalisiereEintrag(aboKanaele) : null;
		offen = an && !e ? [...offen, k] : offen.filter((o) => o !== k);
		if (e || !an) onChange(k, e);
	}
</script>

{#if zeilen.length > 0 || antwort === null}
<div class="amc" data-testid="kanal-block">
	<Eyebrow style="margin-bottom: 10px;">{$t('alarme.kanaele.ueberschrift')}</Eyebrow>
	<p class="amc-hinweis" data-testid="kanal-hinweis-metrikfrei">{$t('alarme.kanaele.metrikfrei_hinweis')}</p>
	{#if antwort === null}
		<p class="amc-hinweis" data-testid="kanal-nicht-verfuegbar">{$t('alarme.kanaele.nicht_verfuegbar')}</p>
	{/if}
	{#each zeilen as k (k)}
		{@const eintrag = eintraege?.[k] ?? null}
		{@const aus = hinweise(eintrag, aboKanaele)}
		<div class="amc-zeile" data-testid="kanal-zeile-{k}">
			<div class="amc-titel">{metrikenVon(k).map((m) => alertMetricLabel(m, $locale)).join(' / ')}</div>
			<ChannelToggle
				label={$t('alarme.kanaele.eigene_wahl')}
				checked={schalterSichtbar(k)}
				onchange={(an) => eigeneWahl(k, an)}
				testid="kanal-eigene-{k}"
			/>
			{#if !schalterSichtbar(k)}
				<p class="amc-hinweis" data-testid="kanal-erbt-{k}">{$t('alarme.kanaele.wie_abo')}</p>
			{:else}
				<div class="amc-schalter">
					{#each KANAELE as kanal (kanal)}
						<ChannelToggle
							label={KANAL_NAMEN[kanal]}
							checked={eintrag?.[kanal] ?? false}
							onchange={(an) => kanalSetzen(k, kanal, an)}
							disabled={kanal === 'premium_sms' && premiumSmsGate.disabled}
							hint={kanal === 'premium_sms' ? (premiumSmsGate.hint ?? undefined) : undefined}
							testid="kanal-schalter-{k}-{kanal}"
						/>
					{/each}
				</div>
			{/if}
			{#if aus.length > 0}
				<p class="amc-hinweis" data-testid="kanal-hinweis-nicht-im-abo-{k}">
					{$t('alarme.kanaele.nicht_im_abo', { kanaele: aus.map((a) => KANAL_NAMEN[a]).join(', ') })}
				</p>
			{/if}
			{#if metrikenVon(k).includes('wind_change')}
				<p class="amc-hinweis" data-testid="kanal-hinweis-wind-{k}">{$t('alarme.kanaele.wind_hinweis')}</p>
			{/if}
		</div>
	{/each}
</div>
{/if}

<style>
	.amc {
		display: flex;
		flex-direction: column;
		gap: 12px;
		margin-top: 24px;
	}
	.amc-zeile {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 0;
		border-top: 1px solid var(--g-line, #e2ddd2);
	}
	.amc-titel {
		font-weight: 600;
		color: var(--g-ink);
	}
	.amc-schalter {
		display: flex;
		flex-wrap: wrap;
		gap: 10px 20px;
	}
	.amc-hinweis {
		margin: 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
	}
</style>
