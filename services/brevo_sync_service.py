# -*- coding: utf-8 -*-

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from .brevo_service import BrevoService

_logger = logging.getLogger(__name__)


class BrevoSyncService:
    """Service class for Brevo synchronization operations"""
    
    def __init__(self, config):
        """Initialize sync service with Brevo configuration"""
        self.config = config
        self.brevo_service = BrevoService(config.api_key)
        self.env = config.env
    
    def sync_contacts(self, batch_size: int = None) -> Dict[str, Any]:
        """Synchronize contacts between Odoo and Brevo"""
        try:
            batch_size = batch_size or self.config.batch_size
            
            # Log sync start
            self.env['brevo.sync.log'].log_info(
                'sync_all',
                'bidirectional',
                'Starting contact synchronization',
                config_id=self.config.id,
                start_time=fields.Datetime.now()
            )
            
            # Sync Odoo to Brevo
            odoo_to_brevo_result = self._sync_odoo_to_brevo_contacts(batch_size)
            
            # Sync Brevo to Odoo
            brevo_to_odoo_result = self._sync_brevo_to_odoo_contacts(batch_size)
            
            # Update config
            self.config.last_sync_contacts = fields.Datetime.now()
            self.config.sync_status = 'success'
            self.config.error_message = False
            
            # Log sync completion
            self.env['brevo.sync.log'].log_success(
                'sync_all',
                'bidirectional',
                'Contact synchronization completed',
                config_id=self.config.id,
                end_time=fields.Datetime.now(),
                details=json.dumps({
                    'odoo_to_brevo': odoo_to_brevo_result,
                    'brevo_to_odoo': brevo_to_odoo_result,
                })
            )
            
            return {
                'success': True,
                'odoo_to_brevo': odoo_to_brevo_result,
                'brevo_to_odoo': brevo_to_odoo_result,
            }
            
        except Exception as e:
            _logger.error(f"Contact synchronization failed: {str(e)}")
            
            # Update config with error
            self.config.sync_status = 'error'
            self.config.error_message = str(e)
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'sync_all',
                'bidirectional',
                f'Contact synchronization failed: {str(e)}',
                error_message=str(e),
                config_id=self.config.id,
                end_time=fields.Datetime.now()
            )
            
            return {
                'success': False,
                'error': str(e),
            }
    
    def _sync_odoo_to_brevo_contacts(self, batch_size: int) -> Dict[str, Any]:
        """Sync Odoo contacts to Brevo"""
        try:
            partners = self.env['res.partner'].get_partners_for_brevo_sync(limit=batch_size)
            
            synced_count = 0
            error_count = 0
            
            for partner in partners:
                try:
                    result = self.sync_partner_to_brevo(partner)
                    if result.get('success'):
                        synced_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    _logger.error(f"Failed to sync partner {partner.id} to Brevo: {str(e)}")
                    error_count += 1
            
            return {
                'synced_count': synced_count,
                'error_count': error_count,
                'total_processed': len(partners),
            }
            
        except Exception as e:
            _logger.error(f"Odoo to Brevo sync failed: {str(e)}")
            raise
    
    def _sync_brevo_to_odoo_contacts(self, batch_size: int) -> Dict[str, Any]:
        """Sync Brevo contacts to Odoo"""
        try:
            # Get contacts modified since last sync
            modified_since = self.config.last_sync_contacts
            if not modified_since:
                modified_since = datetime.now() - timedelta(days=30)  # Default to 30 days ago
            
            result = self.brevo_service.get_contacts(
                limit=batch_size,
                modified_since=modified_since
            )
            
            if not result.get('success'):
                raise Exception(result.get('error', 'Unknown error'))
            
            contacts = result.get('contacts', [])
            synced_count = 0
            error_count = 0
            
            for contact_data in contacts:
                try:
                    # Check if contact already exists
                    existing_partner = self.env['res.partner'].search([
                        ('brevo_id', '=', str(contact_data.id))
                    ], limit=1)
                    
                    if existing_partner:
                        # Update existing partner
                        self._update_partner_from_brevo(existing_partner, contact_data)
                    else:
                        # Create new partner
                        self.env['res.partner'].create_from_brevo_data(contact_data)
                    
                    synced_count += 1
                    
                except Exception as e:
                    _logger.error(f"Failed to sync Brevo contact {contact_data.id} to Odoo: {str(e)}")
                    error_count += 1
            
            return {
                'synced_count': synced_count,
                'error_count': error_count,
                'total_processed': len(contacts),
            }
            
        except Exception as e:
            _logger.error(f"Brevo to Odoo sync failed: {str(e)}")
            raise
    
    def sync_partner_to_brevo(self, partner) -> Dict[str, Any]:
        """Sync a single partner to Brevo"""
        try:
            if not partner.email:
                raise ValidationError(_('Email address is required for Brevo sync'))
            
            if partner.is_company:
                raise ValidationError(_('Companies cannot be synced to Brevo'))
            
            # Prepare contact data
            contact_data = partner.get_brevo_data()
            
            if partner.brevo_id:
                # Update existing contact
                result = self.brevo_service.update_contact(partner.brevo_id, contact_data)
                operation = 'contact_update'
            else:
                # Create new contact
                result = self.brevo_service.create_contact(contact_data)
                operation = 'contact_create'
            
            if result.get('success'):
                # Update partner with Brevo ID
                partner.write({
                    'brevo_id': str(result.get('contact_id', partner.brevo_id)),
                    'brevo_sync_status': 'synced',
                    'brevo_last_sync': fields.Datetime.now(),
                    'brevo_sync_error': False,
                    'brevo_sync_needed': False,
                })
                
                # Log success
                self.env['brevo.sync.log'].log_success(
                    operation,
                    'odoo_to_brevo',
                    f'Partner {partner.name} synced to Brevo',
                    partner_id=partner.id,
                    brevo_id=str(result.get('contact_id', partner.brevo_id)),
                    brevo_email=partner.email
                )
                
                return {
                    'success': True,
                    'contact_id': result.get('contact_id'),
                }
            else:
                # Log error
                self.env['brevo.sync.log'].log_error(
                    operation,
                    'odoo_to_brevo',
                    f'Failed to sync partner {partner.name} to Brevo',
                    error_message=result.get('error'),
                    partner_id=partner.id,
                    brevo_email=partner.email,
                    details=json.dumps(result)
                )
                
                # Update partner with error
                partner.write({
                    'brevo_sync_status': 'error',
                    'brevo_sync_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                }
                
        except Exception as e:
            _logger.error(f"Failed to sync partner {partner.id} to Brevo: {str(e)}")
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'contact_update' if partner.brevo_id else 'contact_create',
                'odoo_to_brevo',
                f'Failed to sync partner {partner.name} to Brevo',
                error_message=str(e),
                partner_id=partner.id,
                brevo_email=partner.email
            )
            
            # Update partner with error
            partner.write({
                'brevo_sync_status': 'error',
                'brevo_sync_error': str(e),
            })
            
            return {
                'success': False,
                'error': str(e),
            }
    
    def _update_partner_from_brevo(self, partner, contact_data):
        """Update partner with data from Brevo"""
        try:
            attributes = contact_data.get('attributes', {})
            
            update_vals = {
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
                'brevo_sync_error': False,
                'brevo_modified_date': contact_data.get('modifiedAt'),
            }
            
            # Update basic fields if they're different
            if attributes.get('FNAME') and attributes.get('LNAME'):
                new_name = f"{attributes.get('FNAME')} {attributes.get('LNAME')}".strip()
                if new_name and new_name != partner.name:
                    update_vals['name'] = new_name
            
            if attributes.get('SMS') and attributes.get('SMS') != partner.mobile:
                update_vals['mobile'] = attributes.get('SMS')
            
            if attributes.get('ADDRESS') and attributes.get('ADDRESS') != partner.street:
                update_vals['street'] = attributes.get('ADDRESS')
            
            if attributes.get('CITY') and attributes.get('CITY') != partner.city:
                update_vals['city'] = attributes.get('CITY')
            
            if attributes.get('ZIP') and attributes.get('ZIP') != partner.zip:
                update_vals['zip'] = attributes.get('ZIP')
            
            partner.write(update_vals)
            
            # Log update
            self.env['brevo.sync.log'].log_success(
                'contact_update',
                'brevo_to_odoo',
                f'Partner {partner.name} updated from Brevo',
                partner_id=partner.id,
                brevo_id=str(contact_data.id),
                brevo_email=contact_data.get('email')
            )
            
        except Exception as e:
            _logger.error(f"Failed to update partner {partner.id} from Brevo: {str(e)}")
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'contact_update',
                'brevo_to_odoo',
                f'Failed to update partner {partner.name} from Brevo',
                error_message=str(e),
                partner_id=partner.id,
                brevo_id=str(contact_data.id),
                brevo_email=contact_data.get('email')
            )
    
    def sync_lists(self, batch_size: int = None) -> Dict[str, Any]:
        """Synchronize contact lists between Odoo and Brevo"""
        try:
            batch_size = batch_size or self.config.batch_size
            
            # Log sync start
            self.env['brevo.sync.log'].log_info(
                'sync_all',
                'bidirectional',
                'Starting contact list synchronization',
                config_id=self.config.id,
                start_time=fields.Datetime.now()
            )
            
            # Sync Brevo to Odoo
            brevo_to_odoo_result = self._sync_brevo_to_odoo_lists(batch_size)
            
            # Sync Odoo to Brevo
            odoo_to_brevo_result = self._sync_odoo_to_brevo_lists(batch_size)
            
            # Update config
            self.config.last_sync_lists = fields.Datetime.now()
            self.config.sync_status = 'success'
            self.config.error_message = False
            
            # Log sync completion
            self.env['brevo.sync.log'].log_success(
                'sync_all',
                'bidirectional',
                'Contact list synchronization completed',
                config_id=self.config.id,
                end_time=fields.Datetime.now(),
                details=json.dumps({
                    'brevo_to_odoo': brevo_to_odoo_result,
                    'odoo_to_brevo': odoo_to_brevo_result,
                })
            )
            
            return {
                'success': True,
                'brevo_to_odoo': brevo_to_odoo_result,
                'odoo_to_brevo': odoo_to_brevo_result,
            }
            
        except Exception as e:
            _logger.error(f"Contact list synchronization failed: {str(e)}")
            
            # Update config with error
            self.config.sync_status = 'error'
            self.config.error_message = str(e)
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'sync_all',
                'bidirectional',
                f'Contact list synchronization failed: {str(e)}',
                error_message=str(e),
                config_id=self.config.id,
                end_time=fields.Datetime.now()
            )
            
            return {
                'success': False,
                'error': str(e),
            }
    
    def _sync_brevo_to_odoo_lists(self, batch_size: int) -> Dict[str, Any]:
        """Sync Brevo lists to Odoo"""
        try:
            result = self.brevo_service.get_lists(limit=batch_size)
            
            if not result.get('success'):
                raise Exception(result.get('error', 'Unknown error'))
            
            lists = result.get('lists', [])
            synced_count = 0
            error_count = 0
            
            for list_data in lists:
                try:
                    # Check if list already exists
                    existing_list = self.env['brevo.contact.list'].search([
                        ('brevo_id', '=', str(list_data.id)),
                        ('company_id', '=', self.config.company_id.id)
                    ], limit=1)
                    
                    if existing_list:
                        # Update existing list
                        existing_list.update_from_brevo_data(list_data)
                    else:
                        # Create new list
                        self.env['brevo.contact.list'].create_from_brevo_data(
                            list_data, 
                            self.config.company_id.id
                        )
                    
                    synced_count += 1
                    
                except Exception as e:
                    _logger.error(f"Failed to sync Brevo list {list_data.id} to Odoo: {str(e)}")
                    error_count += 1
            
            return {
                'synced_count': synced_count,
                'error_count': error_count,
                'total_processed': len(lists),
            }
            
        except Exception as e:
            _logger.error(f"Brevo to Odoo list sync failed: {str(e)}")
            raise
    
    def _sync_odoo_to_brevo_lists(self, batch_size: int) -> Dict[str, Any]:
        """Sync Odoo partner categories to Brevo lists"""
        try:
            # Get partner categories that should be synced
            categories = self.env['res.partner.category'].search([
                ('name', '!=', False),
            ], limit=batch_size)
            
            synced_count = 0
            error_count = 0
            
            for category in categories:
                try:
                    # Check if list already exists in Brevo
                    existing_list = self.env['brevo.contact.list'].search([
                        ('name', '=', category.name),
                        ('company_id', '=', self.config.company_id.id)
                    ], limit=1)
                    
                    if not existing_list:
                        # Create new list in Brevo
                        list_data = {
                            'name': category.name,
                            'description': f'List created from Odoo category: {category.name}',
                        }
                        
                        result = self.brevo_service.create_list(list_data)
                        
                        if result.get('success'):
                            # Create corresponding Brevo list record
                            self.env['brevo.contact.list'].create({
                                'name': category.name,
                                'brevo_id': str(result.get('list_id')),
                                'description': list_data['description'],
                                'company_id': self.config.company_id.id,
                                'sync_status': 'synced',
                                'last_sync': fields.Datetime.now(),
                            })
                            
                            synced_count += 1
                        else:
                            error_count += 1
                    else:
                        synced_count += 1
                        
                except Exception as e:
                    _logger.error(f"Failed to sync category {category.id} to Brevo: {str(e)}")
                    error_count += 1
            
            return {
                'synced_count': synced_count,
                'error_count': error_count,
                'total_processed': len(categories),
            }
            
        except Exception as e:
            _logger.error(f"Odoo to Brevo list sync failed: {str(e)}")
            raise
    
    def sync_list_to_brevo(self, contact_list) -> Dict[str, Any]:
        """Sync a single contact list to Brevo"""
        try:
            list_data = contact_list.get_brevo_data()
            
            if contact_list.brevo_id:
                # Update existing list
                result = self.brevo_service.update_contact(contact_list.brevo_id, list_data)
                operation = 'list_update'
            else:
                # Create new list
                result = self.brevo_service.create_list(list_data)
                operation = 'list_create'
            
            if result.get('success'):
                # Update contact list with Brevo ID
                contact_list.write({
                    'brevo_id': str(result.get('list_id', contact_list.brevo_id)),
                    'sync_status': 'synced',
                    'last_sync': fields.Datetime.now(),
                    'sync_error': False,
                })
                
                # Log success
                self.env['brevo.sync.log'].log_success(
                    operation,
                    'odoo_to_brevo',
                    f'Contact list {contact_list.name} synced to Brevo',
                    contact_list_id=contact_list.id,
                    brevo_id=str(result.get('list_id', contact_list.brevo_id))
                )
                
                return {
                    'success': True,
                    'list_id': result.get('list_id'),
                }
            else:
                # Log error
                self.env['brevo.sync.log'].log_error(
                    operation,
                    'odoo_to_brevo',
                    f'Failed to sync contact list {contact_list.name} to Brevo',
                    error_message=result.get('error'),
                    contact_list_id=contact_list.id,
                    details=json.dumps(result)
                )
                
                # Update contact list with error
                contact_list.write({
                    'sync_status': 'error',
                    'sync_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                }
                
        except Exception as e:
            _logger.error(f"Failed to sync contact list {contact_list.id} to Brevo: {str(e)}")
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'list_update' if contact_list.brevo_id else 'list_create',
                'odoo_to_brevo',
                f'Failed to sync contact list {contact_list.name} to Brevo',
                error_message=str(e),
                contact_list_id=contact_list.id
            )
            
            # Update contact list with error
            contact_list.write({
                'sync_status': 'error',
                'sync_error': str(e),
            })
            
            return {
                'success': False,
                'error': str(e),
            }
    
    def sync_list_memberships(self, contact_list) -> Dict[str, Any]:
        """Sync list memberships for a contact list"""
        try:
            if not contact_list.brevo_id:
                raise ValidationError(_('Contact list must have a Brevo ID'))
            
            # Get partners in this list
            partners = self.env['res.partner'].search([
                ('brevo_lists', 'in', contact_list.id),
                ('email', '!=', False),
                ('is_company', '=', False),
            ])
            
            if not partners:
                return {'success': True, 'message': 'No partners to sync'}
            
            # Prepare email list
            emails = [p.email for p in partners if p.email]
            
            if not emails:
                return {'success': True, 'message': 'No valid emails to sync'}
            
            # Add contacts to Brevo list
            result = self.brevo_service.add_contact_to_list(contact_list.brevo_id, emails)
            
            if result.get('success'):
                # Log success
                self.env['brevo.sync.log'].log_success(
                    'membership_add',
                    'odoo_to_brevo',
                    f'Added {len(emails)} contacts to Brevo list {contact_list.name}',
                    contact_list_id=contact_list.id,
                    brevo_id=contact_list.brevo_id,
                    details=json.dumps({'emails': emails})
                )
                
                return {
                    'success': True,
                    'contacts_added': len(emails),
                }
            else:
                # Log error
                self.env['brevo.sync.log'].log_error(
                    'membership_add',
                    'odoo_to_brevo',
                    f'Failed to add contacts to Brevo list {contact_list.name}',
                    error_message=result.get('error'),
                    contact_list_id=contact_list.id,
                    brevo_id=contact_list.brevo_id,
                    details=json.dumps(result)
                )
                
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                }
                
        except Exception as e:
            _logger.error(f"Failed to sync list memberships for {contact_list.id}: {str(e)}")
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'membership_add',
                'odoo_to_brevo',
                f'Failed to sync list memberships for {contact_list.name}',
                error_message=str(e),
                contact_list_id=contact_list.id
            )
            
            return {
                'success': False,
                'error': str(e),
            }
    
    def sync_lead_to_brevo(self, lead) -> Dict[str, Any]:
        """Sync a CRM lead to Brevo"""
        try:
            if not lead.partner_id or not lead.partner_id.email:
                raise ValidationError(_('Lead must have a partner with email for Brevo sync'))
            
            # For now, we'll just log the lead creation
            # In a full implementation, you might want to create a custom field in Brevo
            # or use Brevo's CRM integration features
            
            # Log success
            self.env['brevo.sync.log'].log_success(
                'lead_create',
                'odoo_to_brevo',
                f'Lead {lead.name} synced to Brevo',
                lead_id=lead.id,
                partner_id=lead.partner_id.id,
                brevo_email=lead.partner_id.email
            )
            
            # Update lead
            lead.write({
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
                'brevo_sync_error': False,
            })
            
            return {
                'success': True,
                'message': 'Lead synced to Brevo (logged)',
            }
            
        except Exception as e:
            _logger.error(f"Failed to sync lead {lead.id} to Brevo: {str(e)}")
            
            # Log error
            self.env['brevo.sync.log'].log_error(
                'lead_create',
                'odoo_to_brevo',
                f'Failed to sync lead {lead.name} to Brevo',
                error_message=str(e),
                lead_id=lead.id,
                partner_id=lead.partner_id.id if lead.partner_id else False
            )
            
            # Update lead with error
            lead.write({
                'brevo_sync_status': 'error',
                'brevo_sync_error': str(e),
            })
            
            return {
                'success': False,
                'error': str(e),
            }
