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

    def create_all_brevo_fields(self):
        """Create all Brevo fields manually if discover_fields didn't work"""
        try:
            from ..services.brevo_service import BrevoService
            service = BrevoService(self.api_key or 'dummy')
            result = service.get_all_contact_attributes()

            if not result.get('success'):
                raise UserError(_('Failed to get Brevo fields: %s') % result.get('error', 'Unknown error'))

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
                    'title': _('All Brevo Fields Created'),
                    'message': _('Created %d Brevo field discovery records') % discovery_count,
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed to create all Brevo fields: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def create_predefined_mappings(self):
        """Create predefined field mappings based on the provided mapping list"""
        try:
            # Predefined mappings from user's specification
            predefined_mappings = {
                'FNAME': {'odoo_field': 'firstname', 'type': 'char'},
                'LNAME': {'odoo_field': 'lastname', 'type': 'char'},
                'BIRTHDAY': {'odoo_field': 'date', 'type': 'date'},
                'AGE': {'odoo_field': 'x_brevo_age', 'type': 'integer'},
                'GENDER': {'odoo_field': 'x_brevo_gender', 'type': 'selection'},
                'TITLE': {'odoo_field': 'title', 'type': 'many2one'},
                'FIRSTNAME': {'odoo_field': 'firstname', 'type': 'char'},
                'LASTNAME': {'odoo_field': 'lastname', 'type': 'char'},
                'MIDDLENAME': {'odoo_field': 'x_brevo_middlename', 'type': 'char'},
                'NICKNAME': {'odoo_field': 'x_brevo_nickname', 'type': 'char'},
                'EMAIL': {'odoo_field': 'email', 'type': 'char'},
                'SMS': {'odoo_field': 'phone', 'type': 'char'},
                'PHONE': {'odoo_field': 'phone', 'type': 'char'},
                'MOBILE': {'odoo_field': 'mobile', 'type': 'char'},
                'FAX': {'odoo_field': 'x_brevo_fax', 'type': 'char'},
                'WEBSITE': {'odoo_field': 'website', 'type': 'char'},
                'SKYPE': {'odoo_field': 'x_brevo_skype', 'type': 'char'},
                'LINKEDIN': {'odoo_field': 'x_brevo_linkedin', 'type': 'char'},
                'TWITTER': {'odoo_field': 'x_brevo_twitter', 'type': 'char'},
                'FACEBOOK': {'odoo_field': 'x_brevo_facebook', 'type': 'char'},
                'INSTAGRAM': {'odoo_field': 'x_brevo_instagram', 'type': 'char'},
                'YOUTUBE': {'odoo_field': 'x_brevo_youtube', 'type': 'char'},
                'TIKTOK': {'odoo_field': 'x_brevo_tiktok', 'type': 'char'},
                'ADDRESS': {'odoo_field': 'street', 'type': 'char'},
                'STREET': {'odoo_field': 'street', 'type': 'char'},
                'STREET2': {'odoo_field': 'street2', 'type': 'char'},
                'CITY': {'odoo_field': 'city', 'type': 'char'},
                'ZIP': {'odoo_field': 'zip', 'type': 'char'},
                'POSTAL_CODE': {'odoo_field': 'zip', 'type': 'char'},
                'COUNTRY': {'odoo_field': 'country_id', 'type': 'many2one'},
                'STATE': {'odoo_field': 'state_id', 'type': 'many2one'},
                'PROVINCE': {'odoo_field': 'state_id', 'type': 'many2one'},
                'REGION': {'odoo_field': 'state_id', 'type': 'many2one'},
                'TIMEZONE': {'odoo_field': 'tz', 'type': 'char'},
                'LATITUDE': {'odoo_field': 'x_brevo_latitude', 'type': 'float'},
                'LONGITUDE': {'odoo_field': 'x_brevo_longitude', 'type': 'float'},
                'COMPANY': {'odoo_field': 'company_name', 'type': 'char'},
                'COMPANY_NAME': {'odoo_field': 'company_name', 'type': 'char'},
                'JOB_TITLE': {'odoo_field': 'function', 'type': 'char'},
                'POSITION': {'odoo_field': 'function', 'type': 'char'},
                'DEPARTMENT': {'odoo_field': 'x_brevo_department', 'type': 'char'},
                'INDUSTRY': {'odoo_field': 'industry_id', 'type': 'many2one'},
                'COMPANY_SIZE': {'odoo_field': 'x_brevo_company_size', 'type': 'integer'},
                'ANNUAL_REVENUE': {'odoo_field': 'x_brevo_annual_revenue', 'type': 'float'},
                'EMPLOYEES': {'odoo_field': 'x_brevo_employees', 'type': 'integer'},
                'COMPANY_WEBSITE': {'odoo_field': 'x_brevo_company_website', 'type': 'char'},
                'COMPANY_PHONE': {'odoo_field': 'x_brevo_company_phone', 'type': 'char'},
                'COMPANY_EMAIL': {'odoo_field': 'x_brevo_company_email', 'type': 'char'},
                'SOURCE': {'odoo_field': 'x_brevo_source', 'type': 'char'},
                'LEAD_SOURCE': {'odoo_field': 'x_brevo_source', 'type': 'char'},
                'CAMPAIGN': {'odoo_field': 'x_brevo_campaign', 'type': 'char'},
                'UTM_SOURCE': {'odoo_field': 'x_brevo_source', 'type': 'char'},
                'UTM_MEDIUM': {'odoo_field': 'x_brevo_utm_medium', 'type': 'char'},
                'UTM_CAMPAIGN': {'odoo_field': 'x_brevo_utm_campaign', 'type': 'char'},
                'UTM_TERM': {'odoo_field': 'x_brevo_utm_term', 'type': 'char'},
                'UTM_CONTENT': {'odoo_field': 'x_brevo_utm_content', 'type': 'char'},
                'REFERRER': {'odoo_field': 'x_brevo_referrer', 'type': 'char'},
                'LANDING_PAGE': {'odoo_field': 'x_brevo_landing_page', 'type': 'char'},
                'SUBSCRIBER_TYPE': {'odoo_field': 'x_brevo_subscriber_type', 'type': 'char'},
                'SUBSCRIPTION_STATUS': {'odoo_field': 'x_brevo_subscription_status', 'type': 'selection'},
                'OPT_IN_DATE': {'odoo_field': 'x_brevo_opt_in_date', 'type': 'date'},
                'OPT_OUT_DATE': {'odoo_field': 'x_brevo_opt_out_date', 'type': 'date'},
                'LAST_ACTIVITY': {'odoo_field': 'x_brevo_last_activity', 'type': 'datetime'},
                'LAST_OPEN': {'odoo_field': 'x_brevo_last_open', 'type': 'datetime'},
                'LAST_CLICK': {'odoo_field': 'x_brevo_last_click', 'type': 'datetime'},
                'EMAIL_FREQUENCY': {'odoo_field': 'x_brevo_email_frequency', 'type': 'selection'},
                'PREFERRED_LANGUAGE': {'odoo_field': 'lang', 'type': 'char'},
                'COMMUNICATION_PREFERENCE': {'odoo_field': 'x_brevo_communication_preference', 'type': 'selection'},
                'CUSTOM_FIELD_1': {'odoo_field': 'x_brevo_custom_field_1', 'type': 'char'},
                'CUSTOM_FIELD_2': {'odoo_field': 'x_brevo_custom_field_2', 'type': 'char'},
                'CUSTOM_FIELD_3': {'odoo_field': 'x_brevo_custom_field_3', 'type': 'char'},
                'CUSTOM_FIELD_4': {'odoo_field': 'x_brevo_custom_field_4', 'type': 'char'},
                'CUSTOM_FIELD_5': {'odoo_field': 'x_brevo_custom_field_5', 'type': 'char'},
                'NOTES': {'odoo_field': 'comment', 'type': 'text'},
                'TAGS': {'odoo_field': 'category_id', 'type': 'many2many'},
                'SEGMENT': {'odoo_field': 'x_brevo_segment', 'type': 'char'},
                'SCORE': {'odoo_field': 'x_brevo_score', 'type': 'integer'},
                'PRIORITY': {'odoo_field': 'x_brevo_priority', 'type': 'selection'},
                'STATUS': {'odoo_field': 'x_brevo_status', 'type': 'selection'},
                'STAGE': {'odoo_field': 'x_brevo_stage', 'type': 'char'},
                'TYPE': {'odoo_field': 'x_brevo_type', 'type': 'char'},
                'CATEGORY': {'odoo_field': 'category_id', 'type': 'many2many'},
                'RATING': {'odoo_field': 'x_brevo_rating', 'type': 'integer'},
                'SALARY': {'odoo_field': 'x_brevo_salary', 'type': 'float'},
                'BUDGET': {'odoo_field': 'x_brevo_budget', 'type': 'float'},
                'INTEREST': {'odoo_field': 'x_brevo_interest', 'type': 'char'},
                'HOBBY': {'odoo_field': 'x_brevo_hobby', 'type': 'char'},
                'EDUCATION': {'odoo_field': 'x_brevo_education', 'type': 'char'},
                'EXPERIENCE': {'odoo_field': 'x_brevo_experience', 'type': 'char'},
                'SKILLS': {'odoo_field': 'x_brevo_skills', 'type': 'char'},
                'CERTIFICATIONS': {'odoo_field': 'x_brevo_certifications', 'type': 'char'},
                'LANGUAGES': {'odoo_field': 'x_brevo_languages', 'type': 'char'},
                'AVAILABILITY': {'odoo_field': 'x_brevo_availability', 'type': 'char'},
                'PREFERRED_CONTACT_TIME': {'odoo_field': 'x_brevo_preferred_contact_time', 'type': 'char'},
                'PREFERRED_CONTACT_METHOD': {'odoo_field': 'x_brevo_preferred_contact_method', 'type': 'selection'},
                'CONSENT_DATE': {'odoo_field': 'x_brevo_consent_date', 'type': 'date'},
                'CONSENT_SOURCE': {'odoo_field': 'x_brevo_consent_source', 'type': 'char'},
                'CONSENT_TEXT': {'odoo_field': 'x_brevo_consent_text', 'type': 'text'},
                'GDPR_CONSENT': {'odoo_field': 'x_brevo_gdpr_consent', 'type': 'boolean'},
                'MARKETING_CONSENT': {'odoo_field': 'x_brevo_marketing_consent', 'type': 'boolean'},
                'NEWSLETTER_CONSENT': {'odoo_field': 'x_brevo_newsletter_consent', 'type': 'boolean'},
                'SMS_CONSENT': {'odoo_field': 'x_brevo_sms_consent', 'type': 'boolean'},
                'CALL_CONSENT': {'odoo_field': 'x_brevo_call_consent', 'type': 'boolean'},
                'EMAIL_CONSENT': {'odoo_field': 'x_brevo_email_consent', 'type': 'boolean'},
            }

            # Create discovery records with predefined mappings
            discovery_count = 0
            for brevo_name, mapping_info in predefined_mappings.items():
                # Create discovery record
                discovery_record = self.env['brevo.field.discovery'].create({
                    'brevo_field_name': brevo_name,
                    'odoo_field_name': mapping_info['odoo_field'],
                    'brevo_field_type': 'text',  # Default type
                    'brevo_field_category': 'custom',
                    'company_id': self.company_id.id,
                })
                
                # Create mapping if odoo field exists
                odoo_field = self.env['res.partner']._fields.get(mapping_info['odoo_field'])
                if odoo_field:
                    self.env['brevo.field.mapping'].create({
                        'name': f'{brevo_name} -> {mapping_info["odoo_field"]}',
                        'brevo_field_name': brevo_name,
                        'odoo_field_name': mapping_info['odoo_field'],
                        'field_type': mapping_info['type'],
                        'company_id': self.company_id.id,
                    })
                
                discovery_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Predefined Mappings Created'),
                    'message': _('Created %d predefined field mappings') % discovery_count,
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed to create predefined mappings: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'type': 'danger',
                }
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
