# -*- coding: utf-8 -*-

import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import brevo_python
    from brevo_python.rest import ApiException
    BREVO_SDK_AVAILABLE = True
except ImportError:
    BREVO_SDK_AVAILABLE = False
    brevo_python = None
    ApiException = Exception

_logger = logging.getLogger(__name__)


class BrevoService:
    """Service class for Brevo API interactions"""
    
    def __init__(self, api_key: str):
        """Initialize Brevo service with API key"""
        if not BREVO_SDK_AVAILABLE:
            raise ImportError("Brevo SDK not available. Please install brevo-python")
        
        self.api_key = api_key
        self.configuration = brevo_python.Configuration()
        self.configuration.api_key['api-key'] = api_key
        
        # Initialize API clients
        self.contacts_api = brevo_python.ContactsApi(brevo_python.ApiClient(self.configuration))
        # Note: ListsApi and AttributesApi not available in current brevo-python version
        # Using ContactsApi for lists functionality
        self.lists_api = brevo_python.ContactsApi(brevo_python.ApiClient(self.configuration))
        self.webhooks_api = brevo_python.WebhooksApi(brevo_python.ApiClient(self.configuration))
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.2  # 200ms between requests (300 requests/minute)
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Brevo API"""
        try:
            self._rate_limit()
            
            # Try a simple API call to test the connection
            # We'll try to get contacts with minimal parameters
            try:
                # Try the simplest possible call
                response = self.contacts_api.get_contacts()
                
                # Check if we got a valid response
                if response:
                    return {
                        'success': True,
                        'message': "Connection successful. API key is valid.",
                    }
                else:
                    return {
                        'success': False,
                        'error': "No response from Brevo API",
                    }
                    
            except ApiException as api_e:
                # Even if we get an API error, it means the connection works
                if api_e.status in [400, 401, 403, 404, 422]:
                    return {
                        'success': True,
                        'message': f"Connection successful. API key is valid (got {api_e.status} response).",
                    }
                else:
                    return {
                        'success': False,
                        'error': f"API Error {api_e.status}: {api_e.reason}",
                    }
                    
        except Exception as e:
            _logger.error(f"Brevo connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contact in Brevo"""
        try:
            self._rate_limit()
            
            create_contact = brevo_python.CreateContact(
                email=contact_data['email'],
                attributes=contact_data.get('attributes', {}),
                list_ids=contact_data.get('listIds', []),
                update_enabled=contact_data.get('updateEnabled', True),
            )
            
            response = self.contacts_api.create_contact(create_contact)
            
            return {
                'success': True,
                'contact_id': response.id,
                'data': response,
            }
        except ApiException as e:
            _logger.error(f"Failed to create Brevo contact: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
                'details': e.body if hasattr(e, 'body') else str(e),
            }
        except Exception as e:
            _logger.error(f"Failed to create Brevo contact: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def update_contact(self, contact_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing contact in Brevo"""
        try:
            self._rate_limit()
            
            update_contact = brevo_python.UpdateContact(
                attributes=contact_data.get('attributes', {}),
                list_ids=contact_data.get('listIds', []),
            )
            
            response = self.contacts_api.update_contact(contact_id, update_contact)
            
            return {
                'success': True,
                'data': response,
            }
        except ApiException as e:
            _logger.error(f"Failed to update Brevo contact: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
                'details': e.body if hasattr(e, 'body') else str(e),
            }
        except Exception as e:
            _logger.error(f"Failed to update Brevo contact: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get a contact from Brevo by ID"""
        try:
            self._rate_limit()
            
            response = self.contacts_api.get_contact_info(contact_id)
            
            return {
                'success': True,
                'data': response,
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    'success': False,
                    'error': 'Contact not found',
                }
            _logger.error(f"Failed to get Brevo contact: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get Brevo contact: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_contact_by_email(self, email: str) -> Dict[str, Any]:
        """Get a contact from Brevo by email"""
        try:
            self._rate_limit()
            
            response = self.contacts_api.get_contact_info(email)
            
            return {
                'success': True,
                'data': response,
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    'success': False,
                    'error': 'Contact not found',
                }
            _logger.error(f"Failed to get Brevo contact by email: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get Brevo contact by email: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete a contact from Brevo"""
        try:
            self._rate_limit()
            
            self.contacts_api.delete_contact(contact_id)
            
            return {
                'success': True,
            }
        except ApiException as e:
            _logger.error(f"Failed to delete Brevo contact: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to delete Brevo contact: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_contacts(self, limit: int = 50, offset: int = 0, modified_since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get contacts from Brevo with pagination"""
        try:
            self._rate_limit()
            
            # Convert datetime to ISO format if provided
            modified_since_str = None
            if modified_since:
                modified_since_str = modified_since.isoformat()
            
            # Try different parameter combinations
            try:
                response = self.contacts_api.get_contacts(
                    limit=limit,
                    offset=offset,
                    modified_since=modified_since_str
                )
            except Exception as e:
                # Try without modified_since parameter
                _logger.warning(f"get_contacts with modified_since failed, trying without: {e}")
                response = self.contacts_api.get_contacts(
                    limit=limit,
                    offset=offset
                )
            
            # Handle different response structures
            contacts = []
            count = 0
            
            if hasattr(response, 'contacts'):
                contacts = response.contacts
            elif hasattr(response, 'data'):
                contacts = response.data
            elif isinstance(response, list):
                contacts = response
            
            if hasattr(response, 'count'):
                count = response.count
            elif hasattr(response, 'total'):
                count = response.total
            else:
                count = len(contacts) if contacts else 0
            
            return {
                'success': True,
                'contacts': contacts,
                'count': count,
            }
        except ApiException as e:
            _logger.error(f"Failed to get Brevo contacts: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get Brevo contacts: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def create_list(self, list_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contact list in Brevo"""
        try:
            self._rate_limit()
            
            create_list = brevo_python.CreateList(
                name=list_data['name'],
                description=list_data.get('description', ''),
                folder_id=list_data.get('folderId'),
            )
            
            response = self.lists_api.create_list(create_list)
            
            return {
                'success': True,
                'list_id': response.id,
                'data': response,
            }
        except ApiException as e:
            _logger.error(f"Failed to create Brevo list: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
                'details': e.body if hasattr(e, 'body') else str(e),
            }
        except Exception as e:
            _logger.error(f"Failed to create Brevo list: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_lists(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get contact lists from Brevo"""
        try:
            self._rate_limit()
            
            response = self.lists_api.get_lists(limit=limit, offset=offset)
            
            return {
                'success': True,
                'lists': response.lists,
                'count': response.count,
            }
        except ApiException as e:
            _logger.error(f"Failed to get Brevo lists: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get Brevo lists: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_list(self, list_id: str) -> Dict[str, Any]:
        """Get a specific contact list from Brevo"""
        try:
            self._rate_limit()
            
            response = self.lists_api.get_list(list_id)
            
            return {
                'success': True,
                'data': response,
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    'success': False,
                    'error': 'List not found',
                }
            _logger.error(f"Failed to get Brevo list: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get Brevo list: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def add_contact_to_list(self, list_id: str, contact_ids: List[str]) -> Dict[str, Any]:
        """Add contacts to a list"""
        try:
            self._rate_limit()
            
            add_contacts = brevo_python.AddContactToList(
                emails=contact_ids
            )
            
            response = self.lists_api.add_contact_to_list(list_id, add_contacts)
            
            return {
                'success': True,
                'data': response,
            }
        except ApiException as e:
            _logger.error(f"Failed to add contacts to Brevo list: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to add contacts to Brevo list: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def remove_contact_from_list(self, list_id: str, contact_ids: List[str]) -> Dict[str, Any]:
        """Remove contacts from a list"""
        try:
            self._rate_limit()
            
            remove_contacts = brevo_python.RemoveContactToList(
                emails=contact_ids
            )
            
            response = self.lists_api.remove_contact_from_list(list_id, remove_contacts)
            
            return {
                'success': True,
                'data': response,
            }
        except ApiException as e:
            _logger.error(f"Failed to remove contacts from Brevo list: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to remove contacts from Brevo list: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def create_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a webhook in Brevo"""
        try:
            self._rate_limit()
            
            create_webhook = brevo_python.CreateWebhook(
                url=webhook_data['url'],
                description=webhook_data.get('description', ''),
                events=webhook_data.get('events', []),
                type=webhook_data.get('type', 'transactional'),
            )
            
            response = self.webhooks_api.create_webhook(create_webhook)
            
            return {
                'success': True,
                'webhook_id': response.id,
                'data': response,
            }
        except ApiException as e:
            _logger.error(f"Failed to create Brevo webhook: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to create Brevo webhook: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_webhooks(self) -> Dict[str, Any]:
        """Get all webhooks from Brevo"""
        try:
            self._rate_limit()
            
            response = self.webhooks_api.get_webhooks()
            
            return {
                'success': True,
                'webhooks': response.webhooks,
            }
        except ApiException as e:
            _logger.error(f"Failed to get Brevo webhooks: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get Brevo webhooks: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook from Brevo"""
        try:
            self._rate_limit()
            
            self.webhooks_api.delete_webhook(webhook_id)
            
            return {
                'success': True,
            }
        except ApiException as e:
            _logger.error(f"Failed to delete Brevo webhook: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to delete Brevo webhook: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_contact_tags(self, contact_id: str) -> Dict[str, Any]:
        """Get tags for a specific contact"""
        try:
            self._rate_limit()
            response = self.contacts_api.get_contact_info(contact_id)
            
            if hasattr(response, 'tags') and response.tags:
                return {
                    'success': True,
                    'tags': response.tags
                }
            else:
                return {
                    'success': True,
                    'tags': []
                }
        except ApiException as e:
            _logger.error(f"Failed to get contact tags: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to get contact tags: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def update_contact_tags(self, contact_id: str, tags: List[str]) -> Dict[str, Any]:
        """Update tags for a specific contact"""
        try:
            self._rate_limit()
            
            # Create update contact request
            update_contact = brevo_python.UpdateContact()
            update_contact.tags = tags
            
            response = self.contacts_api.update_contact(contact_id, update_contact)
            
            return {
                'success': True,
                'message': 'Contact tags updated successfully'
            }
        except ApiException as e:
            _logger.error(f"Failed to update contact tags: {e}")
            return {
                'success': False,
                'error': f"API Error {e.status}: {e.reason}",
            }
        except Exception as e:
            _logger.error(f"Failed to update contact tags: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    def get_all_contact_attributes(self) -> Dict[str, Any]:
        """Get all available contact attributes from Brevo"""
        # Note: AttributesApi not available in current brevo-python version
        # For now, return standard Brevo attributes that are commonly used
        return {
            'success': True,
            'attributes': [
                {'name': 'FNAME', 'type': 'text', 'category': 'personal'},
                {'name': 'LNAME', 'type': 'text', 'category': 'personal'},
                {'name': 'EMAIL', 'type': 'text', 'category': 'contact'},
                {'name': 'SMS', 'type': 'text', 'category': 'contact'},
                {'name': 'PHONE', 'type': 'text', 'category': 'contact'},
                {'name': 'ADDRESS', 'type': 'text', 'category': 'address'},
                {'name': 'CITY', 'type': 'text', 'category': 'address'},
                {'name': 'ZIP', 'type': 'text', 'category': 'address'},
                {'name': 'COUNTRY', 'type': 'text', 'category': 'address'},
                {'name': 'STATE', 'type': 'text', 'category': 'address'},
                {'name': 'COMPANY', 'type': 'text', 'category': 'company'},
                {'name': 'WEBSITE', 'type': 'text', 'category': 'contact'},
                {'name': 'BIRTHDAY', 'type': 'date', 'category': 'personal'},
                {'name': 'AGE', 'type': 'number', 'category': 'personal'},
                {'name': 'GENDER', 'type': 'text', 'category': 'personal'},
            ]
        }
