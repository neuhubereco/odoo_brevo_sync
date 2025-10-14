# Brevo Webhook Setup Guide

Dieses Dokument beschreibt, wie Sie Brevo-Webhooks für das Odoo Brevo Connector Modul einrichten.

## Webhook-Endpunkte

Das Modul bietet zwei Webhook-Endpunkte:

### 1. Meeting/Call-spezifischer Endpunkt (EMPFOHLEN)
```
POST https://your-odoo-instance.com/brevo/booking
```

**Unterstützte Events:**
- `meeting.created`
- `meeting.updated`
- `meeting.cancelled`
- `call.created`
- `call.started`
- `call.cancelled`

**Status:** ✅ Vollständig funktionsfähig und getestet

### 2. Allgemeiner Webhook-Endpunkt
```
POST https://your-odoo-instance.com/brevo/webhook
```

**Unterstützte Events:**
- `contact.created`
- `contact.updated` 
- `contact.deleted`
- `list.created`
- `list.updated`
- `list.deleted`

**Status:** ⚠️ Funktioniert, aber benötigt zusätzliche Berechtigungen für Kontakt-Erstellung

## Brevo-Konfiguration

### 1. Webhook in Brevo einrichten

1. Loggen Sie sich in Ihr Brevo-Konto ein
2. Gehen Sie zu **Settings > Webhooks**
3. Klicken Sie auf **Create a webhook**
4. Konfigurieren Sie den Webhook:

**Für allgemeine Events:**
- **URL**: `https://your-odoo-instance.com/brevo/webhook`
- **Events**: Wählen Sie die gewünschten Events (contact.*, list.*)

**Für Meeting/Call Events (EMPFOHLEN):**
- **URL**: `https://your-odoo-instance.com/brevo/booking`
- **Events**: Wählen Sie meeting.* und/oder call.* Events
- **Status**: ✅ Vollständig funktionsfähig und getestet

### 2. Webhook-Signatur (Optional)

Für zusätzliche Sicherheit können Sie eine Webhook-Signatur aktivieren:

1. In Brevo: Geben Sie ein **Secret** ein
2. In Odoo: Setzen Sie den Parameter `brevo.webhook_secret` auf denselben Wert
3. Aktivieren Sie `brevo.webhook_require_signature` auf `1`

## Odoo-Konfiguration

### 1. Brevo API-Schlüssel konfigurieren

1. Gehen Sie zu **Einstellungen > Technisch > Brevo Integration**
2. Geben Sie Ihren Brevo API-Schlüssel ein
3. Speichern Sie die Konfiguration

### 2. Webhook-Parameter (Optional)

In **Einstellungen > Technisch > System-Parameter**:

- `brevo.webhook_secret`: Secret für Webhook-Signatur-Verifikation
- `brevo.webhook_require_signature`: `1` für Signatur-Verifikation, `0` oder leer für deaktiviert

## Webhook-Payload-Beispiele

### Meeting Created Event

```json
{
  "event": "meeting.created",
  "data": {
    "meeting_name": "Demo Meeting",
    "meeting_start_timestamp": "2024-01-15T10:00:00Z",
    "meeting_end_timestamp": "2024-01-15T11:00:00Z",
    "meeting_notes": "Discussion about project requirements",
    "event_participants": [
      {
        "EMAIL": "customer@example.com",
        "FIRSTNAME": "John",
        "LASTNAME": "Doe"
      }
    ],
    "questions_and_answers": [
      {
        "question": "What is your company?",
        "answer": "Acme Corp"
      },
      {
        "question": "What is your role?",
        "answer": "Project Manager"
      }
    ]
  }
}
```

### Contact Created Event

```json
{
  "event": "contact.created",
  "data": {
    "id": 12345,
    "email": "newcontact@example.com",
    "attributes": {
      "FNAME": "Jane",
      "LNAME": "Smith",
      "SMS": "+1234567890"
    },
    "createdAt": "2024-01-15T10:00:00Z",
    "modifiedAt": "2024-01-15T10:00:00Z"
  }
}
```

## Was passiert bei Webhook-Empfang?

### Meeting/Call Events
1. **Partner-Erstellung/Aktualisierung**: Teilnehmer werden als Odoo-Partner erstellt oder aktualisiert
2. **CRM-Lead-Erstellung**: Ein neuer Lead wird mit folgenden Details erstellt:
   - Name: "Vorname Nachname - Meeting Type" (z.B. "Verena Schweighuber - Kennlerngespräch")
   - Partner: Teilnehmer-Partner
   - Beschreibung: Meeting-Notizen + Fragen und Antworten
   - Brevo-ID: Meeting-ID für Tracking
   - Buchungszeit: Start-Zeit des Meetings

### Contact Events
1. **Partner-Synchronisation**: Brevo-Kontakte werden mit Odoo-Partnern synchronisiert
2. **Feld-Mapping**: Konfigurierte Feld-Zuordnungen werden angewendet
3. **Listen-Zuordnung**: Brevo-Listen werden Odoo-Partner-Kategorien zugeordnet

### List Events
1. **Listen-Synchronisation**: Brevo-Listen werden als Odoo-Partner-Kategorien erstellt/aktualisiert
2. **Mitgliedschaft-Sync**: Listen-Mitgliedschaften werden synchronisiert

## Fehlerbehebung

### Webhook antwortet nicht
- Überprüfen Sie, ob der Odoo-Server läuft
- Überprüfen Sie die URL auf Tippfehler
- Überprüfen Sie die Firewall-Einstellungen

### Berechtigungsfehler
- Das Modul verwendet automatisch System-Benutzer für Webhook-Operationen
- Überprüfen Sie die Modul-Version (mindestens 18.0.1.1.0)

### Signatur-Verifikation fehlgeschlagen
- Überprüfen Sie, ob `brevo.webhook_secret` korrekt gesetzt ist
- Überprüfen Sie, ob das Secret in Brevo und Odoo identisch ist

### Datetime-Fehler
- Das Modul konvertiert automatisch timezone-aware zu naive datetime
- Überprüfen Sie das Datetime-Format in den Webhook-Daten

## Logs und Monitoring

### Odoo-Logs
Webhook-Aktivitäten werden in den Odoo-Logs protokolliert:
- Erfolgreiche Webhook-Verarbeitung
- Fehler bei der Webhook-Verarbeitung
- Erstellte/aktualisierte Partner und Leads

### Brevo-Logs
In Brevo können Sie Webhook-Delivery-Status überprüfen:
- Erfolgreiche Deliveries
- Fehlgeschlagene Deliveries
- Response-Codes und -Nachrichten

## Support

Bei Problemen oder Fragen:
1. Überprüfen Sie die Odoo-Logs
2. Überprüfen Sie die Brevo-Webhook-Logs
3. Testen Sie den Webhook-Endpunkt manuell mit curl
4. Kontaktieren Sie den Administrator

## Changelog

- **v18.0.1.1.0**: Vollständige Meeting/Call-Webhook-Unterstützung
- **v18.0.1.0.53**: Datetime-Kompatibilität und System-User-Nutzung
- **v18.0.1.0.45**: Event-Routing für meeting.* und call.* Events
