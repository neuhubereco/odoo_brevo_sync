# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class BrevoConfigWizard(models.TransientModel):
    """Wizard for Brevo configuration setup"""
    _name = 'brevo.config.wizard'
    _description = 'Brevo Configuration Wizard'

    # API Configuration
    api_key = fields.Char(
        string='Brevo API Key',
        required=True,
        help='Your Brevo API key for authentication'
    )
    
    # Sync Configuration
    sync_interval = fields.Integer(
        string='Sync Interval (minutes)',
        default=15,
        help='How often to synchronize data with Brevo (in minutes)'
    )
    
    batch_size = fields.Integer(
        string='Batch Size',
        default=100,
        help='Number of records to process in each batch'
    )
    
    # Webhook Configuration
    webhooks_enabled = fields.Boolean(
        string='Enable Webhooks',
        default=True,
        help='Enable real-time webhook updates from Brevo'
    )
    
    webhook_secret = fields.Char(
        string='Webhook Secret',
        help='Secret key for webhook signature verification'
    )
    
    # Field Mapping Configuration
    field_mappings = fields.Text(
        string='Field Mappings',
        default='{}',
        help='JSON configuration for field mappings between Odoo and Brevo'
    )
    
    # Test Results
    connection_test_result = fields.Text(
        string='Connection Test Result',
        readonly=True,
        help='Result of the connection test'
    )
    
    connection_success = fields.Boolean(
        string='Connection Successful',
        readonly=True,
        help='Whether the connection test was successful'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from existing configuration"""
        defaults = super().default_get(fields_list)
        
        # Get existing configuration
        config = self.env['brevo.config'].get_active_config()
        if config:
            defaults.update({
                'api_key': config.api_key,
                'sync_interval': config.sync_interval,
                'batch_size': config.batch_size,
                'webhooks_enabled': config.webhooks_enabled,
                'field_mappings': config.field_mappings,
            })
            
            # Get webhook secret from config parameters
            webhook_secret = self.env['ir.config_parameter'].sudo().get_param('brevo.webhook_secret')
            if webhook_secret:
                defaults['webhook_secret'] = webhook_secret
        
        return defaults

    @api.constrains('sync_interval')
    def _check_sync_interval(self):
        """Validate sync interval is reasonable"""
        for record in self:
            if record.sync_interval < 1:
                raise ValidationError(_('Sync interval must be at least 1 minute'))
            if record.sync_interval > 1440:  # 24 hours
                raise ValidationError(_('Sync interval cannot exceed 24 hours'))

    @api.constrains('batch_size')
    def _check_batch_size(self):
        """Validate batch size is reasonable"""
        for record in self:
            if record.batch_size < 1:
                raise ValidationError(_('Batch size must be at least 1'))
            if record.batch_size > 1000:
                raise ValidationError(_('Batch size cannot exceed 1000'))

    def test_connection(self):
        """Test the Brevo API connection"""
        try:
            from ..services.brevo_service import BrevoService
            service = BrevoService(self.api_key)
            result = service.test_connection()
            
            if result.get('success'):
                self.connection_success = True
                self.connection_test_result = f"""Connection Successful!

Account Email: {result.get('account_email', 'N/A')}
Plan: {result.get('plan', 'N/A')}
Credits Remaining: {result.get('credits', 'N/A')}

The connection to Brevo API is working correctly."""
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to Brevo API'),
                        'type': 'success',
                    }
                }
            else:
                self.connection_success = False
                self.connection_test_result = f"""Connection Failed!

Error: {result.get('error', 'Unknown error')}

Please check your API key and try again."""
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': result.get('error', 'Unknown error'),
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.error(f"Brevo connection test failed: {str(e)}")
            self.connection_success = False
            self.connection_test_result = f"""Connection Failed!

Error: {str(e)}

Please check your API key and try again."""
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def setup_webhooks(self):
        """Set up webhooks in Brevo"""
        try:
            if not self.connection_success:
                raise UserError(_('Please test the connection first before setting up webhooks'))
            
            from ..services.brevo_service import BrevoService
            service = BrevoService(self.api_key)
            
            # Get webhook URL
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if not base_url:
                raise UserError(_('Base URL not configured. Please set web.base.url parameter.'))
            
            webhook_url = f"{base_url}/brevo/webhook"
            
            # Define webhook events
            webhook_events = [
                'contact.created',
                'contact.updated',
                'contact.deleted',
                'list.created',
                'list.updated',
                'list.deleted',
                'booking.created',
                'booking.updated',
                'booking.cancelled',
            ]
            
            # Create webhook
            webhook_data = {
                'url': webhook_url,
                'description': 'Odoo Brevo Connector Webhook',
                'events': webhook_events,
                'type': 'transactional',
            }
            
            result = service.create_webhook(webhook_data)
            
            if result.get('success'):
                # Store webhook secret if provided
                if self.webhook_secret:
                    self.env['ir.config_parameter'].sudo().set_param('brevo.webhook_secret', self.webhook_secret)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Webhook Setup Successful'),
                        'message': _('Webhook has been created in Brevo successfully'),
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Webhook Setup Failed'),
                        'message': result.get('error', 'Unknown error'),
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.error(f"Webhook setup failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Webhook Setup Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def apply_configuration(self):
        """Apply the configuration settings"""
        try:
            # Get or create configuration
            config = self.env['brevo.config'].get_active_config()
            
            if config:
                # Update existing configuration
                config.write({
                    'api_key': self.api_key,
                    'sync_interval': self.sync_interval,
                    'batch_size': self.batch_size,
                    'webhooks_enabled': self.webhooks_enabled,
                    'field_mappings': self.field_mappings,
                })
            else:
                # Create new configuration
                config = self.env['brevo.config'].create({
                    'name': 'Default Brevo Configuration',
                    'api_key': self.api_key,
                    'sync_interval': self.sync_interval,
                    'batch_size': self.batch_size,
                    'webhooks_enabled': self.webhooks_enabled,
                    'field_mappings': self.field_mappings,
                    'company_id': self.env.company.id,
                })
            
            # Store webhook secret if provided
            if self.webhook_secret:
                self.env['ir.config_parameter'].sudo().set_param('brevo.webhook_secret', self.webhook_secret)
            
            # Update cron job interval
            cron_job = self.env['ir.cron'].search([
                ('name', '=', 'Brevo Contact Sync'),
                ('model_id.model', '=', 'brevo.config')
            ], limit=1)
            
            if cron_job:
                cron_job.write({
                    'interval_number': self.sync_interval,
                    'interval_type': 'minutes',
                })
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Brevo Configuration'),
                'res_model': 'brevo.config',
                'res_id': config.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            _logger.error(f"Configuration application failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def manual_sync_contacts(self):
        """Trigger manual synchronization of contacts"""
        try:
            if not self.connection_success:
                raise UserError(_('Please test the connection first before running sync'))
            
            # Apply configuration first
            self.apply_configuration()
            
            # Get the configuration
            config = self.env['brevo.config'].get_active_config()
            if not config:
                raise UserError(_('No active Brevo configuration found'))
            
            # Run sync
            result = config.manual_sync_contacts()
            return result
            
        except Exception as e:
            _logger.error(f"Manual contact sync failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def manual_sync_lists(self):
        """Trigger manual synchronization of contact lists"""
        try:
            if not self.connection_success:
                raise UserError(_('Please test the connection first before running sync'))
            
            # Apply configuration first
            self.apply_configuration()
            
            # Get the configuration
            config = self.env['brevo.config'].get_active_config()
            if not config:
                raise UserError(_('No active Brevo configuration found'))
            
            # Run sync
            result = config.manual_sync_lists()
            return result
            
        except Exception as e:
            _logger.error(f"Manual lists sync failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def get_field_mapping_help(self):
        """Get help text for field mappings"""
        help_text = """Field Mappings Configuration

This JSON configuration defines how Odoo fields map to Brevo contact attributes.

Example configuration:
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

Available Brevo attributes:
- FNAME: First name
- LNAME: Last name
- SMS: Mobile phone
- ADDRESS: Street address
- CITY: City
- STATE: State/Province
- ZIP: Postal code
- COUNTRY: Country
- COMPANY: Company name

Options:
- split: Split name field into first and last name
- use_name: Use the name field instead of ID
- first_name_field: Field for first name when splitting
- last_name_field: Field for last name when splitting"""
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Field Mapping Help'),
                'message': help_text,
                'type': 'info',
            }
        }
