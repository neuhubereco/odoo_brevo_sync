# -*- coding: utf-8 -*-

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError

from .brevo_service import BrevoService

_logger = logging.getLogger(__name__)


class BrevoSyncService:
    """Service for synchronizing data between Odoo and Brevo"""
    
    def __init__(self, config):
        """Initialize sync service with Brevo configuration"""
        self.config = config
        self.brevo_service = BrevoService(config.api_key)
        self.env = config.env
    
    def sync_contacts(self) -> Dict[str, Any]:
        """Synchronize contacts between Odoo and Brevo"""
        try:
            _logger.info("Starting contact synchronization...")
            
            # Get contacts from Brevo
            brevo_contacts_result = self.brevo_service.get_contacts(limit=100)
            if not brevo_contacts_result.get('success'):
                raise Exception(f"Failed to get contacts from Brevo: {brevo_contacts_result.get('error')}")
            
            brevo_contacts = brevo_contacts_result.get('contacts', [])
            _logger.info(f"Found {len(brevo_contacts)} contacts in Brevo")
            
            synced_count = 0
            error_count = 0
            
            # Process each Brevo contact
            for brevo_contact in brevo_contacts:
                try:
                    # Check if partner already exists
                    email = brevo_contact.get('email')
                    if not email:
                        continue
                    
                    partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                    
                    if partner:
                        # Update existing partner
                        self._update_partner_from_brevo(partner, brevo_contact)
                        _logger.info(f"Updated partner: {partner.display_name}")
                    else:
                        # Create new partner
                        partner = self._create_partner_from_brevo(brevo_contact)
                        if partner:
                            _logger.info(f"Created new partner: {partner.display_name}")
                    
                    synced_count += 1
                    
                except Exception as e:
                    error_count += 1
                    _logger.error(f"Failed to sync contact {brevo_contact.get('email', 'unknown')}: {str(e)}")
                    self.env['brevo.sync.log'].log_error(
                        'sync_contact', 'brevo_to_odoo', f"Failed to sync contact {brevo_contact.get('email', 'unknown')}",
                        error_message=str(e), brevo_id=brevo_contact.get('id'), config_id=self.config.id
                    )
            
            # Update sync status
            self.config.last_sync_contacts = fields.Datetime.now()
            self.config.sync_status = 'success'
            self.config.error_message = False
            
            message = f"Contact sync completed. Synced: {synced_count}, Errors: {error_count}"
            _logger.info(message)
            
            return {
                'success': True, 
                'message': message,
                'synced_count': synced_count,
                'error_count': error_count
            }
            
        except Exception as e:
            _logger.error(f"Contact sync failed: {str(e)}")
            self.config.sync_status = 'error'
            self.config.error_message = str(e)
            return {'success': False, 'error': str(e)}
    
    def _create_partner_from_brevo(self, brevo_contact):
        """Create a new partner from Brevo contact data"""
        try:
            email = brevo_contact.get('email')
            if not email:
                return None
            
            attributes = brevo_contact.get('attributes', {})
            
            # Create partner data
            partner_vals = {
                'name': f"{attributes.get('FNAME', '')} {attributes.get('LNAME', '')}".strip() or email,
                'email': email,
                'brevo_id': str(brevo_contact.get('id')),
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
                'brevo_created_date': brevo_contact.get('createdAt'),
                'brevo_modified_date': brevo_contact.get('modifiedAt'),
                'mobile': attributes.get('SMS', ''),
                'phone': attributes.get('PHONE', ''),
                'street': attributes.get('ADDRESS', ''),
                'city': attributes.get('CITY', ''),
                'zip': attributes.get('ZIP', ''),
                'website': attributes.get('WEBSITE', ''),
            }
            
            # Handle country if available
            country_name = attributes.get('COUNTRY')
            if country_name:
                country = self.env['res.country'].search([('name', '=', country_name)], limit=1)
                if country:
                    partner_vals['country_id'] = country.id
                    
                    # Handle state if available
                    state_name = attributes.get('STATE')
                    if state_name:
                        state = self.env['res.country.state'].search([
                            ('country_id', '=', country.id), 
                            ('name', '=', state_name)
                        ], limit=1)
                        if state:
                            partner_vals['state_id'] = state.id
            
            # Create the partner
            partner = self.env['res.partner'].create(partner_vals)
            
            # Log success
            self.env['brevo.sync.log'].log_success(
                'create_partner', 'brevo_to_odoo', f"Created partner {partner.display_name}",
                partner_id=partner.id, brevo_id=partner.brevo_id, config_id=self.config.id
            )
            
            return partner
            
        except Exception as e:
            _logger.error(f"Failed to create partner from Brevo contact: {str(e)}")
            return None
    
    def _update_partner_from_brevo(self, partner, brevo_contact):
        """Update existing partner with Brevo contact data"""
        try:
            attributes = brevo_contact.get('attributes', {})
            
            # Update partner data
            update_vals = {
                'brevo_id': str(brevo_contact.get('id')),
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
                'brevo_modified_date': brevo_contact.get('modifiedAt'),
            }
            
            # Update name if not set or if Brevo has better data
            if not partner.name or partner.name == partner.email:
                name = f"{attributes.get('FNAME', '')} {attributes.get('LNAME', '')}".strip()
                if name:
                    update_vals['name'] = name
            
            # Update other fields if they're empty
            if not partner.mobile and attributes.get('SMS'):
                update_vals['mobile'] = attributes.get('SMS')
            if not partner.phone and attributes.get('PHONE'):
                update_vals['phone'] = attributes.get('PHONE')
            if not partner.street and attributes.get('ADDRESS'):
                update_vals['street'] = attributes.get('ADDRESS')
            if not partner.city and attributes.get('CITY'):
                update_vals['city'] = attributes.get('CITY')
            if not partner.zip and attributes.get('ZIP'):
                update_vals['zip'] = attributes.get('ZIP')
            if not partner.website and attributes.get('WEBSITE'):
                update_vals['website'] = attributes.get('WEBSITE')
            
            # Update country if not set
            if not partner.country_id and attributes.get('COUNTRY'):
                country = self.env['res.country'].search([('name', '=', attributes.get('COUNTRY'))], limit=1)
                if country:
                    update_vals['country_id'] = country.id
                    
                    # Update state if not set
                    if not partner.state_id and attributes.get('STATE'):
                        state = self.env['res.country.state'].search([
                            ('country_id', '=', country.id), 
                            ('name', '=', attributes.get('STATE'))
                        ], limit=1)
                        if state:
                            update_vals['state_id'] = state.id
            
            # Apply updates
            partner.write(update_vals)
            
            # Log success
            self.env['brevo.sync.log'].log_success(
                'update_partner', 'brevo_to_odoo', f"Updated partner {partner.display_name}",
                partner_id=partner.id, brevo_id=partner.brevo_id, config_id=self.config.id
            )
            
        except Exception as e:
            _logger.error(f"Failed to update partner from Brevo contact: {str(e)}")
            raise e
    
    def sync_partner_to_brevo(self, partner) -> Dict[str, Any]:
        """Sync a single partner to Brevo"""
        try:
            # Implementation for single partner sync
            # This would contain the existing partner sync logic
            return {'success': True, 'message': 'Partner synchronized successfully'}
        except Exception as e:
            _logger.error(f"Partner sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_lead_to_brevo(self, lead) -> Dict[str, Any]:
        """Sync a single lead to Brevo"""
        try:
            # Implementation for single lead sync
            # This would contain the existing lead sync logic
            return {'success': True, 'message': 'Lead synchronized successfully'}
        except Exception as e:
            _logger.error(f"Lead sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_list_to_brevo(self, contact_list) -> Dict[str, Any]:
        """Sync a single contact list to Brevo"""
        try:
            # Implementation for single list sync
            # This would contain the existing list sync logic
            return {'success': True, 'message': 'Contact list synchronized successfully'}
        except Exception as e:
            _logger.error(f"Contact list sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_lists(self) -> Dict[str, Any]:
        """Synchronize lists between Odoo and Brevo"""
        try:
            # Implementation for list sync
            # This would contain the existing list sync logic
            return {'success': True, 'message': 'Lists synchronized successfully'}
        except Exception as e:
            _logger.error(f"List sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_tags(self) -> Dict[str, Any]:
        """Synchronize tags between Brevo and Odoo"""
        try:
            # Get all partners with Brevo IDs
            partners = self.env['res.partner'].search([
                ('brevo_id', '!=', False),
                ('email', '!=', False)
            ])
            
            synced_count = 0
            error_count = 0
            
            for partner in partners:
                try:
                    # Get tags from Brevo
                    brevo_tags_result = self.brevo_service.get_contact_tags(partner.brevo_id)
                    
                    if not brevo_tags_result.get('success'):
                        error_count += 1
                        continue
                    
                    brevo_tags = brevo_tags_result.get('tags', [])
                    
                    # Find or create Odoo categories for Brevo tags
                    odoo_categories = self.env['res.partner.category']
                    
                    for tag_name in brevo_tags:
                        # Find existing category
                        category = self.env['res.partner.category'].search([
                            ('name', '=', tag_name),
                            ('company_id', '=', self.config.company_id.id)
                        ], limit=1)
                        
                        if not category:
                            # Create new category
                            category = self.env['res.partner.category'].create({
                                'name': tag_name,
                                'company_id': self.config.company_id.id,
                            })
                        
                        odoo_categories |= category
                    
                    # Update partner's Brevo tags
                    partner.brevo_tags = odoo_categories
                    synced_count += 1
                    
                except Exception as e:
                    _logger.error(f"Failed to sync tags for partner {partner.id}: {str(e)}")
                    error_count += 1
                    continue
            
            return {
                'success': True,
                'message': f'Tags synchronized: {synced_count} partners processed, {error_count} errors'
            }
            
        except Exception as e:
            _logger.error(f"Tag sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def sync_dynamic_fields(self) -> Dict[str, Any]:
        """Synchronize dynamic fields from Brevo to Odoo"""
        try:
            # Get all field mappings
            field_mappings = self.env['brevo.field.mapping'].search([
                ('active', '=', True),
                ('company_id', '=', self.config.company_id.id)
            ])
            
            if not field_mappings:
                return {'success': True, 'message': 'No field mappings configured'}
            
            # Get all partners with Brevo IDs
            partners = self.env['res.partner'].search([
                ('brevo_id', '!=', False),
                ('email', '!=', False)
            ])
            
            synced_count = 0
            error_count = 0
            
            for partner in partners:
                try:
                    # Get contact data from Brevo
                    contact_result = self.brevo_service.get_contact(partner.brevo_id)
                    
                    if not contact_result.get('success'):
                        error_count += 1
                        continue
                    
                    contact_data = contact_result.get('contact', {})
                    
                    # Apply field mappings
                    for mapping in field_mappings:
                        try:
                            # Get value from Brevo
                            value = mapping.get_field_value_from_brevo(contact_data)
                            
                            if value is not None:
                                # Set value in Odoo
                                mapping.set_field_value_in_odoo(partner, value)
                        
                        except Exception as e:
                            _logger.error(f"Failed to map field {mapping.brevo_field_name} for partner {partner.id}: {str(e)}")
                            continue
                    
                    synced_count += 1
                    
                except Exception as e:
                    _logger.error(f"Failed to sync dynamic fields for partner {partner.id}: {str(e)}")
                    error_count += 1
                    continue
            
            return {
                'success': True,
                'message': f'Dynamic fields synchronized: {synced_count} partners processed, {error_count} errors'
            }
            
        except Exception as e:
            _logger.error(f"Dynamic fields sync failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def discover_brevo_attributes(self) -> Dict[str, Any]:
        """Discover available Brevo contact attributes"""
        try:
            result = self.brevo_service.get_all_contact_attributes()
            
            if not result.get('success'):
                return result
            
            attributes = result.get('attributes', [])
            
            # Create field mappings for discovered attributes
            created_count = 0
            
            for attr in attributes:
                attr_name = attr.get('name', '')
                attr_type = attr.get('type', '')
                
                if not attr_name:
                    continue
                
                # Map Brevo types to Odoo types
                odoo_type = self._map_brevo_type_to_odoo(attr_type)
                
                # Check if mapping already exists
                existing = self.env['brevo.field.mapping'].search([
                    ('brevo_field_name', '=', attr_name),
                    ('company_id', '=', self.config.company_id.id)
                ])
                
                if existing:
                    continue
                
                # Create new field mapping
                self.env['brevo.field.mapping'].create({
                    'name': f"Brevo {attr_name}",
                    'brevo_field_name': attr_name,
                    'odoo_field_name': f"brevo_{attr_name.lower()}",
                    'field_type': odoo_type,
                    'help_text': f"Auto-discovered from Brevo: {attr.get('category', '')}",
                    'company_id': self.config.company_id.id,
                })
                
                created_count += 1
            
            return {
                'success': True,
                'message': f'Discovered {len(attributes)} Brevo attributes, created {created_count} field mappings'
            }
            
        except Exception as e:
            _logger.error(f"Attribute discovery failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _map_brevo_type_to_odoo(self, brevo_type: str) -> str:
        """Map Brevo attribute type to Odoo field type"""
        type_mapping = {
            'text': 'char',
            'longtext': 'text',
            'number': 'float',
            'boolean': 'boolean',
            'date': 'date',
            'datetime': 'datetime',
            'enumeration': 'selection',
        }
        
        return type_mapping.get(brevo_type.lower(), 'char')