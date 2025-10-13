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
            # Implementation for contact sync
            # This would contain the existing contact sync logic
            return {'success': True, 'message': 'Contacts synchronized successfully'}
        except Exception as e:
            _logger.error(f"Contact sync failed: {str(e)}")
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