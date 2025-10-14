# -*- coding: utf-8 -*-
{
    'name': 'Brevo Connector',
            'version': '18.0.1.0.28',
    'category': 'CRM',
    'summary': 'Bidirectional synchronization between Odoo and Brevo (Sendinblue)',
    'description': """
Brevo Connector Module
=====================

This module provides bidirectional synchronization between Odoo and Brevo (formerly Sendinblue):

* **Contact Synchronization**: Sync Odoo res.partner records with Brevo contacts
* **List Synchronization**: Map Odoo partner categories to Brevo contact lists
* **CRM Lead Creation**: Automatically create CRM leads from Brevo bookings/appointments
* **Webhook Support**: Real-time updates via webhooks
* **Configurable Sync**: Customizable sync intervals and field mappings

Features:
---------
- Bidirectional contact sync (name, email, phone, address)
- Partner category to Brevo list mapping
- Automatic CRM lead creation from Brevo bookings
- Webhook endpoints for real-time updates
- Configurable sync intervals
- Error logging and status dashboard
- Batch processing for large datasets
- Rate limit compliance

Technical Details:
------------------
- Uses Brevo API v3 with official Python SDK
- Secure API key storage in Odoo config parameters
- Cron jobs for periodic synchronization
- Real-time triggers for Odoo-to-Brevo sync
- Webhook endpoints for Brevo-to-Odoo sync
- Configurable field mappings
- Comprehensive error handling and logging
    """,
    'author': 'Florian Neuhuber',
    'website': 'https://www.neuhuber.group',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'contacts',
        'crm',
        'mail',
    ],
    'external_dependencies': {
        'python': ['brevo-python'],
    },
            'data': [
                'security/ir.model.access.csv',
                'security/brevo_security.xml',
                'data/ir_cron_data.xml',
                'data/ir_config_parameter_data.xml',
                'views/brevo_config_views.xml',
                'views/res_partner_views.xml',
                'views/brevo_sync_log_views.xml',
                'views/brevo_field_mapping_views.xml',
                'wizards/brevo_config_wizard_views.xml',
                'wizards/brevo_delete_confirmation_wizard_views.xml',
                'views/brevo_menu.xml',
            ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
