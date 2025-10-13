# Brevo Connector - Odoo Module

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-green.svg)](https://www.odoo.com)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)

## 📋 Overview

This Odoo module provides **bidirectional synchronization** between Odoo and Brevo (formerly Sendinblue) API v3. It enables seamless integration of contact management, list synchronization, and CRM lead creation from Brevo bookings.

## ✨ Key Features

### 🔄 Contact Synchronization
- **Bidirectional sync**: Sync Odoo res.partner records with Brevo contacts
- **Field mapping**: Configurable mapping between Odoo and Brevo fields
- **Conflict resolution**: Timestamp-based conflict resolution (last modified wins)
- **Batch processing**: Handle large datasets with configurable batch sizes

### 📋 List Synchronization
- **Category mapping**: Map Odoo partner categories to Brevo contact lists
- **Membership sync**: Synchronize contact list memberships in both directions
- **Automatic creation**: Create Brevo lists from Odoo partner categories

### 🎯 CRM Lead Creation
- **Booking integration**: Automatically create CRM leads from Brevo bookings
- **Webhook support**: Real-time lead creation via webhooks
- **Data extraction**: Pull contact info, booking time, and notes

### ⚙️ Configuration & Monitoring
- **Setup wizard**: Easy configuration through a guided wizard
- **Connection testing**: Test Brevo API connectivity
- **Sync monitoring**: Comprehensive logging and status dashboard
- **Error handling**: Detailed error logging and recovery

## 🚀 Installation

### Prerequisites
- Odoo 18.0 Community Edition
- Python 3.8+
- Brevo API key

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Install Module
1. Copy the module to your Odoo addons directory
2. Update the addons list in Odoo
3. Install the module from the Apps menu

### Step 3: Configure Brevo
1. Go to **Settings > Technical > Brevo Integration**
2. Run the **Setup Wizard**
3. Enter your Brevo API key
4. Test the connection
5. Configure webhooks (optional)

## 🔧 Configuration

### API Setup
1. Get your Brevo API key from your [Brevo account](https://app.brevo.com/)
2. Navigate to **Settings > API Keys** in Brevo
3. Create a new API key with appropriate permissions

### Webhook Configuration
1. Enable webhooks in the configuration wizard
2. Copy the webhook URL provided
3. In Brevo, go to **Settings > Webhooks**
4. Create a new webhook with the URL
5. Select the following events:
   - `contact.created`
   - `contact.updated`
   - `contact.deleted`
   - `list.created`
   - `list.updated`
   - `list.deleted`
   - `booking.created`
   - `booking.updated`
   - `booking.cancelled`

### Field Mapping
Configure field mappings in JSON format:
```json
{
    "name": {
        "brevo_attribute": "FNAME",
        "split": true,
        "first_name_field": "FNAME",
        "last_name_field": "LNAME"
    },
    "mobile": {
        "brevo_attribute": "SMS"
    },
    "street": {
        "brevo_attribute": "ADDRESS"
    },
    "city": {
        "brevo_attribute": "CITY"
    },
    "zip": {
        "brevo_attribute": "ZIP"
    },
    "country_id": {
        "brevo_attribute": "COUNTRY",
        "use_name": true
    },
    "state_id": {
        "brevo_attribute": "STATE",
        "use_name": true
    },
    "parent_id": {
        "brevo_attribute": "COMPANY",
        "use_name": true
    }
}
```

## 📖 Usage

### Manual Synchronization
- **Contacts**: Use the "Sync Contacts" button in the configuration
- **Lists**: Use the "Sync Lists" button in the configuration
- **Individual records**: Use the "Sync to Brevo" button on partner/lead forms

### Automatic Synchronization
- **Cron jobs**: Automatic sync every 15 minutes (configurable)
- **Real-time**: Webhook-based real-time updates
- **Batch processing**: Configurable batch sizes for large datasets

### Monitoring
- **Dashboard**: View sync status and statistics
- **Logs**: Detailed sync logs with error tracking
- **Status indicators**: Visual status indicators on records

## 🛠️ Technical Details

### API Rate Limits
- Respects Brevo API rate limits (300 calls/minute)
- Implements automatic rate limiting
- Batch processing for large datasets

### Error Handling
- Comprehensive error logging
- Graceful failure handling
- Retry mechanisms for transient errors

### Security
- Secure API key storage
- Webhook signature verification
- Multi-company support
- Access control and permissions

## 🔍 Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify API key is correct
   - Check network connectivity
   - Ensure API key has required permissions

2. **Sync Errors**
   - Check sync logs for detailed error messages
   - Verify field mappings are correct
   - Ensure required fields are present

3. **Webhook Issues**
   - Verify webhook URL is accessible
   - Check webhook secret configuration
   - Ensure webhook events are properly configured

### Logs
- View sync logs in **Brevo Integration > Monitoring > Sync Logs**
- Check Odoo logs for detailed error information
- Use the dashboard for quick status overview

## 📁 Module Structure

```
brevo_connector/
├── __manifest__.py              # Module manifest
├── __init__.py                  # Main initialization
├── models/                      # Data models
│   ├── __init__.py
│   ├── brevo_config.py          # Configuration model
│   ├── res_partner.py           # Partner extension
│   ├── brevo_contact_list.py    # Contact list model
│   ├── brevo_sync_log.py        # Sync logs
│   └── crm_lead.py              # CRM lead extension
├── services/                    # API services
│   ├── __init__.py
│   ├── brevo_service.py         # Brevo API service
│   └── brevo_sync_service.py    # Sync service
├── controllers/                 # Webhook controllers
│   ├── __init__.py
│   └── brevo_webhook.py         # Webhook handler
├── wizards/                     # Configuration wizards
│   ├── __init__.py
│   └── brevo_config_wizard.py  # Setup wizard
├── views/                       # User interfaces
│   ├── brevo_config_views.xml   # Configuration views
│   ├── res_partner_views.xml    # Partner views
│   ├── brevo_sync_log_views.xml # Log views
│   ├── brevo_menu.xml           # Menu structure
│   └── brevo_config_wizard_views.xml # Wizard views
├── data/                        # Default data
│   ├── ir_cron_data.xml         # Cron jobs
│   └── ir_config_parameter_data.xml # Configuration parameters
├── security/                    # Security policies
│   ├── ir.model.access.csv      # Access rights
│   └── brevo_security.xml       # Security groups
├── static/description/          # Module description
│   └── index.html               # HTML description
├── requirements.txt             # Python dependencies
└── README.md                    # Documentation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues and questions:
1. Check the sync logs for error details
2. Review the configuration settings
3. Test the API connection
4. Consult the [Brevo API documentation](https://developers.brevo.com/)

## 📝 Changelog

### Version 18.0.1.0.0
- Initial release
- Contact synchronization
- List synchronization
- CRM lead creation
- Webhook support
- Configuration wizard
- Comprehensive logging

## 🙏 Acknowledgments

- [Brevo](https://www.brevo.com/) for their excellent API
- [Odoo](https://www.odoo.com/) for the amazing platform
- The open-source community for inspiration and support

---

**Made with ❤️ for the Odoo community**