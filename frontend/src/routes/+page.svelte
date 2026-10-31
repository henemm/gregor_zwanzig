<script lang="ts">
	// Issue 579 — Home-Screen 1:1 nach JSX (screen-home.jsx + screen-home-planning.jsx).
	// Spec: docs/specs/modules/issue_579_home_screen.md

	import type { Trip, ComparePreset, CockpitStatus } from '$lib/types.js';
	import { Card, Pill, Dot, Eyebrow, Btn, SectionH, PageHeader } from '$lib/components/atoms';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import {
		BriefingTimelineRow,
		QuickAction,
		SetupResumeCard
	} from '$lib/components/molecules';
	import {
		deriveStatusFromPreset
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { tripStatus, activeOrNextTrip, todayStageIndex } from '$lib/utils/tripStatus.js';
	import {
		plannedBriefings,
		archivedTrips,
		homeCompareTimeline,
		alertsForTrip
	} from './_home/cockpitHelpers.js';
	import {
		dayProgress,
		setupStepTrip,
		setupStepCompare,
		nextPlannedTrip,
		firstIncompleteCompare,
		liveTrip,
		// Issue #1268 (AC-10): geteilte Slot-Aufloesung — NICHT nachbauen.
		primarySendSlot
	} from '$lib/utils/cockpitHelpers568.js';
	// Issue #1969 (AC-23/AC-24): nächster Versand = Backend-Wert (+page.server.ts).
	// Hero und Kacheln formatieren ihn in _home/ (homeHeroProps bzw. kachelVersand -> formatNextBriefing).
	import type { NextBriefing } from '$lib/components/shared/versand-tab/nextBriefingText';
	import Startseite from './_start/Startseite.svelte';
	// Issue #2346 S2: EINE Startseiten-Kachel fuer Trip und Ortsvergleich.
	import SubscriptionKachel from './_home/SubscriptionKachel.svelte';
	import { kachelVersand, kachelNextBriefing } from './_home/kachelVersand.js';
	// Issue #2346 S3: EIN Startseiten-Hero fuer Trip und Ortsvergleich.
	import HomeHero from './_home/HomeHero.svelte';
	import { homeHeroProps } from './_home/homeHeroProps.js';
	import EmptyKachel from './_home/EmptyKachel.svelte';
	import StartklarCheckliste from './_home/StartklarCheckliste.svelte';
	import { buildCompareCtaHref } from './_home/compareCta.js';
	import { erzeugeOnboardingAktionen } from './_home/onboardingAktionen.js';
	import {
		zeigeWillkommen,
		zeigeCheckliste,
		type OnboardingProfil
	} from './_home/onboardingSichtbarkeit.js';
	import { api } from '$lib/api.js';
	import { tr } from '$lib/i18n/index.js';

	let { data } = $props();

	const now = new Date();
	const trips = $derived((data.trips ?? []) as Trip[]);
	// Issue #1969: { trips: {id: NB}, compare: {id: NB} } oder null (fail-soft ⇒ „—").
	const nextBriefings = $derived(
		(data as { nextBriefings?: { trips: Record<string, NextBriefing>; compare: Record<string, NextBriefing> } | null })
			.nextBriefings ?? null
	);
	const compareNb = (id: string | undefined): NextBriefing | null =>
		(id && nextBriefings?.compare?.[id]) || null;
	const presets = $derived((data.presets ?? []) as ComparePreset[]);
	const activePresets = $derived(
		presets.filter((p) => deriveStatusFromPreset(p) === 'active')
	);
	const cockpitStatus = $derived((data.cockpitStatus ?? null) as CockpitStatus | null);
	const isEmpty = $derived(trips.length === 0 && presets.length === 0);

	// Issue #2521 S2 — Onboarding. Profilstand vom Loader; lokale Overrides
	// spiegeln nur, was der Nutzer gerade geklickt hat (die Wahrheit liegt im Profil).
	let onbLokal = $state<Partial<OnboardingProfil>>({});
	let testmailStatus = $state<'idle' | 'loading' | 'error'>('idle');
	let testmailFehler = $state<string | null>(null);
	const onb = $derived(
		data.onboarding ? ({ ...data.onboarding, ...onbLokal } as OnboardingProfil) : null
	);
	const bestand = $derived({ tripCount: trips.length, compareCount: presets.length });
	const willkommenSichtbar = $derived(onb ? zeigeWillkommen(onb, bestand) : false);
	const checklisteSichtbar = $derived(onb ? zeigeCheckliste(onb, bestand) : false);

	// Klick-Logik liegt testbar in ./_home/onboardingAktionen.ts.
	const { verstanden, ausblenden, sendeTestmail } = erzeugeOnboardingAktionen({
		api,
		t: tr,
		getLokal: () => onbLokal,
		setLokal: (neu) => (onbLokal = neu),
		setTestmail: (status, fehler) => {
			testmailStatus = status;
			testmailFehler = fehler;
		}
	});

	const todayPretty = now.toLocaleDateString('de-DE', {
		weekday: 'short',
		day: '2-digit',
		month: 'long',
		year: 'numeric'
	});
	// Mobile-Shell S2 — Datum als Mono-Caption neben der Wordmark („Sa., 19. Sep.").
	const heuteKurz = now.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' });

	// --- Hero-Modus: trip > compare > planning --------------------------------
	const activeLiveTrip = $derived(liveTrip(trips, now));

	const mode = $derived(
		activeLiveTrip ? 'trip' : (activePresets.length > 0 ? 'compare' : 'planning')
	);

	const compareHero = $derived(mode === 'compare' ? activePresets[0] : null);

	// "Außerdem beobachtet" — nebenher laufende Vergleiche
	const alsoWatched = $derived(
		mode === 'trip' ? activePresets :
		mode === 'compare' ? activePresets.slice(1) : []
	);

	// --- Hero-Trip (aktiv) --------------------------------------------------
	const hero = $derived(mode === 'trip' ? activeLiveTrip : null);
	const heroIsActive = $derived(mode === 'trip');
	const heroStages = $derived(hero?.stages ?? []);
	const todayIdx = $derived(hero ? todayStageIndex(hero, now) : -1);
	const heroStageIdx = $derived(todayIdx >= 0 ? todayIdx : 0);
	const dayX = $derived(heroIsActive ? heroStageIdx + 1 : 1);
	const dayY = $derived(heroStages.length);
	const progressPct = $derived(dayProgress(dayX, dayY));

	// --- Planungs-Kandidaten ------------------------------------------------
	const nextPlanned = $derived(nextPlannedTrip(trips, now));
	const firstIncomplete = $derived(firstIncompleteCompare(presets));
	const setupStepsTrip = $derived(nextPlanned ? setupStepTrip(nextPlanned) : []);
	const setupStepsCompare = $derived(firstIncomplete ? setupStepCompare(firstIncomplete) : []);

	// Issue #1743: der Versand steht unten im Reiter Wetter-Metriken (Anker #versand).
	const TRIP_TAB_MAP = ['etappen', 'etappen', 'wetter-metriken', 'wetter-metriken#versand', 'wetter-metriken#versand'];

	function buildTripCtaHref(): string {
		if (!nextPlanned) return '/trips/new';
		const firstOpen = setupStepsTrip.findIndex((s) => !s.done);
		if (firstOpen < 0) return `/trips/${nextPlanned.id}?tab=uebersicht`;
		if (firstOpen === 0) return '/trips/new';
		return `/trips/${nextPlanned.id}?tab=${TRIP_TAB_MAP[firstOpen]}`;
	}

	const tripCtaHref = $derived(buildTripCtaHref());
	// Issue #2521 S2 (AC-16): reiner Export, Ziel ohne angefangenen Vergleich = /compare/new.
	const compareCtaHref = $derived(buildCompareCtaHref(firstIncomplete));

	// --- Rechte Spalte / Archiv ---------------------------------------------
	const briefings = $derived(
		hero
			? plannedBriefings(hero.report_config, cockpitStatus?.briefings, hero.id, nextBriefings?.trips?.[hero.id] ?? null)
			: []
	);
	const heroAlerts = $derived(alertsForTrip(cockpitStatus?.alerts, hero?.id));
	const archive = $derived(archivedTrips(trips, now, 4));

	// AC-9: fertig-Trips aus otherTrips ausschließen
	const otherTrips = $derived(trips.filter((t) => t.id !== hero?.id && tripStatus(t, now) !== 'fertig'));

	// Datum-Range für den Fortschrittsbalken
	const heroDateRange = $derived.by(() => {
		if (!hero) return '';
		const dates = (hero.stages ?? [])
			.map((s: { date?: string }) => s.date)
			.filter((d: string | undefined): d is string => !!d)
			.sort();
		if (dates.length === 0) return '';
		const fmt = (iso: string) =>
			new Date(iso).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' });
		return dates.length === 1 ? fmt(dates[0]) : `${fmt(dates[0])} → ${fmt(dates[dates.length - 1])}`;
	});
</script>

<!-- Issue #2520 — Ausgeloggte sehen die oeffentliche Startseite, Eingeloggte das Cockpit. -->
{#if data.oeffentlich}
	<Startseite />
{:else}
<div class="page-root" style:position="relative" style:max-width="1320px">
	<!-- Mobile-Shell S2 — Wordmark + Datum als erste Zeile der Uebersicht (nur
	     hier, nur mobil): die Marke einmal pro Sitzung statt in einem fixen
	     Balken auf jedem Screen. Desktop traegt sie in der Sidebar. -->
	<div class="desktop:hidden" data-testid="home-wordmark-row" style="display: flex; align-items: center; justify-content: space-between; height: 24px; margin: var(--g-s-2) 0 var(--g-s-5);">
		<Wordmark size="sm" />
		<span class="mono" data-testid="home-datum" style="font-size: 11px; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase; color: var(--g-ink-3);">{heuteKurz}</span>
	</div>
	<!-- Topbar — AC-7: kein sub-Text, beide Buttons ghost -->
	<PageHeader
		eyebrow="Übersicht · {todayPretty}"
		title="Deine Trips & Vergleiche"
	>
		{#snippet right()}
			<Btn href="/trips/new" variant="ghost" size="sm">+ Neuer Trip</Btn>
			<Btn href="/compare/new" variant="ghost" size="sm">+ Neuer Vergleich</Btn>
		{/snippet}
	</PageHeader>

	{#if checklisteSichtbar && onb}
		<StartklarCheckliste
			profil={onb}
			tripCount={trips.length}
			compareCount={presets.length}
			{testmailStatus}
			{testmailFehler}
			onTestmail={sendeTestmail}
			onAusblenden={ausblenden}
		/>
	{/if}

	{#if isEmpty}
		<EmptyKachel
			willkommen={willkommenSichtbar}
			{testmailStatus}
			{testmailFehler}
			onTestmail={sendeTestmail}
			onVerstanden={verstanden}
		/>
	{:else}

		<!-- Zustand A: aktiver Trip-Hero + Schnellaktionen in linker Spalte -->
		{#if hero && heroIsActive}
			<!-- #2346 S3: ein HomeHero fuer beide kinds (2-Spalten-Grid, rechte Spalte als aside) -->
				<!-- Kanaele (Flags, Slot-Regel #2422), naechster Versand (Backend), Link: homeHeroProps -->
				<HomeHero {...homeHeroProps('trip', hero, nextBriefings)}>
					{#snippet pills()}
						<Pill tone="accent"><Dot tone="bad" size={6} /> Live · Tag {dayX} von {dayY}</Pill>
						<Pill tone="ghost">Sommer-Trekking</Pill>
					{/snippet}
					{#snippet details()}
						<!-- Fortschrittsbalken mit Label "Tag x / y" + Datum-Range (volle Breite) -->
						<div style:grid-column="1 / -1">
							<div
									style:display="flex"
									style:justify-content="space-between"
									style:align-items="baseline"
									style:margin-bottom="8px"
								>
									<span
										style:font-family="var(--g-font-mono)"
										style:font-size="11px"
										style:color="var(--g-ink-2)"
										style:letter-spacing="0.06em"
										style:text-transform="uppercase"
										style:font-weight="600"
									>Tag {dayX} / {dayY}</span>
									<span
										style:font-family="var(--g-font-mono)"
										style:font-size="11px"
										style:color="var(--g-ink-3)"
									>{heroDateRange}</span>
								</div>
								<div
									style:height="6px"
									style:border-radius="999px"
									style:background="var(--g-paper-deep)"
									style:overflow="hidden"
								>
									<div
										style:width="{progressPct}%"
										style:height="100%"
										style:background="var(--g-accent)"
										style:border-radius="999px"
									></div>
								</div>
							</div>
					{/snippet}
					{#snippet actions()}
						<!-- AC-3/V13: Schnellaktionen vertikal in linker Spalte -->
						<QuickAction
							glyph="pause"
							label="Pausentag einplanen"
							sub="→ Etappen & Wegpunkte"
							href="/trips/{hero.id}?tab=etappen"
						/>
						<QuickAction
							glyph="metrics"
							label="Wetter-Metriken ändern"
							sub="→ Wetter-Metriken"
							href="/trips/{hero.id}?tab=wetter-metriken"
						/>
						<QuickAction
							glyph="clock"
							label="Briefing-Zeitplan"
							sub="→ Briefing-Zeitplan"
							href="/trips/{hero.id}?tab=wetter-metriken#versand"
						/>
						<QuickAction
							glyph="send"
							label="Test-Briefing schicken"
							sub="→ An deine eigenen Kanäle"
							href="/trips/{hero.id}?action=test-send"
						/>
					{/snippet}
					{#snippet aside()}
				<!-- Rechte Spalte: Outbox + Alerts -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<!-- Outbox -->
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="14px"
							style:gap="12px"
						>
							<div style:min-width="0">
								<Eyebrow style="margin-bottom: 4px">Versand · heute</Eyebrow>
								<div
									style:font-size="17px"
									style:font-weight="600"
									style:white-space="nowrap"
									style:overflow="hidden"
									style:text-overflow="ellipsis"
								>
									Was geht raus · <span style:color="var(--g-ink-2)" style:font-weight="600">{hero?.name ?? ''}</span>
								</div>
							</div>
							<Pill tone="good">Alle Kanäle ok</Pill>
						</div>
						{#if briefings.length > 0}
							<div style:display="flex" style:flex-direction="column" style:gap="8px">
								{#each briefings.slice(0, 3) as r, i (i)}
									<BriefingTimelineRow report={r} />
								{/each}
							</div>
						{:else}
							<div style:font-size="13px" style:color="var(--g-ink-2)">
								Keine Briefings für diesen Trip geplant.
							</div>
						{/if}
					</Card>

					<!-- Alerts -->
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="12px"
						>
							<div>
								<Eyebrow style="margin-bottom: 4px">Alerts · letzte 24 h</Eyebrow>
								<div style:font-size="17px" style:font-weight="600">
									{heroAlerts.length > 0 ? `${heroAlerts.length} ausgelöst` : 'Keine'}
								</div>
							</div>
							<a
								href="/trips/{hero.id}?tab=wertebereiche"
								class="g-link-tap"
								style:font-size="12px"
								style:color="var(--g-ink-3)"
								style:text-decoration="none"
								style:font-family="var(--g-font-mono)"
							>Schwellen →</a>
						</div>
						{#if heroAlerts.length > 0}
							<div style:display="flex" style:flex-direction="column" style:gap="6px">
								{#each heroAlerts as alert (alert.sent_at)}
									<div
										style:display="flex"
										style:align-items="center"
										style:gap="8px"
										style:padding="8px 10px"
										style:background="var(--g-card-alt)"
										style:border="1px solid var(--g-rule-soft)"
										style:border-radius="var(--g-r-2)"
										style:font-size="13px"
									>
										<Dot
											tone={alert.severity === 'HIGH'
												? 'bad'
												: alert.severity === 'MODERATE'
													? 'warn'
													: 'neutral'}
										/>
										<span style:color="var(--g-ink-2)"
											>{new Date(alert.sent_at).toLocaleTimeString('de-DE', {
												hour: '2-digit',
												minute: '2-digit'
											})}</span
										>
										<span style:color="var(--g-ink-2)"
											>{alert.changes_count} Änderung{alert.changes_count !== 1
												? 'en'
												: ''}</span
										>
									</div>
								{/each}
							</div>
						{:else}
							<div
								style:font-size="13px"
								style:color="var(--g-ink-2)"
								style:line-height="1.5"
								style:padding-top="2px"
							>
								Keine Schwellen-Überschreitung in den verglichenen Orten. Du wirst sofort benachrichtigt, sobald eine Bedingung kippt.
							</div>
						{/if}
					</Card>
				</div>
					{/snippet}
				</HomeHero>
		{/if}

		<!-- Zustand C: Compare-Hero (kein aktiver Trip, aber aktive Vergleiche) -->
		{#if mode === 'compare' && compareHero}
			<!-- #2346 S3: derselbe HomeHero wie der Trip -->

				<!-- Kanaele aus den Flags, nie aus empfaenger (#1452): homeHeroProps -->
				<HomeHero {...homeHeroProps('vergleich', compareHero, nextBriefings)}>
					{#snippet pills()}
						<Pill tone="accent"><Dot tone="good" size={6} /> Aktiv · läuft automatisch</Pill>
						{#if (compareHero.display_config as Record<string,unknown> | undefined)?.profile_label}
							<Pill tone="ghost">{(compareHero.display_config as Record<string,unknown>).profile_label as string}</Pill>
						{/if}
					{/snippet}
					{#snippet details()}
						<!-- Zeitplan (neben dem Naechsten Versand) -->
						<div
							style:padding="12px 14px"
							style:border="1px solid var(--g-rule-soft)"
							style:border-radius="var(--g-r-2)"
							style:background="var(--g-paper-deep)"
						>
							<div
								style:font-family="var(--g-font-mono)"
								style:font-size="11px"
								style:color="var(--g-ink-3)"
								style:text-transform="uppercase"
								style:letter-spacing="0.1em"
								style:margin-bottom="5px"
							>Zeitplan</div>
							<div style:font-size="15px" style:font-weight="600">
								{compareHero.schedule === 'daily' ? 'täglich' : compareHero.schedule === 'weekly' ? 'wöchentlich' : 'manuell'}
								<!-- Issue #1268 (AC-10): echte Versandzeit aus dem Slot statt hour_from
								     (zeigte bei neu angelegten Vergleichen "· 00:00"). -->
								{#if compareHero.schedule !== 'manual' && primarySendSlot(compareHero)} · {String(primarySendSlot(compareHero)!.hour).padStart(2,'0')}:00{/if}
							</div>
						</div>
					{/snippet}
					{#snippet actions()}
						<QuickAction
							glyph="route"
							label="Orte bearbeiten"
							sub="→ Verglichene Orte"
							href="/compare/{compareHero.id}"
						/>
						<QuickAction
							glyph="metrics"
							label="Ideal-Werte ändern"
							sub="→ Ideal-Profil"
							href="/compare/{compareHero.id}?tab=wertebereiche"
						/>
						<QuickAction
							glyph="clock"
							label="Briefing-Zeitplan"
							sub="→ Zeitplan & Kanäle"
							href="/compare/{compareHero.id}?tab=wetter-metriken#versand"
						/>
						<QuickAction
							glyph="send"
							label="Test-Vergleich schicken"
							sub="→ An deine eigenen Kanäle"
							href="/compare/{compareHero.id}?action=test-send"
						/>
					{/snippet}
					{#snippet aside()}
				<!-- Rechte Spalte: Outbox + Alerts -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="14px"
							style:gap="12px"
						>
							<div style:min-width="0">
								<Eyebrow style="margin-bottom: 4px">Versand · heute</Eyebrow>
								<div
									style:font-size="17px"
									style:font-weight="600"
									style:white-space="nowrap"
									style:overflow="hidden"
									style:text-overflow="ellipsis"
								>
									Was geht raus · <span style:color="var(--g-ink-2)" style:font-weight="600">{compareHero.name}</span>
								</div>
							</div>
							<Pill tone="good">Alle Kanäle ok</Pill>
						</div>
						{#if homeCompareTimeline(compareHero, compareNb(compareHero.id)).length > 0}
							<div
								style:display="flex"
								style:flex-direction="column"
								style:gap="8px"
								style:margin-top="8px"
							>
								{#each homeCompareTimeline(compareHero, compareNb(compareHero.id)) as r, i (i)}
									<BriefingTimelineRow report={r} />
								{/each}
							</div>
						{:else}
							<div style:font-size="13px" style:color="var(--g-ink-2)" style:margin-top="8px">
								Versand läuft automatisch gemäß Zeitplan.
							</div>
						{/if}
					</Card>
					<Card padding={20}>
						<div
							style:display="flex"
							style:justify-content="space-between"
							style:align-items="center"
							style:margin-bottom="12px"
						>
							<div>
								<Eyebrow style="margin-bottom: 4px">Alerts · letzte 24 h</Eyebrow>
								<div style:font-size="17px" style:font-weight="600">Keine</div>
							</div>
							<a
								href="/compare/{compareHero.id}"
								style:font-size="12px"
								style:color="var(--g-ink-3)"
								style:text-decoration="none"
								style:font-family="var(--g-font-mono)"
							>Schwellen →</a>
						</div>
						<div style:font-size="13px" style:color="var(--g-ink-2)" style:line-height="1.5" style:padding-top="2px">
							Keine Schwellen-Überschreitung in den verglichenen Orten. Du wirst sofort benachrichtigt, sobald eine Bedingung kippt.
						</div>
					</Card>
				</div>
					{/snippet}
				</HomeHero>
		{/if}

		<!-- Zustand B: Planungs-/Leerzustand (kein aktiver Trip, keine aktiven Vergleiche) -->
		{#if mode === 'planning'}
			<!-- Ehrlicher Hinweis-Banner -->
			<div
				style:display="flex"
				style:align-items="center"
				style:gap="12px"
				style:margin-bottom="28px"
				style:padding="12px 18px"
				style:border-radius="var(--g-r-3)"
				style:background="var(--g-card-alt)"
				style:border="1px solid var(--g-rule-soft)"
			>
				<Dot tone="neutral" size={8} />
				<span style:font-size="14px" style:color="var(--g-ink-2)">
					Aktuell läuft <strong>kein Trip</strong>. Sobald deine nächste Reise startet, schickt <span style:font-family="var(--g-font-mono)" style:font-size="13px">gregor · zwanzig</span> die Briefings automatisch in deine Kanäle.
				</span>
			</div>

			<!-- Weiter einrichten -->
			{#if nextPlanned || firstIncomplete}
				<div style:margin-bottom="36px">
					<SectionH
						eyebrow="Weiter einrichten"
						title="Mach weiter, wo du aufgehört hast"
						kicker="Du nutzt die Webseite vor allem zur Vorbereitung — hier liegen deine offenen Entwürfe"
					/>
					<div class="setup-grid">
						{#if nextPlanned}
							<SetupResumeCard
								tone="accent"
								eyebrow="Nächster Trip"
								title={nextPlanned.name}
								steps={setupStepsTrip}
								ctaLabel="Setup fortsetzen"
								ctaHref={tripCtaHref}
								secondary={{ label: 'Öffnen', href: `/trips/${nextPlanned.id}?tab=uebersicht` }}
							/>
						{/if}
						{#if firstIncomplete}
							<SetupResumeCard
								eyebrow="Orts-Vergleich"
								title={firstIncomplete.name}
								steps={setupStepsCompare}
								ctaLabel="Setup fortsetzen"
								ctaHref={compareCtaHref}
								secondary={{ label: 'Öffnen', href: `/compare/${firstIncomplete.id}` }}
								tone="default"
							/>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Schnell anlegen -->
			<div style:margin-bottom="36px">
				<SectionH eyebrow="Schnell anlegen" title="Neu starten" />
				<div class="quick-create-grid">
					<QuickAction
						glyph="route"
						tone="accent"
						label="Neuer Trip"
						sub="Wizard · 5 Schritte"
						href="/trips/new"
					/>
					<QuickAction
						glyph="metrics"
						label="Neuer Orts-Vergleich"
						sub="Wizard · 5 Schritte"
						href="/compare/new"
					/>
				</div>
			</div>
		{/if}

		<!-- AC-5/V5: "Außerdem beobachtet" in Card mit Titel + Link -->
		{#if alsoWatched.length > 0}
			<Card padding={20} style="margin-bottom: 36px">
				<div
					style:display="flex"
					style:justify-content="space-between"
					style:align-items="baseline"
					style:margin-bottom="4px"
					style:gap="16px"
				>
					<div>
						<Eyebrow style="margin-bottom: 4px">Außerdem beobachtet</Eyebrow>
						<div style:font-size="15px" style:font-weight="600">
							{#if alsoWatched.length === 1}
								{alsoWatched.length} Orts-Vergleich läuft nebenher
							{:else}
								{alsoWatched.length} Orts-Vergleiche laufen nebenher
							{/if}
						</div>
					</div>
					<a
						href="/compare"
						class="g-link-tap"
						style:font-size="12px"
						style:color="var(--g-ink-3)"
						style:text-decoration="none"
						style:font-family="var(--g-font-mono)"
					>Alle Vergleiche →</a>
				</div>
				<!-- Issue #2346 S2: Vergleiche als dieselbe Startseiten-Kachel wie Trips. -->
				<div class="kachel-grid" style:margin-top="12px">
					{#each alsoWatched as preset (preset.id)}
						{@const v = kachelVersand('vergleich', preset, kachelNextBriefing('vergleich', preset.id, nextBriefings))}
						<SubscriptionKachel kind="vergleich" sub={preset} nextSend={v.nextSend} lastSent={v.lastSent} />
					{/each}
				</div>
			</Card>
		{/if}

		<!-- Weitere Trips (nicht hero, nicht fertig) — nur im Trip/Compare-Modus -->
		{#if mode !== 'planning' && otherTrips.length > 0}
			<section style:margin-bottom="32px">
				<div class="kachel-grid">
					{#each otherTrips as trip (trip.id)}
						{@const v = kachelVersand('trip', trip, kachelNextBriefing('trip', trip.id, nextBriefings))}
						<SubscriptionKachel kind="trip" sub={trip} nextSend={v.nextSend} lastSent={v.lastSent} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- AC-2 (Trip-Modus): Einrichten / Frühere Trips -->
		{#if mode === 'trip' && archive.length > 0}
			<div style:margin-bottom="40px">
				<SectionH eyebrow="Einrichten" title="Frühere Trips" kicker="{archive.length} abgeschlossene Mehrtages-Trips" right={archiveLink} />
				<div class="archive-grid">
					{#each archive as t (t.id)}
						{@render archiveCard(t)}
					{/each}
				</div>
			</div>
		{/if}

		<!-- AC-1 + AC-3 (Compare-Modus): Einrichten / Kein Trip geplant — Kopf immer sichtbar -->
		{#if mode === 'compare'}
			<div style:margin-bottom="40px">
				<SectionH eyebrow="Einrichten" title="Kein Trip geplant" kicker="Sobald ein Mehrtages-Trip ansteht, übernimmt er das Cockpit" right={newTripLink} />
				{#if archive.length > 0}
					<div class="archive-grid">
						{#each archive as t (t.id)}
							{@render archiveCard(t)}
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		<!-- Planning-Modus: Archiv in Card (1:1 screen-home-planning.jsx Z.133) -->
		{#if mode === 'planning' && archive.length > 0}
			<Card padding={20}>
				<div style:margin-bottom="40px">
					<SectionH eyebrow="Archiv" title="Frühere Trips" kicker="{archive.length} abgeschlossene Trips" right={archiveLink} />
					<div class="archive-grid">
						{#each archive as t (t.id)}
							{@render archiveCard(t)}
						{/each}
					</div>
				</div>
			</Card>
		{/if}
	{/if}
</div>

{#snippet archiveLink()}
	<Btn href="/trips" variant="quiet" size="sm">Alle anzeigen</Btn>
{/snippet}

{#snippet newTripLink()}
	<Btn href="/trips/new" variant="primary" size="sm">Neuer Trip</Btn>
{/snippet}

{#snippet archiveCard(t: { id: string; dates: string; name: string; stages: number })}
	<a
		href="/trips/{t.id}"
		style:padding="14px 16px"
		style:border="1px solid var(--g-rule-soft)"
		style:border-radius="var(--g-r-2)"
		style:background="var(--g-card-alt)"
		style:text-decoration="none"
		style:color="var(--g-ink)"
		style:display="block"
	>
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="var(--g-text-xs)"
			style:color="var(--g-ink-3)"
			style:text-transform="uppercase"
			style:letter-spacing="var(--g-track-caps)"
			style:margin-bottom="4px"
		>{t.dates}</div>
		<div
			style:font-size="var(--g-text-sm)"
			style:font-weight="600"
			style:line-height="1.3"
			style:margin-bottom="6px"
		>{t.name}</div>
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="11px"
			style:color="var(--g-ink-3)"
		>{t.stages} {t.stages === 1 ? 'Etappe' : 'Etappen'}</div>
	</a>
{/snippet}


{/if}

<style>
	/* .cockpit-hero (Hero-Raster) lebt seit #2346 S3 in _home/HomeHero.svelte. */
	.setup-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
	}
	.quick-create-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 14px;
	}
	.archive-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
	}
	.kachel-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}
	@media (max-width: 899px) {
		.setup-grid {
			grid-template-columns: 1fr;
		}
		.quick-create-grid {
			grid-template-columns: repeat(2, 1fr);
		}
		.archive-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	.page-root {
		padding: 0 0 80px;
	}
	@media (max-width: 640px) {
		.page-root {
			/* F002: Inhalt darf nicht hinter der fixen Mobile-Bottom-Nav verschwinden (64px + Safe Area) */
			padding-bottom: 120px;
		}
		.quick-create-grid {
			grid-template-columns: 1fr;
		}
	}
	@media (min-width: 640px) {
		.kachel-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (min-width: 1024px) {
		.kachel-grid {
			grid-template-columns: repeat(3, 1fr);
		}
	}
</style>
