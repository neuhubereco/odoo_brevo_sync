# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [18.0.1.1.0] - 2024-10-14

### Hinzugefügt
- **Webhook-Endpunkt `/brevo/booking`** für Meeting/Call-Integration
- **Meeting-Event-Unterstützung** (`meeting.created`, `meeting.updated`, `meeting.cancelled`)
- **Call-Event-Unterstützung** (`call.created`, `call.started`, `call.cancelled`)
- **Event-Normalisierung** von `meeting.*` zu `booking.*` Events
- **Participant-Daten-Verarbeitung** aus `event_participants` Array
- **Fragen-und-Antworten-Integration** in CRM-Lead-Beschreibung
- **System-User-Nutzung** für Webhook-Operationen (bypass Berechtigungen)
- **Naive-Datetime-Konvertierung** für Odoo-Kompatibilität

### Geändert
- **Webhook-Controller** erweitert um Meeting/Call-Handler
- **CRM-Lead-Erstellung** optimiert für Webhook-Kontext
- **Partner-Erstellung** mit System-User für öffentliche Webhooks
- **Logging-System** angepasst für öffentliche Benutzer

### Behoben
- **Berechtigungsprobleme** bei Webhook-Operationen gelöst
- **Datetime-Feld-Kompatibilität** mit Odoo-Standards
- **Event-Routing** für verschiedene Brevo-Event-Typen
- **Partner-Erstellung** aus Webhook-Daten

### Technische Details
- Webhook-Endpunkte: `/brevo/webhook` (allgemein), `/brevo/booking` (Meeting/Call-spezifisch)
- Unterstützte Events: `meeting.*`, `call.*`, `contact.*`, `list.*`
- System-User: `base.user_root` für Webhook-Operationen
- Datetime-Handling: Konvertierung von timezone-aware zu naive datetime

## [18.0.1.0.53] - 2024-10-14

### Behoben
- Datetime-Feld-Kompatibilität für Odoo
- System-User-Nutzung für CRM-Lead-Erstellung
- Berechtigungsprobleme bei Partner-Erstellung

## [18.0.1.0.52] - 2024-10-14

### Geändert
- System-User (`base.user_root`) für Lead- und Partner-Erstellung
- Vereinfachte Lead-Erstellung für öffentliche Benutzer

## [18.0.1.0.51] - 2024-10-14

### Geändert
- `sudo()` für CRM-Lead- und Partner-Erstellung
- Vereinfachte Lead-Erstellung (entfernte problematische Felder)

## [18.0.1.0.50] - 2024-10-14

### Geändert
- Vereinfachte CRM-Lead-Erstellung für öffentliche Benutzer
- Entfernte `stage_id` und `phone` Felder

## [18.0.1.0.49] - 2024-10-14

### Geändert
- CRM-Lead-Erstellung-Logging für öffentliche Benutzer deaktiviert
- Standard-Python-Logging statt `brevo.sync.log`

## [18.0.1.0.48] - 2024-10-14

### Geändert
- Webhook-Logging für öffentliche Benutzer deaktiviert
- Standard-Python-Logging statt Datenbank-Logging

## [18.0.1.0.47] - 2024-10-14

### Geändert
- Webhook-Logging-Berechtigungen mit try-catch behandelt
- Webhook-Verarbeitung setzt fort auch wenn Logging fehlschlägt

## [18.0.1.0.46] - 2024-10-14

### Hinzugefügt
- Öffentliche Berechtigungen für `brevo.sync.log`, `res.partner`, `crm.lead`
- Berechtigungen für `brevo.delete.confirmation.wizard`

## [18.0.1.0.45] - 2024-10-14

### Geändert
- Webhook-Event-Routing für `meeting.*` und `call.*` Events
- Event-Normalisierung in `_handle_booking_webhook`

## Frühere Versionen
- Kontakt-Synchronisation
- Listen-Synchronisation  
- Feld-Mapping-System
- Konfigurations-Wizard
- Cron-Jobs für automatische Synchronisation
