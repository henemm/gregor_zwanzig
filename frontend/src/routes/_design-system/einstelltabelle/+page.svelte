<script lang="ts">
	// Issue #3122 B3a — Vorschauseite der Bausteine Haken, RohEinfachKnopf und EinstellTabelle
	// (Sichtprüfung und Messort von e2e/einstelltabelle-bausteine.spec.ts). Nur Bausteine, Beispieldaten
	// nach dem Soll-Bild Fassung 4. Die Seite hält den Zustand selbst und schreibt jedes gemeldete
	// Ereignis in das Protokoll; sie ruft keine API. `?zustand=gemischt` zeigt abgewählte Zellen.
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { Card, Eyebrow, Haken, RohEinfachKnopf, Switch } from '$lib/components/atoms';
	import { EinstellTabelle, Einstellungszeile } from '$lib/components/molecules';
	import type { EinstellMetrik } from '$lib/components/molecules';
	import type { Darstellung } from '$lib/components/atoms';
	import { FESTE_ZEILE, orteMetriken, stellen, tripMetriken, type Flaeche } from './beispieldaten';

	let bereit = $state(false);
	let ereignisse = $state<Record<string, unknown>[]>([]);
	let kurzstil = $state(false);
	let hakenAn = $state(true);
	let knopf = $state<Darstellung>('raw');
	const tabellen = $state<Record<Flaeche, EinstellMetrik[]>>({ trip: tripMetriken(), orte: orteMetriken(page.url.searchParams.get('zustand') === 'gemischt') });

	onMount(() => {
		bereit = true;
	});

	const melde = (e: Record<string, unknown>) => ereignisse.push(e);
	const zelle = (f: Flaeche, metrik: string, stelle: string) => tabellen[f].find((m) => m.id === metrik)!.zellen[stelle];

	function haken(f: Flaeche, e: { metrik: string; stelle: string; an: boolean }) {
		zelle(f, e.metrik, e.stelle).zustand = e.an ? 'on' : 'off';
		melde({ quelle: f, art: 'haken', ...e });
	}
	function format(f: Flaeche, e: { metrik: string; stelle: string; format: Darstellung }) {
		zelle(f, e.metrik, e.stelle).format = e.format;
		melde({ quelle: f, art: 'format', ...e });
	}
	function reihenfolge(f: Flaeche, ids: string[]) {
		tabellen[f] = ids.map((id) => tabellen[f].find((m) => m.id === id)!);
		melde({ quelle: f, art: 'reihenfolge', metriken: ids });
	}
	const nie = (quelle: string) => () => melde({ quelle, unerwartet: true });
</script>

<Eyebrow>Design-System · Einstell-Tabelle „Was steht wo“</Eyebrow>

<Card padding={0}>
	<div data-testid="demo-haken">
		<Einstellungszeile titel="Haken: an / aus" hinweis="echtes Kontrollkästchen">
			<Haken zustand={hakenAn ? 'an' : 'aus'} name="Wind in E-Mail" onAenderung={(an) => { hakenAn = an; melde({ quelle: 'haken', an }); }} />
		</Einstellungszeile>
		<Einstellungszeile titel="Haken: gesperrt" hinweis="Strich mit Grund als Kurztext">
			<Haken zustand="gesperrt" name="Sonnenstunden im Stundenverlauf" grund="kein Stundenwert" onAenderung={nie('gesperrt')} />
		</Einstellungszeile>
		<Einstellungszeile titel="Haken: nicht in der E-Mail" hinweis="Strich, Grund als Name und Tooltip">
			<Haken zustand="nicht_in_email" name="Wind im 3-Tages-Ausblick" grund="nicht in der E-Mail" onAenderung={nie('nicht_in_email')} />
		</Einstellungszeile>
		<Einstellungszeile titel="Haken: fest" hinweis="ohne Abwahl">
			<Haken zustand="fest" name="Amtliche Warnungen in SMS" grund="immer dabei" onAenderung={nie('fest')} />
		</Einstellungszeile>
		<Einstellungszeile titel="Haken: nicht bedienbar" hinweis="Block aus oder Kurzstil">
			<Haken zustand="an" name="Böen in Telegram" bedienbar={false} onAenderung={nie('ruht')} />
		</Einstellungszeile>
	</div>
	<div data-testid="demo-knopf">
		<Einstellungszeile titel="Roh/Einfach-Knopf" hinweis="zeigt die aktuelle Form als Wort">
			<RohEinfachKnopf wert={knopf} name="Wind in E-Mail" onAenderung={(neu) => { knopf = neu; melde({ quelle: 'knopf', format: neu }); }} />
		</Einstellungszeile>
	</div>
	<Einstellungszeile titel="Telegram: Kurzstil" hinweis="Die Telegram-Spalte ruht dann, es gilt die SMS-Spalte.">
		<Switch checked={kurzstil} onchange={(v) => (kurzstil = v)} aria-label="Telegram im Kurzstil" testid="demo-kurzstil" tap />
	</Einstellungszeile>
</Card>

<Eyebrow>Trip · vier Stellen</Eyebrow>
<Card padding={0}>
	<EinstellTabelle testid="demo-trip" metrikTitel="Metrik" stellen={stellen('trip', kurzstil)} metriken={tabellen.trip} festeZeile={FESTE_ZEILE} onHaken={(e) => haken('trip', e)} onFormat={(e) => format('trip', e)} onReihenfolge={(ids) => reihenfolge('trip', ids)} />
</Card>

<Eyebrow>Orte · fünf Stellen</Eyebrow>
<Card padding={0}>
	<EinstellTabelle testid="demo-orte" metrikTitel="Metrik" stellen={stellen('orte', kurzstil)} metriken={tabellen.orte} festeZeile={FESTE_ZEILE} onHaken={(e) => haken('orte', e)} onFormat={(e) => format('orte', e)} onReihenfolge={(ids) => reihenfolge('orte', ids)} />
</Card>

<Eyebrow>Gemeldete Ereignisse</Eyebrow>
<pre data-testid="demo-ereignisse" data-bereit={bereit ? 'true' : 'false'}>{JSON.stringify(ereignisse)}</pre>
