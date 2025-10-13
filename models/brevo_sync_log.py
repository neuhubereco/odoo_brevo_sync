# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BrevoSyncLog(models.Model):
    """Model to log Brevo synchronization activities"""
    _name = 'brevo.sync.log'
    _description = 'Brevo Synchronization Log'
    _order = 'create_date desc'
    _rec_name = 'operation'

    # Basic Information
    operation = fields.Selection([
        ('contact_create', 'Create Contact'),
        ('contact_update', 'Update Contact'),
        ('contact_delete', 'Delete Contact'),
        ('list_create', 'Create List'),
        ('list_update', 'Update List'),
        ('list_delete', 'Delete List'),
        ('membership_add', 'Add to List'),
        ('membership_remove', 'Remove from List'),
        ('lead_create', 'Create Lead'),
        ('sync_all', 'Full Sync'),
        ('webhook', 'Webhook Processing'),
    ], string='Operation', required=True)
    
    direction = fields.Selection([
        ('odoo_to_brevo', 'Odoo → Brevo'),
        ('brevo_to_odoo', 'Brevo → Odoo'),
        ('bidirectional', 'Bidirectional'),
    ], string='Direction', required=True)
    
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ], string='Status', required=True)
    
    # Related Records
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        help='Related partner record'
    )
    
    contact_list_id = fields.Many2one(
        'brevo.contact.list',
        string='Contact List',
        help='Related contact list record'
    )
    
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        help='Related CRM lead record'
    )
    
    # Brevo Information
    brevo_id = fields.Char(
        string='Brevo ID',
        help='Brevo record identifier'
    )
    
    brevo_email = fields.Char(
        string='Brevo Email',
        help='Email address from Brevo'
    )
    
    # Message and Details
    message = fields.Text(
        string='Message',
        required=True,
        help='Log message'
    )
    
    details = fields.Text(
        string='Details',
        help='Additional details (JSON format)'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error message if status is error'
    )
    
    # Timing Information
    start_time = fields.Datetime(
        string='Start Time',
        help='When the operation started'
    )
    
    end_time = fields.Datetime(
        string='End Time',
        help='When the operation ended'
    )
    
    duration = fields.Float(
        string='Duration (seconds)',
        compute='_compute_duration',
        help='Operation duration in seconds'
    )
    
    # Configuration
    config_id = fields.Many2one(
        'brevo.config',
        string='Configuration',
        help='Brevo configuration used for this operation'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Compute operation duration"""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds()
            else:
                record.duration = 0.0

    @api.model
    def create_log(self, operation, direction, status, message, **kwargs):
        """Create a new sync log entry"""
        log_vals = {
            'operation': operation,
            'direction': direction,
            'status': status,
            'message': message,
            'start_time': kwargs.get('start_time', fields.Datetime.now()),
            'end_time': kwargs.get('end_time', fields.Datetime.now()),
            'config_id': kwargs.get('config_id'),
            'company_id': kwargs.get('company_id', self.env.company.id),
        }
        
        # Add optional fields
        for field in ['partner_id', 'contact_list_id', 'lead_id', 'brevo_id', 
                     'brevo_email', 'details', 'error_message']:
            if field in kwargs:
                log_vals[field] = kwargs[field]
        
        return self.create(log_vals)

    @api.model
    def log_success(self, operation, direction, message, **kwargs):
        """Log a successful operation"""
        return self.create_log(operation, direction, 'success', message, **kwargs)

    @api.model
    def log_error(self, operation, direction, message, error_message=None, **kwargs):
        """Log a failed operation"""
        kwargs['error_message'] = error_message
        return self.create_log(operation, direction, 'error', message, **kwargs)

    @api.model
    def log_warning(self, operation, direction, message, **kwargs):
        """Log a warning"""
        return self.create_log(operation, direction, 'warning', message, **kwargs)

    @api.model
    def log_info(self, operation, direction, message, **kwargs):
        """Log an informational message"""
        return self.create_log(operation, direction, 'info', message, **kwargs)

    def get_recent_logs(self, limit=100):
        """Get recent log entries"""
        return self.search([], limit=limit)

    def get_error_logs(self, limit=50):
        """Get recent error log entries"""
        return self.search([
            ('status', '=', 'error')
        ], limit=limit)

    def get_logs_by_operation(self, operation, limit=50):
        """Get logs for a specific operation"""
        return self.search([
            ('operation', '=', operation)
        ], limit=limit)

    def get_logs_by_partner(self, partner_id, limit=50):
        """Get logs for a specific partner"""
        return self.search([
            ('partner_id', '=', partner_id)
        ], limit=limit)

    def cleanup_old_logs(self, days=30):
        """Clean up old log entries"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([
            ('create_date', '<', cutoff_date),
            ('status', '!=', 'error')  # Keep error logs longer
        ])
        
        if old_logs:
            old_logs.unlink()
            _logger.info(f"Cleaned up {len(old_logs)} old sync log entries")

    def action_view_related_record(self):
        """Action to view the related record"""
        if self.partner_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Partner'),
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.contact_list_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact List'),
                'res_model': 'brevo.contact.list',
                'res_id': self.contact_list_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.lead_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Lead'),
                'res_model': 'crm.lead',
                'res_id': self.lead_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Related Record'),
                    'message': _('No related record found for this log entry'),
                    'type': 'info',
                }
            }

    def action_cleanup_old_logs(self):
        """Method for cron job to cleanup old logs"""
        try:
            # Delete logs older than 30 days, but keep error logs for 90 days
            cutoff_date_success = fields.Datetime.now() - timedelta(days=30)
            cutoff_date_error = fields.Datetime.now() - timedelta(days=90)
            
            # Delete successful logs older than 30 days
            success_logs = self.search([
                ('status', '=', 'success'),
                ('create_date', '<', cutoff_date_success)
            ])
            success_logs.unlink()
            
            # Delete error logs older than 90 days
            error_logs = self.search([
                ('status', '=', 'error'),
                ('create_date', '<', cutoff_date_error)
            ])
            error_logs.unlink()
            
            _logger.info(f"Cleaned up old Brevo sync logs: {len(success_logs)} success logs, {len(error_logs)} error logs")
        except Exception as e:
            _logger.error(f"Failed to cleanup old Brevo sync logs: {str(e)}")
