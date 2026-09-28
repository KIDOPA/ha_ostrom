# Ostrom Custom Integration für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/badge/release-v1.2.0-blue.svg)](https://github.com/KIDOPA/ha_ostrom)

Home Assistant Integration für dynamische Stromtarife von **[Ostrom](https://ostrom.de)** über die offizielle **Ostrom Developer API**.

## Highlights & Sensoren

- ⚡ **Aktueller Strompreis**: Stündlicher Gesamt-Arbeitspreis in EUR/kWh inklusive Steuern, gesetzlicher Umlagen und arbeitsbezogener Netzentgelte.
- 🔮 **Preisvorschau in die Zukunft**:
  - `Preis nächste Stunde` (EUR/kWh)
  - `Günstigster Preis heute` & `Günstigste Uhrzeit heute` (z. B. `14:00` für Spülmaschine/EV)
  - `Höchster Preis heute` & `Teuerste Uhrzeit heute`
  - `Durchschnittspreis heute`
  - `Günstigster Preis morgen`, `Höchster Preis morgen` & `Durchschnittspreis morgen` (sobald nachmittags verfügbar)
  - `forecast`-Attribut mit stündlichen Start- und Endzeitstempeln für ApexCharts und Lovelace
- 🏷️ **Preisstufe & Rang**:
  - Preisstufe: `sehr_guenstig`, `guenstig`, `normal`, `teuer`, `sehr_teuer`.
  - Preis-Rang heute: 1 (günstigste Stunde des Tages) bis 24.
- 💶 **Fixkosten-Transparenz**:
  - `Monatliche Grundgebühr`: Ostrom-Grundgebühr + Grundpreis der Netzentgelte.
  - Tägliche anteilige Grundgebühr.
- 🔌 **Smart Meter & Verbrauchskosten**:
  - `Stromkosten heute` (aufgelaufene Verbrauchskosten sowie Attribut `gesamtkosten_heute_inkl_grundgebuehr`).
  - `Stromverbrauch heute` (kWh).

---

## Preisverlaufs-Diagramm im Dashboard (ApexCharts)

Kopiere folgenden Code in eine **Manuelle Karte** in deinem Dashboard (benötigt [ApexCharts Card](https://github.com/RomRider/apexcharts-card)):

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Ostrom Strompreis (Heute & Morgen)
  show_states: true
  colorize_states: true
graph_span: 48h
span:
  start: day
now:
  show: true
  label: Jetzt
series:
  - entity: sensor.ostrom_aktueller_strompreis
    name: Strompreis
    type: column
    data_generator: |
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.start).getTime(), entry.price];
      });
    color_threshold:
      - value: 0.20
        color: '#2b908f'
      - value: 0.30
        color: '#90ee7e'
      - value: 0.38
        color: '#f45b5b'
```
