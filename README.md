# ⚡ Ostrom Integration für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/KIDOPA/ha_ostrom?style=for-the-badge&color=blue)](https://github.com/KIDOPA/ha_ostrom/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blueviolet?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

> Die moderne, zuverlässige Home Assistant Integration für deinen dynamischen Stromtarif von **[Ostrom](https://ostrom.de)** über die offizielle **Ostrom Developer API**.
>
> 💡 **Echte Endkundenpreise**: Zeigt nicht nur den nackten Börsenpreis, sondern berechnet den **vollständigen Brutto-Arbeitspreis** inklusive aller Steuern, Umlagen und regionalen Netzentgelte.

---

## 🌟 Highlights auf einen Blick

- 💶 **Echte Gesamtkosten (Brutto)**: Cent-genauer Arbeitspreis (`EUR/kWh`) inklusive Börsenpreis, Steuern (19% MwSt.), Konzessionsabgaben, KWKG-Umlage, Offshore-Netzumlage und regionaler Netzentgelte deines Verteilnetzbetreibers.
- 🔮 **48h Day-Ahead Preisvorschau**: Vollständiges `forecast`-Attribut (kompatibel mit [ApexCharts Card](https://github.com/RomRider/apexcharts-card)), das die Preise von heute und morgen stundengenau abbildet.
- 🕒 **Perfekt für Automationen**:
  - `Preis nächste Stunde`: Reagiere schon 60 Minuten vorher auf Preissprünge.
  - `Günstigste Uhrzeit heute` & `Günstigste Uhrzeit morgen`: Starte Großverbraucher exakt zum optimalen Zeitpunkt.
  - `Preis Rang heute` (1 bis 24): Schalte Geräte ein, wenn die Stunde zu den X günstigsten des Tages gehört.
  - `Preisstufe`: Sofortige Einordnung in `sehr_guenstig`, `guenstig`, `normal`, `teuer` oder `sehr_teuer`.
- 📊 **Transparente Fixkosten**: Exakte Aufschlüsselung der monatlichen Grundgebühr (Ostrom-Gebühr + Grundpreis des Netzbetreibers) sowie tägliche anteilige Kosten.
- ⚡ **Smart Meter & Verbrauchskosten**: Verfolgung des stündlichen Verbrauchs und der aufgelaufenen Stromkosten für den heutigen Tag (bei Nutzung eines Smart-Meters wie Ostrom Pulse).
- 🔒 **Sicher & Modern**: Vollständiger OAuth2 Client-Credentials Flow mit automatischem Token-Refresh, typed DataUpdateCoordinator und asynchronem `aiohttp`.

---

## 📋 Übersicht der 24 Sensoren

Alle Sensoren werden unter dem Gerät **Ostrom (<Deine-PLZ>)** gebündelt:

| Sensor | Entitäts-ID | Einheit | Beschreibung |
| :--- | :--- | :---: | :--- |
| **Aktueller Strompreis** | `sensor.ostrom_aktueller_strompreis` | `EUR/kWh` | Brutto-Gesamtarbeitspreis der aktuellen Stunde. Enthält das `forecast`-Array. |
| **Preis nächste Stunde** | `sensor.ostrom_preis_nachste_stunde` | `EUR/kWh` | Preis der direkt folgenden Stunde. |
| **Günstigster Preis heute** | `sensor.ostrom_gunstigster_preis_heute` | `EUR/kWh` | Tiefstpreis des aktuellen Tages. |
| **Günstigste Uhrzeit heute** | `sensor.ostrom_gunstigste_uhrzeit_heute` | `HH:MM` | Uhrzeit des Tiefstpreises heute (z. B. `13:00`). |
| **Höchster Preis heute** | `sensor.ostrom_hochster_preis_heute` | `EUR/kWh` | Spitzenpreis des heutigen Tages. |
| **Teuerste Uhrzeit heute** | `sensor.ostrom_teuerste_uhrzeit_heute` | `HH:MM` | Uhrzeit des Spitzenpreises heute (z. B. `18:00`). |
| **Durchschnittspreis heute** | `sensor.ostrom_durchschnittspreis_heute` | `EUR/kWh` | Arithmetischer Mittelwert aller 24 Stunden heute. |
| **Günstigster Preis morgen** | `sensor.ostrom_gunstigster_preis_morgen` | `EUR/kWh` | Tiefstpreis für den morgigen Tag *(ab ~13:30 Uhr)*. |
| **Günstigste Uhrzeit morgen** | `sensor.ostrom_gunstigste_uhrzeit_morgen` | `HH:MM` | Uhrzeit des Tiefstpreises morgen *(ab ~13:30 Uhr)*. |
| **Höchster Preis morgen** | `sensor.ostrom_hochster_preis_morgen` | `EUR/kWh` | Spitzenpreis für morgen *(ab ~13:30 Uhr)*. |
| **Teuerste Uhrzeit morgen** | `sensor.ostrom_teuerste_uhrzeit_morgen` | `HH:MM` | Uhrzeit des Spitzenpreises morgen *(ab ~13:30 Uhr)*. |
| **Durchschnittspreis morgen** | `sensor.ostrom_durchschnittspreis_morgen` | `EUR/kWh` | Tagesdurchschnitt für morgen *(ab ~13:30 Uhr)*. |
| **Monatliche Grundgebühr** | `sensor.ostrom_monatliche_grundgebuhr` | `EUR` | Feste monatliche Gebühren (Ostrom + Netzentgelte). |
| **Preisstufe** | `sensor.ostrom_preisstufe` | Text | `sehr_guenstig`, `guenstig`, `normal`, `teuer`, `sehr_teuer`. |
| **Preis Rang heute** | `sensor.ostrom_preis_rang_heute` | Zahl | Rang der aktuellen Stunde (1 = billigste Stunde, 24 = teuerste). |
| **Stundenverbrauch vor 48h** | `sensor.ostrom_stundenverbrauch_vor_48h` | `kWh` | Stündlicher Smart-Meter-Verbrauch der aktuellen Stunde von vor 48 Stunden (Quelle für Utility Meter mit `delta_values: true`). |
| **Stundenkosten vor 48h** | `sensor.ostrom_stundenkosten_vor_48h` | `EUR` | Berechnete Stromkosten der Stunde vor 48 Stunden (inkl. anteiliger Grundgebühr). |
| **Stromkosten gestern** | `sensor.ostrom_stromkosten_gestern` | `EUR` | Gesamtkosten von gestern exakt wie in der Ostrom-App (inkl. anteiliger Grundgebühr; Marktpreis, Abgaben & 24h-Stundenwerte in Attributen). |
| **Stromverbrauch gestern** | `sensor.ostrom_stromverbrauch_gestern` | `kWh` | Vom Smart-Meter gemessener Gesamtverbrauch von gestern (inkl. 24h-Stundenwerte in Attributen). |
| **Stromkosten vor 48h** | `sensor.ostrom_stromkosten_vor_48h` | `EUR` | Gesamtkosten von vor 48 Stunden exakt wie in der Ostrom-App (inkl. anteiliger Grundgebühr; Marktpreis, Abgaben & 24h-Stundenwerte in Attributen). |
| **Stromverbrauch vor 48h** | `sensor.ostrom_stromverbrauch_vor_48h` | `kWh` | Vom Smart-Meter gemessener Gesamtverbrauch von vor 48 Stunden (inkl. 24h-Stundenwerte in Attributen). |
| **Stromkosten heute** | `sensor.ostrom_stromkosten_heute` | `EUR` | Aufgelaufene Kosten heute (sobald Daten vorliegen). |
| **Stromverbrauch heute** | `sensor.ostrom_stromverbrauch_heute` | `kWh` | Gemessener Verbrauch heute (sobald Daten vorliegen). |
| **Zählerstand** | `sensor.ostrom_zahlerstand` | `kWh` | *(Standardmäßig deaktiviert, da Ostrom nur Intervall-kWh liefert).* |

---

## ⚡ Wichtiger Hinweis zu Smart-Meter-Verbrauchsdaten

> [!TIP]
> **Warum gibt es Sensoren für „gestern“ und „vor 48h“?**
> Deutsche Messstellenbetreiber und Smart-Meter-Gateways übermitteln Messdaten nicht in Echtzeit an die Stromanbieter, sondern gebündelt mit **24 bis 48 Stunden Verzögerung**.
>
> In der Ostrom-App und -API stehen die verifizierten Verbrauchs- und Abrechnungsdaten daher immer für den **Vortag (gestern)** bzw. sicher für **vor 48 Stunden** bereit. Die Sensoren berechnen stundengenau den jeweiligen Arbeitspreis multipliziert mit deinem gemessenen Verbrauch für diese Tage.
>
> **Tipp für Live-Kosten in Echtzeit:**  
> Möchtest du deine Stromkosten sekundengenau und ohne 48h Verzögerung verfolgen, binde deinen Stromzähler (z. B. via IR-Lesekopf / Shelly 3EM) in das offizielle **Home Assistant Energie-Dashboard** ein und wähle dort `sensor.ostrom_aktueller_strompreis` als dynamische Preisentität!

---

## 📈 Kumulierter Verbrauch & Kosten mit dem Utility Meter (Verbrauchszähler)

Möchtest du deinen Stromverbrauch oder deine Stromkosten täglich, monatlich oder jährlich automatisch kumulieren lassen, nutze die Sensoren `sensor.ostrom_stundenverbrauch_vor_48h` bzw. `sensor.ostrom_stundenkosten_vor_48h` zusammen mit dem offiziellen Home Assistant **Utility Meter (Verbrauchszähler)** Helfer.

> [!TIP]
> **Warum Werte von vor 48 Stunden?**  
> Deutsche Smart-Meter-Gateways übermitteln Verbrauchsdaten oft mit 24 bis 36 Stunden Verzögerung. Während Daten von vor 24h daher noch unvollständig sein können, sind die Messwerte von **vor 48 Stunden** stets zu 100 % vollständig, final abgerechnet und verlässlich da. Auf den Monat oder das Jahr bezogen ist dieser 2-Tage-Versatz vernachlässigbar – die Gesamtsumme entspricht exakt deiner tatsächlichen Monatsabrechnung!

> [!IMPORTANT]
> Da `sensor.ostrom_stundenverbrauch_vor_48h` und `sensor.ostrom_stundenkosten_vor_48h` stündliche Werte (Deltas) liefern, aktiviere im Utility Meter unbedingt die Option **Delta-Werte** (`delta_values: true`).

### Einrichtung über die Benutzeroberfläche:
1. Gehe zu **Einstellungen** $\rightarrow$ **Geräte & Dienste** $\rightarrow$ **Helfer**.
2. Klicke auf **+ Helfer erstellen** und wähle **Verbrauchszähler** (Utility Meter).
3. **Eingabesensor:** `sensor.ostrom_stundenverbrauch_vor_48h` (für kWh) oder `sensor.ostrom_stundenkosten_vor_48h` (für €)
4. **Rücksetzzyklus:** `Täglich`, `Monatlich` oder `Jährlich`
5. **Delta-Werte:** Setze das Häkchen bei **„Werte stellen den Verbrauch seit der letzten Aktualisierung dar (Delta-Werte)“**!

### Oder via `configuration.yaml`:
```yaml
utility_meter:
  ostrom_verbrauch_monatlich:
    source: sensor.ostrom_stundenverbrauch_vor_48h
    cycle: monthly
    delta_values: true
    name: "Ostrom Verbrauch Monatlich"

  ostrom_stromkosten_monatlich:
    source: sensor.ostrom_stundenkosten_vor_48h
    cycle: monthly
    delta_values: true
    name: "Ostrom Stromkosten Monatlich"
```

---

## ⏰ Wichtiger Hinweis zu den „Morgen“-Sensoren

> [!NOTE]
> **Warum stehen die morgigen Sensoren vormittags auf „Unbekannt“?**
> Die EPEX Spot Strombörse versteigert den Strom für den nächsten Tag täglich um 12:00 Uhr mittags in der sogenannten **Day-Ahead-Auktion**.
> 
> Die offiziellen Preise für morgen werden täglich zwischen **13:00 und 14:00 Uhr** veröffentlicht. Vor diesem Zeitpunkt existieren die Preise schlichtweg noch nicht. Sobald die Daten nachmittags verfügbar sind, füllen sich alle Sensoren für morgen automatisch mit Werten!

---

## 📊 Dashboard-Visualisierung mit ApexCharts

Mit der beliebten [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (über HACS installierbar) erstellst du ein interaktives 48-Stunden-Balkendiagramm mit automatischer Farbcodierung:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Ostrom Strompreis (48h Vorschau)
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
    unit: ' €/kWh'
    float_precision: 4
    data_generator: |
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.start).getTime(), entry.price];
      });
    color_threshold:
      - value: 0.20
        color: '#2ecc71' # Sehr günstig (Grün)
      - value: 0.28
        color: '#f1c40f' # Normal (Gelb)
      - value: 0.35
        color: '#e67e22' # Teuer (Orange)
      - value: 0.40
        color: '#e74c3c' # Sehr teuer (Rot)
```

---

## 🤖 Praktische Automations-Beispiele

### 1. Waschmaschine / Spülmaschine zur günstigsten Uhrzeit starten
Starte einen Zwischenstecker genau zur günstigsten Stunde des Tages:

```yaml
alias: "Ostrom: Großverbraucher zur günstigsten Stunde starten"
description: "Aktiviert den Zwischenstecker, sobald die günstigste Uhrzeit heute erreicht ist."
trigger:
  - platform: template
    value_template: >
      {{ now().strftime('%H:%M') == states('sensor.ostrom_gunstigste_uhrzeit_heute') }}
condition: []
action:
  - service: switch.turn_on
    target:
      entity_id: switch.waschmaschine_steckdose
  - service: notify.persistent_notification
    data:
      title: "⚡ Günstigster Strompreis erreicht!"
      message: >
        Die günstigste Stunde hat begonnen! Aktueller Preis:
        {{ states('sensor.ostrom_aktueller_strompreis') }} €/kWh.
mode: single
```

---

### 2. E-Auto oder Heimspeicher in den TOP 3 günstigsten Stunden laden
Nutze den Sensor `sensor.ostrom_preis_rang_heute`, um Ladestationen oder Batteriespeicher gezielt in den 3 billigsten Stunden des Tages freizugeben:

```yaml
alias: "Ostrom: Wallbox in Top-3 Stunden aktivieren"
description: "Schaltet die Wallbox ein, wenn die Stunde zu den 3 günstigsten des Tages gehört."
trigger:
  - platform: state
    entity_id: sensor.ostrom_preis_rang_heute
condition:
  - condition: numeric_state
    entity_id: sensor.ostrom_preis_rang_heute
    below: 4 # Rang 1, 2 oder 3
action:
  - service: switch.turn_on
    target:
      entity_id: switch.wallbox_freigabe
mode: single
```

---

### 3. Spitzenpreis-Warnung: Wärmepumpe / Heimspeicher-Entladung steuern
Verhindere teuren Netzbezug, wenn der Strompreis in die Stufe `sehr_teuer` schlägt:

```yaml
alias: "Ostrom: Spitzenpreis-Schutz"
description: "Sendet Warnung und schaltet energieintensive Geräte ab, wenn Strom sehr teuer ist."
trigger:
  - platform: state
    entity_id: sensor.ostrom_preisstufe
    to: "sehr_teuer"
action:
  - service: notify.notify
    data:
      title: "⚠️ Hoher Strompreis!"
      message: >
        Achtung! Der Strompreis liegt aktuell bei {{ states('sensor.ostrom_aktueller_strompreis') }} €/kWh.
        Bitte keine Großverbraucher einschalten.
mode: single
```

---

### 4. Tägliche Push-Benachrichtigung um 14:00 Uhr mit morgigen Preisen
Erhalte jeden Nachmittag nach Veröffentlichung der Börsenpreise eine Zusammenfassung für morgen auf dein Smartphone:

```yaml
alias: "Ostrom: Preisvorschau für morgen um 14:00 Uhr"
trigger:
  - platform: time
    at: "14:00:00"
condition:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.ostrom_gunstigster_preis_morgen
        state: "unknown"
action:
  - service: notify.notify
    data:
      title: "⚡ Strompreis-Vorschau für morgen"
      message: >
        Günstigste Zeit: {{ states('sensor.ostrom_gunstigste_uhrzeit_morgen') }} Uhr ({{ states('sensor.ostrom_gunstigster_preis_morgen') }} €/kWh).
        Höchster Preis: {{ states('sensor.ostrom_hochster_preis_morgen') }} €/kWh um {{ states('sensor.ostrom_teuerste_uhrzeit_morgen') }} Uhr.
        Durchschnitt: {{ states('sensor.ostrom_durchschnittspreis_morgen') }} €/kWh.
```

---

## 🚀 Installation & Einrichtung

### Methode 1: Über HACS (Empfohlen)

1. Öffne **HACS** in Home Assistant.
2. Gehe auf **Integrationen** und klicke oben rechts auf das Dreipunkt-Menü ⋮ → **Benutzerdefinierte Repositories**.
3. Trage folgende URL ein:
   ```text
   https://github.com/KIDOPA/ha_ostrom
   ```
   Kategorie: **Integration**.
4. Klicke auf **Hinzufügen**, suche nach **Ostrom** und klicke auf **Herunterladen**.
5. Starte Home Assistant neu (*Entwicklerwerkzeuge → Neu starten*).

### Methode 2: Manuelle Installation

Kopiere den Ordner `custom_components/ostrom_custom` in das Verzeichnis `custom_components/` deiner Home Assistant Installation und starte Home Assistant neu.

---

## 🔑 Konfiguration

1. Gehe in Home Assistant zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen**.
2. Suche nach **Ostrom**.
3. Gib deine Daten ein:
   - **Client ID**: Erhältst du im [Ostrom Developer Portal](https://developers.ostrom.de/)
   - **Client Secret**: Dein API-Geheimnis
   - **Postleitzahl**: Deine Lieferadresse (zur exakten Ermittlung der Netzentgelte)
4. Klicke auf **Absenden**. Fertig!

---

## ❓ Häufige Fragen (FAQ)

<details>
<summary><b>Muss ich einen Ostrom Pulse oder Smart Meter besitzen?</b></summary>
Nein! Auch ohne Smart-Meter liefert die Ostrom API stündliche Börsen- und Arbeitspreise, Vorhersagen, Rang-Metriken und Grundgebühren für deine Postleitzahl. Lediglich die Sensoren für Live-Verbrauch und Verbrauchskosten bleiben ohne Smart Meter inaktiv.
</details>

<details>
<summary><b>Sind die angezeigten Preise Brutto oder Netto?</b></summary>
Alle Preise in dieser Integration sind <b>echte Brutto-Preise</b> inklusive 19% Mehrwertsteuer, aller gesetzlichen Steuern & Umlagen sowie der variablen Netzentgelte deines örtlichen Verteilnetzbetreibers.
</details>

<details>
<summary><b>Wie oft werden die Daten aktualisiert?</b></summary>
Die Integration aktualisiert sich vollautomatisch alle 30 Minuten und berechnet zur vollen Stunde die aktuellen Preis-Slots neu.
</details>

---

## ☕ Unterstütze dieses Projekt

Die Entwicklung und Pflege dieser Integration erfordert kontinuierliche Arbeit, Tests und Anpassungen an neue Home Assistant Versionen und API-Änderungen. 

Wenn dir diese Integration hilft, bares Geld bei deinen Stromkosten zu sparen oder deine Automationen zu optimieren, freue ich mich riesig über eine kleine Unterstützung auf einen Kaffee:

[![PayPal Spenden](https://img.shields.io/badge/PayPal-Spenden-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/kidopafotografie)

👉 **[Hier per PayPal spenden](https://paypal.me/kidopafotografie)**

---

### Lizenz & Haftungsausschluss

Dieses Projekt steht unter der [MIT Lizenz](LICENSE).  
*Hinweis: Dies ist eine inoffizielle Community-Integration und steht in keiner direkten geschäftlichen Verbindung zur Ostrom Energy GmbH.*

