---
spec_file: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md
spec_sha256: 045fa3ae5dd67e846e788a980a21269d859ed0efc304238afa813bc590ebd14a
---

# PO-Briefing: fix-2422-s3-kanal-an-aus-kette

- **Spec:** docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md
- **Issue:** #2422
- **Erstellt:** 2026-09-28

## Was gebaut wird

Im Editor abgeschaltete Morgen- oder Abend-Briefings werden nicht mehr verschickt; Kanal-, Zeit- und Formateinstellungen werden bis zur Auslieferung getestet.

## Definition of Done

Trip mit abgehaktem Abend bekommt auf Staging nur die Morgen-Mail; alle neuen Tests sind grün.

## Wie geprüft wird

Tests laufen den echten Versandweg bis zur Nachricht, mit zwei Nutzern und einer Staging-Mail; Anzahl betroffener Bestands-Trips messen sie nicht.

## Kritische Anmerkungen

- Bestands-Trips mit abgehaktem Morgen/Abend bekommen ab Deploy ein Briefing weniger; Anzahl unbekannt, Prod-Bestand nicht lesbar.
- Nicht alle Testlücken: Alarme, Ortsvergleich, Editor-Hinweise folgen später; ein als unerreichbar gewertetes Premium-SMS-Speicherproblem bleibt unbehoben.
- Ungefragt zusätzlich: Mail-Wetterpillen folgen der SMS-Schwelle; Umfang nahe Zeilenlimit, Parallelsitzung #2417 berührt dieselben Dateien.

## Freigabe-Frage

Darf ein im Editor abgehaktes Briefing ab Deploy bei allen Bestands-Trips wegfallen, auch wenn deren Anzahl unbekannt ist?
