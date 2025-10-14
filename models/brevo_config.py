# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class BrevoConfig(models.Model):
    """Configuration model for Brevo integration settings"""
    _name = 'brevo.config'
    _description = 'Brevo Configuration'
    _rec_name = 'name'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='Default Brevo Configuration'
    )
    
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
    
    webhooks_enabled = fields.Boolean(
        string='Enable Webhooks',
        default=True,
        help='Enable real-time webhook updates from Brevo'
    )
    
    webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url',
        help='URL to configure in Brevo for webhook notifications'
    )
    
    # Field Mapping Configuration
    field_mappings = fields.Text(
        string='Field Mappings',
        default='{}',
        help='JSON configuration for field mappings between Odoo and Brevo'
    )
    
    # Status Information
    last_sync_contacts = fields.Datetime(
        string='Last Contacts Sync',
        help='Last time contacts were synchronized'
    )
    
    last_sync_lists = fields.Datetime(
        string='Last Lists Sync',
        help='Last time contact lists were synchronized'
    )
    
    sync_status = fields.Selection([
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('error', 'Error'),
        ('success', 'Success')
    ], string='Sync Status', default='idle')
    
    error_message = fields.Text(
        string='Last Error Message',
        help='Last error message from synchronization'
    )
    
    # Company restriction
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this configuration is active'
    )

    @api.depends('webhooks_enabled')
    def _compute_webhook_url(self):
        """Compute the webhook URL for Brevo configuration"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.webhooks_enabled and base_url:
                record.webhook_url = f"{base_url}/brevo/webhook"
            else:
                record.webhook_url = False

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

    @api.model
    def get_active_config(self):
        """Get the active configuration for the current company"""
        return self.search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    def test_connection(self):
        """Test the Brevo API connection"""
        try:
            from ..services.brevo_service import BrevoService
            service = BrevoService(self.api_key)
            result = service.test_connection()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.error_message = False
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
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
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
            self.sync_status = 'error'
            self.error_message = str(e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def discover_fields(self):
        """Discover available fields from Brevo and Odoo"""
        try:
            if not self.api_key:
                raise UserError(_('Please provide a Brevo API Key'))

            from ..services.brevo_service import BrevoService
            service = BrevoService(self.api_key)
            result = service.get_all_contact_attributes()

            if not result.get('success'):
                raise UserError(_('Failed to get Brevo fields: %s') % result.get('error', 'Unknown error'))

            # Get Odoo partner fields
            odoo_fields = []
            partner_model = self.env['res.partner']
            for field_name, field_obj in partner_model._fields.items():
                if field_obj.type in ['char', 'text', 'integer', 'float', 'boolean', 'date', 'datetime', 'selection', 'many2one', 'many2many']:
                    odoo_fields.append({
                        'name': field_name,
                        'type': field_obj.type,
                        'string': field_obj.string,
                    })

            # Clear existing discovery records for this company
            self.env['brevo.field.discovery'].search([
                ('company_id', '=', self.company_id.id)
            ]).unlink()

            # Create discovery records for all Brevo attributes
            discovery_count = 0
            for brevo_attr in result.get('attributes', []):
                brevo_name = brevo_attr['name']
                
                # Create discovery record for each Brevo field
                self.env['brevo.field.discovery'].create({
                    'brevo_field_name': brevo_name,
                    'brevo_field_type': brevo_attr.get('type', ''),
                    'brevo_field_category': brevo_attr.get('category', ''),
                    'company_id': self.company_id.id,
                })
                discovery_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Field Discovery Complete'),
                    'message': _('Discovered %d field combinations') % discovery_count,
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Field discovery failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Field Discovery Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_open_field_discovery(self):
        """Open Field Discovery window"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Field Discovery',
            'res_model': 'brevo.field.discovery',
            'view_mode': 'list,form',
            'target': 'current',
            'context': {'search_default_unmapped': 1}
        }

    def manual_sync_contacts(self):
        """Trigger manual synchronization of contacts"""
        try:
            self.sync_status = 'syncing'
            self.error_message = False
            
            from ..services.brevo_sync_service import BrevoSyncService
            sync_service = BrevoSyncService(self)
            result = sync_service.sync_contacts()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.last_sync_contacts = fields.Datetime.now()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Successful'),
                        'message': _('Contacts synchronized successfully'),
                        'type': 'success',
                    }
                }
            else:
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Failed'),
                        'message': result.get('error', 'Unknown error'),
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.error(f"Manual contact sync failed: {str(e)}")
            self.sync_status = 'error'
            self.error_message = str(e)
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
            self.sync_status = 'syncing'
            self.error_message = False
            
            from ..services.brevo_sync_service import BrevoSyncService
            sync_service = BrevoSyncService(self)
            result = sync_service.sync_lists()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.last_sync_lists = fields.Datetime.now()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Successful'),
                        'message': _('Contact lists synchronized successfully'),
                        'type': 'success',
                    }
                }
            else:
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Failed'),
                        'message': result.get('error', 'Unknown error'),
                        'type': 'danger',
                    }
                }
        except Exception as e:
            _logger.error(f"Manual lists sync failed: {str(e)}")
            self.sync_status = 'error'
            self.error_message = str(e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_sync_contacts(self):
        """Method for cron job to sync contacts"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            sync_service = BrevoSyncService(self)
            result = sync_service.sync_contacts()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.error_message = False
            else:
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
        except Exception as e:
            _logger.error(f"Brevo contact sync cron failed for config {self.id}: {str(e)}")
            self.sync_status = 'error'
            self.error_message = str(e)

    def action_sync_lists(self):
        """Method for cron job to sync lists"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            sync_service = BrevoSyncService(self)
            result = sync_service.sync_lists()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.error_message = False
            else:
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
        except Exception as e:
            _logger.error(f"Brevo list sync cron failed for config {self.id}: {str(e)}")
            self.sync_status = 'error'
            self.error_message = str(e)

    def action_sync_tags(self):
        """Method for cron job to sync tags"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            sync_service = BrevoSyncService(self)
            result = sync_service.sync_tags()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.error_message = False
            else:
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
        except Exception as e:
            _logger.error(f"Brevo tag sync cron failed for config {self.id}: {str(e)}")
            self.sync_status = 'error'
            self.error_message = str(e)

    def action_sync_dynamic_fields(self):
        """Method for cron job to sync dynamic fields"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            sync_service = BrevoSyncService(self)
            result = sync_service.sync_dynamic_fields()
            
            if result.get('success'):
                self.sync_status = 'success'
                self.error_message = False
            else:
                self.sync_status = 'error'
                self.error_message = result.get('error', 'Unknown error')
        except Exception as e:
            _logger.error(f"Brevo dynamic fields sync cron failed for config {self.id}: {str(e)}")
            self.sync_status = 'error'
            self.error_message = str(e)
