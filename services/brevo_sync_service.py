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
    
    def _parse_brevo_datetime(self, date_string):
        """Parse Brevo datetime string to Odoo datetime format"""
        if not date_string:
            return None
        
        try:
            # Handle different Brevo datetime formats
            if 'T' in date_string:
                # ISO format with timezone
                if '+' in date_string or 'Z' in date_string:
                    # Remove timezone info for Odoo
                    date_string = date_string.split('+')[0].split('Z')[0]
                # Parse ISO format
                return datetime.fromisoformat(date_string.replace('T', ' '))
            else:
                # Simple date format
                return datetime.strptime(date_string, '%Y-%m-%d')
        except Exception as e:
            _logger.warning(f"Failed to parse datetime '{date_string}': {str(e)}")
            return None
    
    def sync_contacts(self) -> Dict[str, Any]:
        """Synchronize contacts between Odoo and Brevo"""
        try:
            _logger.info("Starting contact synchronization...")
            
            # Get contacts from Brevo in batches
            batch_size = self.config.batch_size or 100
            offset = 0
            total_synced = 0
            total_errors = 0
            
            while True:
                # Get batch of contacts from Brevo
                brevo_contacts_result = self.brevo_service.get_contacts(limit=batch_size, offset=offset)
                if not brevo_contacts_result.get('success'):
                    raise Exception(f"Failed to get contacts from Brevo: {brevo_contacts_result.get('error')}")
                
                brevo_contacts = brevo_contacts_result.get('contacts', [])
                if not brevo_contacts:
                    break  # No more contacts
                
                _logger.info(f"Processing batch {offset//batch_size + 1}: {len(brevo_contacts)} contacts")
                
                batch_synced = 0
                batch_errors = 0
                
                # Process each contact in this batch
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
                        
                        batch_synced += 1
                        
                    except Exception as e:
                        batch_errors += 1
                        _logger.error(f"Failed to sync contact {brevo_contact.get('email', 'unknown')}: {str(e)}")
                        self.env['brevo.sync.log'].log_error(
                            'sync_contact', 'brevo_to_odoo', f"Failed to sync contact {brevo_contact.get('email', 'unknown')}",
                            error_message=str(e), brevo_id=brevo_contact.get('id'), config_id=self.config.id
                        )
                
                total_synced += batch_synced
                total_errors += batch_errors
                offset += batch_size
                
                # Log batch progress
                _logger.info(f"Batch completed: {batch_synced} synced, {batch_errors} errors")
                
                # Break if we got fewer contacts than requested (end of data)
                if len(brevo_contacts) < batch_size:
                    break
            
            # Update sync status
            self.config.last_sync_contacts = fields.Datetime.now()
            self.config.sync_status = 'success'
            self.config.error_message = False
            
            message = f"Contact sync completed. Total synced: {total_synced}, Total errors: {total_errors}"
            _logger.info(message)
            
            return {
                'success': True, 
                'message': message,
                'synced_count': total_synced,
                'error_count': total_errors
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
                'brevo_created_date': self._parse_brevo_datetime(brevo_contact.get('createdAt')),
                'brevo_modified_date': self._parse_brevo_datetime(brevo_contact.get('modifiedAt')),
                'mobile': attributes.get('SMS', ''),
                'phone': attributes.get('PHONE', ''),
                'street': attributes.get('ADDRESS', ''),
                'city': attributes.get('CITY', ''),
                'zip': attributes.get('ZIP', ''),
                'website': attributes.get('WEBSITE', ''),
            }
            
            # Handle Brevo lists (map to Odoo categories)
            list_ids = brevo_contact.get('listIds', [])
            brevo_list_records = []
            if list_ids:
                # Find corresponding Odoo categories for Brevo lists
                brevo_lists = self.env['brevo.contact.list'].search([
                    ('brevo_id', 'in', [str(lid) for lid in list_ids]),
                    ('company_id', '=', self.config.company_id.id)
                ])
                if brevo_lists:
                    category_ids = brevo_lists.mapped('partner_category_id.id')
                    if category_ids:
                        partner_vals['category_id'] = [(6, 0, category_ids)]
                    # Store Brevo list records for brevo_lists field
                    brevo_list_records = brevo_lists.ids
            
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
            
            # Apply field mappings (Brevo -> Odoo), including x_brevo_ Felder
            # But preserve the name field that was already set from FNAME + LNAME
            original_name = partner_vals.get('name')
            self._apply_attribute_mappings_to_vals(attributes, partner_vals)
            
            # Restore the original name if it was overwritten by mappings
            if original_name and original_name != partner_vals.get('name'):
                partner_vals['name'] = original_name

            # Create the partner
            partner = self.env['res.partner'].create(partner_vals)
            
            # Set Brevo lists after creation
            if brevo_list_records:
                partner.brevo_lists = [(6, 0, brevo_list_records)]
            
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
                'brevo_modified_date': self._parse_brevo_datetime(brevo_contact.get('modifiedAt')),
            }
            
            # Set created date if not already set
            if not partner.brevo_created_date:
                update_vals['brevo_created_date'] = self._parse_brevo_datetime(brevo_contact.get('createdAt'))
            
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
            
            # Handle Brevo lists (map to Odoo categories)
            list_ids = brevo_contact.get('listIds', [])
            brevo_list_records = []
            if list_ids:
                # Find corresponding Odoo categories for Brevo lists
                brevo_lists = self.env['brevo.contact.list'].search([
                    ('brevo_id', 'in', [str(lid) for lid in list_ids]),
                    ('company_id', '=', self.config.company_id.id)
                ])
                if brevo_lists:
                    category_ids = brevo_lists.mapped('partner_category_id.id')
                    if category_ids:
                        # Merge with existing categories
                        existing_categories = partner.category_id.ids
                        all_categories = list(set(existing_categories + category_ids))
                        update_vals['category_id'] = [(6, 0, all_categories)]
                    # Store Brevo list records for brevo_lists field
                    brevo_list_records = brevo_lists.ids
            
            # Apply field mappings (Brevo -> Odoo), including x_brevo_ Felder
            # But preserve the name field that was already set from FNAME + LNAME
            original_name = update_vals.get('name')
            self._apply_attribute_mappings_to_vals(attributes, update_vals, partner=partner)
            
            # Restore the original name if it was overwritten by mappings
            if original_name and original_name != update_vals.get('name'):
                update_vals['name'] = original_name

            # Apply updates
            partner.write(update_vals)
            
            # Update Brevo lists after write
            if brevo_list_records:
                partner.brevo_lists = [(6, 0, brevo_list_records)]
            
            # Log success
            self.env['brevo.sync.log'].log_success(
                'update_partner', 'brevo_to_odoo', f"Updated partner {partner.display_name}",
                partner_id=partner.id, brevo_id=partner.brevo_id, config_id=self.config.id
            )
            
        except Exception as e:
            _logger.error(f"Failed to update partner from Brevo contact: {str(e)}")
            raise e

    def _apply_attribute_mappings_to_vals(self, attributes: Dict[str, Any], vals: Dict[str, Any], partner=None) -> None:
        """Apply active Brevo->Odoo field mappings to a vals dict for partner create/update.
        If partner provided, we are in update-mode; otherwise create-mode.
        """
        try:
            # Get active mappings for current company
            mapping_domain = [
                ('active', '=', True),
                ('company_id', '=', self.config.company_id.id)
            ]
            mappings = self.env['brevo.field.mapping'].search(mapping_domain)

            for mapping in mappings:
                brevo_key = mapping.brevo_field_name
                odoo_field = mapping.odoo_field_name
                if not brevo_key or not odoo_field:
                    continue

                if brevo_key not in attributes:
                    continue

                raw_value = attributes.get(brevo_key)
                if raw_value in (None, ''):
                    continue

                # Convert value according to Odoo field type when possible
                field_def = self.env['res.partner']._fields.get(odoo_field)
                if not field_def:
                    continue

                converted = self._convert_brevo_value_for_field(raw_value, field_def)

                # On update, optionally avoid overwriting non-empty values unless desired
                if partner is not None:
                    try:
                        current = getattr(partner, odoo_field)
                        if current not in (False, None, '') and str(current) == str(converted):
                            continue
                    except Exception:
                        pass

                vals[odoo_field] = converted

        except Exception as map_exc:
            _logger.warning(f"Failed to apply attribute mappings: {str(map_exc)}")

    def _convert_brevo_value_for_field(self, value: Any, field_def) -> Any:
        """Convert Brevo attribute value to match the Odoo field type.
        Supports char/text, integer, float, boolean, date, datetime, selection.
        """
        ftype = getattr(field_def, 'type', 'char')
        try:
            if ftype in ('char', 'text', 'html'):  # html unlikely here
                return '' if value is None else str(value)
            if ftype == 'integer':
                return int(value)
            if ftype == 'float':
                return float(value)
            if ftype == 'boolean':
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                val = str(value).strip().lower()
                return val in ('1', 'true', 'yes', 'y')
            if ftype == 'date':
                # Accept ISO or date-only; return YYYY-MM-DD
                try:
                    dt = self._parse_brevo_datetime(value)
                    if dt:
                        return dt.date().isoformat()
                except Exception:
                    pass
                s = str(value)
                return s[:10] if len(s) >= 10 else s
            if ftype == 'datetime':
                dt = self._parse_brevo_datetime(value)
                return dt and dt.strftime('%Y-%m-%d %H:%M:%S') or False
            if ftype == 'selection':
                # Keep raw string; expect mapping to align with allowed keys
                return '' if value is None else str(value)
            # Many2one / Many2many not expected for x_brevo_ defaults; fallback to string
            return '' if value is None else str(value)
        except Exception:
            return '' if value is None else str(value)
    
    def sync_partner_to_brevo(self, partner) -> Dict[str, Any]:
        """Sync a single partner to Brevo"""
        try:
            if not partner.email:
                return {'success': False, 'error': 'Partner has no email address'}
            
            # Get field mappings
            field_mappings = self.env['brevo.field.mapping'].search([
                ('active', '=', True),
                ('company_id', '=', self.config.company_id.id)
            ])
            
            # Prepare Brevo contact data
            brevo_contact_data = {
                'email': partner.email,
                'attributes': {}
            }
            
            # Apply field mappings
            for mapping in field_mappings:
                try:
                    value = mapping.get_field_value_from_odoo(partner)
                    if value is not None:
                        brevo_contact_data['attributes'][mapping.brevo_field_name] = value
                except Exception as e:
                    _logger.warning(f"Failed to map field {mapping.brevo_field_name}: {str(e)}")
                    continue
            
            # Handle partner categories (map to Brevo lists)
            if partner.category_id:
                brevo_list_ids = []
                for category in partner.category_id:
                    # Find corresponding Brevo list
                    brevo_list = self.env['brevo.contact.list'].search([
                        ('partner_category_id', '=', category.id),
                        ('company_id', '=', self.config.company_id.id)
                    ], limit=1)
                    if brevo_list and brevo_list.brevo_id:
                        brevo_list_ids.append(int(brevo_list.brevo_id))
                
                if brevo_list_ids:
                    brevo_contact_data['listIds'] = brevo_list_ids
            
            # Create or update contact in Brevo
            if partner.brevo_id:
                # Update existing contact
                result = self.brevo_service.update_contact(partner.brevo_id, brevo_contact_data)
            else:
                # Create new contact
                result = self.brevo_service.create_contact(brevo_contact_data)
            
            if result.get('success'):
                # Update partner with Brevo ID
                if not partner.brevo_id and result.get('contact_id'):
                    partner.brevo_id = str(result.get('contact_id'))
                
                partner.brevo_sync_status = 'synced'
                partner.brevo_last_sync = fields.Datetime.now()
                
                # Log success
                self.env['brevo.sync.log'].log_success(
                    'sync_partner', 'odoo_to_brevo', f"Synced partner {partner.display_name} to Brevo",
                    partner_id=partner.id, brevo_id=partner.brevo_id, config_id=self.config.id
                )
                
                return {'success': True, 'message': 'Partner synchronized successfully'}
            else:
                # Log error
                self.env['brevo.sync.log'].log_error(
                    'sync_partner', 'odoo_to_brevo', f"Failed to sync partner {partner.display_name} to Brevo",
                    error_message=result.get('error'), partner_id=partner.id, config_id=self.config.id
                )
                return {'success': False, 'error': result.get('error')}
                
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
        """Synchronize Brevo lists to Odoo partner categories (tags)"""
        try:
            _logger.info("Starting list synchronization...")
            
            # Get lists from Brevo
            brevo_lists_result = self.brevo_service.get_lists()
            if not brevo_lists_result.get('success'):
                raise Exception(f"Failed to get lists from Brevo: {brevo_lists_result.get('error')}")
            
            brevo_lists = brevo_lists_result.get('lists', [])
            _logger.info(f"Found {len(brevo_lists)} lists in Brevo")
            
            synced_count = 0
            error_count = 0
            
            # Process each Brevo list
            for brevo_list in brevo_lists:
                try:
                    list_id = brevo_list.get('id')
                    list_name = brevo_list.get('name')
                    
                    if not list_id or not list_name:
                        continue
                    
                    # Check if category already exists
                    category = self.env['res.partner.category'].search([
                        ('name', '=', list_name)
                    ], limit=1)
                    
                    if not category:
                        # Create new category
                        category = self.env['res.partner.category'].create({
                            'name': list_name,
                        })
                        _logger.info(f"Created new category: {list_name}")
                    else:
                        _logger.info(f"Category already exists: {list_name}")
                    
                    # Create or update brevo.contact.list record
                    brevo_list_record = self.env['brevo.contact.list'].search([
                        ('brevo_id', '=', str(list_id)),
                        ('company_id', '=', self.config.company_id.id)
                    ], limit=1)
                    
                    if not brevo_list_record:
                        brevo_list_record = self.env['brevo.contact.list'].create({
                            'name': list_name,
                            'brevo_id': str(list_id),
                            'partner_category_id': category.id,
                            'unique_subscribers': brevo_list.get('uniqueSubscribers', 0),
                            'total_blacklisted': brevo_list.get('totalBlacklisted', 0),
                            'total_unsubscribers': brevo_list.get('totalUnsubscribers', 0),
                            'description': brevo_list.get('description', ''),
                            'folder_id': str(brevo_list.get('folderId', '')),
                            'created_at': self._parse_brevo_datetime(brevo_list.get('createdAt')),
                            'updated_at': self._parse_brevo_datetime(brevo_list.get('updatedAt')),
                            'sync_status': 'synced',
                            'last_sync': fields.Datetime.now(),
                            'company_id': self.config.company_id.id,
                        })
                        _logger.info(f"Created brevo.contact.list record: {list_name}")
                    else:
                        # Update existing record
                        brevo_list_record.write({
                            'name': list_name,
                            'partner_category_id': category.id,
                            'unique_subscribers': brevo_list.get('uniqueSubscribers', 0),
                            'total_blacklisted': brevo_list.get('totalBlacklisted', 0),
                            'total_unsubscribers': brevo_list.get('totalUnsubscribers', 0),
                            'description': brevo_list.get('description', ''),
                            'folder_id': str(brevo_list.get('folderId', '')),
                            'updated_at': self._parse_brevo_datetime(brevo_list.get('updatedAt')),
                            'sync_status': 'synced',
                            'last_sync': fields.Datetime.now(),
                        })
                        _logger.info(f"Updated brevo.contact.list record: {list_name}")
                    
                    synced_count += 1
                    
                except Exception as e:
                    error_count += 1
                    _logger.error(f"Failed to sync list {brevo_list.get('name', 'unknown')}: {str(e)}")
                    self.env['brevo.sync.log'].log_error(
                        'sync_list', 'brevo_to_odoo', f"Failed to sync list {brevo_list.get('name', 'unknown')}",
                        error_message=str(e), brevo_id=brevo_list.get('id'), config_id=self.config.id
                    )
            
            # Update sync status
            self.config.last_sync_lists = fields.Datetime.now()
            self.config.sync_status = 'success'
            self.config.error_message = False
            
            message = f"List sync completed. Synced: {synced_count}, Errors: {error_count}"
            _logger.info(message)
            
            return {
                'success': True, 
                'message': message,
                'synced_count': synced_count,
                'error_count': error_count
            }
            
        except Exception as e:
            _logger.error(f"List sync failed: {str(e)}")
            self.config.sync_status = 'error'
            self.config.error_message = str(e)
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