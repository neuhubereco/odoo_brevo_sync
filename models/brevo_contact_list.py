# -*- coding: utf-8 -*-

import logging
import json
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BrevoContactList(models.Model):
    """Model to represent Brevo contact lists"""
    _name = 'brevo.contact.list'
    _description = 'Brevo Contact List'
    _rec_name = 'name'

    name = fields.Char(
        string='List Name',
        required=True,
        help='Name of the contact list'
    )
    
    brevo_id = fields.Char(
        string='Brevo List ID',
        required=True,
        help='Unique identifier for this list in Brevo',
        index=True
    )
    
    description = fields.Text(
        string='Description',
        help='Description of the contact list'
    )
    
    folder_id = fields.Char(
        string='Brevo Folder ID',
        help='ID of the folder this list belongs to in Brevo'
    )
    
    unique_subscribers = fields.Integer(
        string='Unique Subscribers',
        help='Number of unique subscribers in this list'
    )
    
    total_blacklisted = fields.Integer(
        string='Total Blacklisted',
        help='Number of blacklisted contacts in this list'
    )
    
    total_unsubscribers = fields.Integer(
        string='Total Unsubscribers',
        help='Number of unsubscribed contacts in this list'
    )
    
    # Mapping to Odoo partner categories
    partner_category_id = fields.Many2one(
        'res.partner.category',
        string='Partner Category',
        help='Odoo partner category mapped to this Brevo list'
    )
    
    partner_category_ids = fields.Many2many(
        'res.partner.category',
        'brevo_list_category_rel',
        'list_id',
        'category_id',
        string='Partner Categories',
        help='Odoo partner categories mapped to this Brevo list'
    )
    
    # Sync information
    sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('error', 'Error'),
        ('never', 'Never Synced')
    ], string='Sync Status', default='never')
    
    last_sync = fields.Datetime(
        string='Last Sync',
        help='Last time this list was synchronized'
    )
    
    sync_error = fields.Text(
        string='Sync Error',
        help='Last error message from synchronization'
    )
    
    # Timestamps
    created_at = fields.Datetime(
        string='Created At',
        help='When this list was created in Brevo'
    )
    
    updated_at = fields.Datetime(
        string='Updated At',
        help='When this list was last updated in Brevo'
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
        help='Whether this list is active'
    )

    _sql_constraints = [
        ('brevo_id_unique', 'unique(brevo_id, company_id)', 
         'Brevo List ID must be unique per company!'),
    ]

    @api.model
    def create_from_brevo_data(self, brevo_data, company_id=None):
        """Create a new contact list from Brevo data"""
        try:
            company_id = company_id or self.env.company.id
            
            # Check if list already exists
            existing_list = self.search([
                ('brevo_id', '=', str(brevo_data.get('id'))),
                ('company_id', '=', company_id)
            ], limit=1)
            
            if existing_list:
                return existing_list
            
            # Create new list
            list_vals = {
                'name': brevo_data.get('name', ''),
                'brevo_id': str(brevo_data.get('id')),
                'description': brevo_data.get('description', ''),
                'folder_id': str(brevo_data.get('folderId', '')),
                'unique_subscribers': brevo_data.get('uniqueSubscribers', 0),
                'total_blacklisted': brevo_data.get('totalBlacklisted', 0),
                'total_unsubscribers': brevo_data.get('totalUnsubscribers', 0),
                'created_at': brevo_data.get('createdAt'),
                'updated_at': brevo_data.get('updatedAt'),
                'company_id': company_id,
                'sync_status': 'synced',
                'last_sync': fields.Datetime.now(),
            }
            
            return self.create(list_vals)
            
        except Exception as e:
            _logger.error(f"Failed to create contact list from Brevo data: {str(e)}")
            raise ValidationError(_('Failed to create contact list from Brevo data: %s') % str(e))

    def update_from_brevo_data(self, brevo_data):
        """Update this list with data from Brevo"""
        try:
            update_vals = {
                'name': brevo_data.get('name', self.name),
                'description': brevo_data.get('description', self.description),
                'folder_id': str(brevo_data.get('folderId', self.folder_id)),
                'unique_subscribers': brevo_data.get('uniqueSubscribers', self.unique_subscribers),
                'total_blacklisted': brevo_data.get('totalBlacklisted', self.total_blacklisted),
                'total_unsubscribers': brevo_data.get('totalUnsubscribers', self.total_unsubscribers),
                'updated_at': brevo_data.get('updatedAt', self.updated_at),
                'sync_status': 'synced',
                'last_sync': fields.Datetime.now(),
                'sync_error': False,
            }
            
            self.write(update_vals)
            
        except Exception as e:
            _logger.error(f"Failed to update contact list from Brevo data: {str(e)}")
            self.sync_status = 'error'
            self.sync_error = str(e)

    def sync_to_brevo(self):
        """Manually sync this list to Brevo"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            config = self.env['brevo.config'].get_active_config()
            
            if not config:
                raise ValidationError(_('No active Brevo configuration found'))
            
            sync_service = BrevoSyncService(config)
            result = sync_service.sync_list_to_brevo(self)
            
            if result.get('success'):
                self.sync_status = 'synced'
                self.last_sync = fields.Datetime.now()
                self.sync_error = False
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Successful'),
                        'message': _('Contact list synchronized to Brevo successfully'),
                        'type': 'success',
                    }
                }
            else:
                self.sync_status = 'error'
                self.sync_error = result.get('error', 'Unknown error')
                
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
            _logger.error(f"Contact list sync to Brevo failed: {str(e)}")
            self.sync_status = 'error'
            self.sync_error = str(e)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def get_brevo_data(self):
        """Get data formatted for Brevo API"""
        return {
            'name': self.name,
            'description': self.description or '',
            'folderId': int(self.folder_id) if self.folder_id else None,
        }

    @api.model
    def get_lists_for_brevo_sync(self, limit=None):
        """Get contact lists that need Brevo synchronization"""
        domain = [
            ('active', '=', True),
            ('sync_status', 'in', ['pending', 'error', 'never']),
        ]
        
        return self.search(domain, limit=limit)

    def sync_memberships(self):
        """Sync list memberships with Brevo"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            config = self.env['brevo.config'].get_active_config()
            
            if not config:
                raise ValidationError(_('No active Brevo configuration found'))
            
            sync_service = BrevoSyncService(config)
            result = sync_service.sync_list_memberships(self)
            
            if result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Successful'),
                        'message': _('List memberships synchronized successfully'),
                        'type': 'success',
                    }
                }
            else:
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
            _logger.error(f"List memberships sync failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }
