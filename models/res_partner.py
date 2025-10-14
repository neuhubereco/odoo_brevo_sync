# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extend res.partner with Brevo integration fields"""
    _inherit = 'res.partner'

    # Brevo Integration Fields
    brevo_id = fields.Char(
        string='Brevo Contact ID',
        help='Unique identifier for this contact in Brevo',
        index=True
    )
    
    brevo_sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('error', 'Error'),
        ('never', 'Never Synced')
    ], string='Brevo Sync Status', default='never')
    
    brevo_last_sync = fields.Datetime(
        string='Last Brevo Sync',
        help='Last time this contact was synchronized with Brevo'
    )
    
    brevo_sync_error = fields.Text(
        string='Brevo Sync Error',
        help='Last error message from Brevo synchronization'
    )
    
    brevo_attributes = fields.Text(
        string='Brevo Attributes',
        help='Additional attributes stored in Brevo (JSON format)'
    )
    
    # Dynamic Brevo Fields (will be created at runtime)
    brevo_dynamic_fields = fields.Text(
        string='Brevo Dynamic Fields',
        help='JSON storage for dynamically created Brevo fields'
    )
    
    # Brevo Tags
    brevo_tags = fields.Many2many(
        'res.partner.category',
        'partner_brevo_tag_rel',
        'partner_id',
        'category_id',
        string='Brevo Tags',
        help='Tags synchronized from Brevo'
    )
    
    brevo_lists = fields.Many2many(
        'brevo.contact.list',
        'partner_brevo_list_rel',
        'partner_id',
        'list_id',
        string='Brevo Lists',
        help='Brevo contact lists this partner belongs to'
    )
    
    brevo_created_date = fields.Datetime(
        string='Brevo Created Date',
        help='Date when this contact was created in Brevo'
    )
    
    brevo_modified_date = fields.Datetime(
        string='Brevo Modified Date',
        help='Date when this contact was last modified in Brevo'
    )
    
    # Computed fields for sync status
    brevo_sync_needed = fields.Boolean(
        string='Brevo Sync Needed',
        compute='_compute_brevo_sync_needed',
        store=True,
        help='Whether this contact needs to be synchronized with Brevo'
    )
    
    brevo_has_email = fields.Boolean(
        string='Has Email for Brevo',
        compute='_compute_brevo_has_email',
        help='Whether this contact has an email address for Brevo sync'
    )

    @api.depends('brevo_last_sync', 'write_date', 'brevo_sync_status')
    def _compute_brevo_sync_needed(self):
        """Compute whether this contact needs Brevo synchronization"""
        for partner in self:
            if not partner.email:
                partner.brevo_sync_needed = False
                continue
                
            if partner.brevo_sync_status in ['error', 'never']:
                partner.brevo_sync_needed = True
            elif partner.brevo_last_sync and partner.write_date:
                partner.brevo_sync_needed = partner.write_date > partner.brevo_last_sync
            else:
                partner.brevo_sync_needed = True

    @api.depends('email')
    def _compute_brevo_has_email(self):
        """Compute whether this contact has an email for Brevo sync"""
        for partner in self:
            partner.brevo_has_email = bool(partner.email)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle Brevo sync"""
        partners = super().create(vals_list)
        
        # Mark partners with email for Brevo sync
        for partner in partners:
            if partner.email and partner.is_company is False:
                partner.brevo_sync_status = 'pending'
                partner.brevo_sync_needed = True
        
        return partners

    def write(self, vals):
        """Override write to handle Brevo sync"""
        result = super().write(vals)
        
        # Mark partners with email changes for Brevo sync
        if 'email' in vals:
            for partner in self:
                if partner.email and partner.is_company is False:
                    partner.brevo_sync_status = 'pending'
                    partner.brevo_sync_needed = True
        
        return result

    def unlink(self):
        """Override unlink to handle Brevo sync and ask for confirmation"""
        # Check if any partners have Brevo IDs
        brevo_partners = self.filtered(lambda p: p.brevo_id and p.email)
        
        if brevo_partners:
            # Show confirmation dialog
            return {
                'type': 'ir.actions.act_window',
                'name': _('Confirm Deletion'),
                'res_model': 'brevo.delete.confirmation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_partner_ids': [(6, 0, self.ids)],
                    'default_brevo_partner_count': len(brevo_partners),
                }
            }
        
        return super().unlink()

    def sync_to_brevo(self):
        """Manually sync this partner to Brevo"""
        try:
            if not self.email:
                raise ValidationError(_('Email address is required for Brevo sync'))
            
            if self.is_company:
                raise ValidationError(_('Companies cannot be synced to Brevo'))
            
            from ..services.brevo_sync_service import BrevoSyncService
            config = self.env['brevo.config'].get_active_config()
            
            if not config:
                raise ValidationError(_('No active Brevo configuration found'))
            
            sync_service = BrevoSyncService(config)
            result = sync_service.sync_partner_to_brevo(self)
            
            if result.get('success'):
                self.brevo_sync_status = 'synced'
                self.brevo_last_sync = fields.Datetime.now()
                self.brevo_sync_error = False
                self.brevo_sync_needed = False
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Successful'),
                        'message': _('Partner synchronized to Brevo successfully'),
                        'type': 'success',
                    }
                }
            else:
                self.brevo_sync_status = 'error'
                self.brevo_sync_error = result.get('error', 'Unknown error')
                
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
            _logger.error(f"Partner sync to Brevo failed: {str(e)}")
            self.brevo_sync_status = 'error'
            self.brevo_sync_error = str(e)
            
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
            'email': self.email,
            'attributes': {
                'FNAME': self.name.split(' ')[0] if self.name else '',
                'LNAME': ' '.join(self.name.split(' ')[1:]) if self.name and ' ' in self.name else '',
                'SMS': self.mobile or self.phone or '',
                'COMPANY': self.parent_id.name if self.parent_id else '',
                'ADDRESS': self.street or '',
                'CITY': self.city or '',
                'STATE': self.state_id.name if self.state_id else '',
                'ZIP': self.zip or '',
                'COUNTRY': self.country_id.name if self.country_id else '',
            },
            'listIds': [int(list_id.brevo_id) for list_id in self.brevo_lists if list_id.brevo_id],
            'updateEnabled': True,
        }

    @api.model
    def get_partners_for_brevo_sync(self, limit=None):
        """Get partners that need Brevo synchronization"""
        domain = [
            ('email', '!=', False),
            ('is_company', '=', False),
            ('brevo_sync_needed', '=', True),
        ]
        
        return self.search(domain, limit=limit)

    @api.model
    def create_from_brevo_data(self, brevo_data):
        """Create a new partner from Brevo data"""
        try:
            # Check if partner already exists by email
            existing_partner = self.search([('email', '=', brevo_data.get('email'))], limit=1)
            if existing_partner:
                return existing_partner
            
            # Extract attributes
            attributes = brevo_data.get('attributes', {})
            
            # Create new partner
            partner_vals = {
                'name': f"{attributes.get('FNAME', '')} {attributes.get('LNAME', '')}".strip(),
                'email': brevo_data.get('email'),
                'mobile': attributes.get('SMS', ''),
                'street': attributes.get('ADDRESS', ''),
                'city': attributes.get('CITY', ''),
                'zip': attributes.get('ZIP', ''),
                'brevo_id': str(brevo_data.get('id')),
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
                'brevo_created_date': brevo_data.get('createdAt'),
                'brevo_modified_date': brevo_data.get('modifiedAt'),
            }
            
            # Handle country
            if attributes.get('COUNTRY'):
                country = self.env['res.country'].search([('name', '=', attributes.get('COUNTRY'))], limit=1)
                if country:
                    partner_vals['country_id'] = country.id
            
            # Handle state
            if attributes.get('STATE'):
                state = self.env['res.country.state'].search([
                    ('name', '=', attributes.get('STATE')),
                    ('country_id', '=', partner_vals.get('country_id'))
                ], limit=1)
                if state:
                    partner_vals['state_id'] = state.id
            
            partner = self.create(partner_vals)
            
            # Handle company
            if attributes.get('COMPANY'):
                company = self.env['res.partner'].search([
                    ('name', '=', attributes.get('COMPANY')),
                    ('is_company', '=', True)
                ], limit=1)
                if company:
                    partner.parent_id = company.id
            
            return partner
            
        except Exception as e:
            _logger.error(f"Failed to create partner from Brevo data: {str(e)}")
            raise ValidationError(_('Failed to create partner from Brevo data: %s') % str(e))
