# -*- coding: utf-8 -*-

import logging
import json
import hmac
import hashlib
from datetime import datetime

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BrevoWebhookController(http.Controller):
    """Controller for handling Brevo webhooks"""
    
    @http.route('/brevo/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def brevo_webhook(self):
        """Handle incoming webhooks from Brevo"""
        try:
            # Get the raw request data
            raw_data = request.httprequest.get_data()
            
            # Verify webhook signature if configured
            if not self._verify_webhook_signature(raw_data):
                _logger.warning("Brevo webhook signature verification failed")
                return {'status': 'error', 'message': 'Invalid signature'}
            
            # Parse JSON data
            try:
                webhook_data = json.loads(raw_data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                _logger.error(f"Failed to parse Brevo webhook data: {str(e)}")
                return {'status': 'error', 'message': 'Invalid JSON data'}
            
            # Log webhook receipt
            request.env['brevo.sync.log'].log_info(
                'webhook',
                'brevo_to_odoo',
                f'Received webhook from Brevo: {webhook_data.get("event", "unknown")}',
                details=json.dumps(webhook_data)
            )
            
            # Process webhook based on event type
            result = self._process_webhook(webhook_data)
            
            if result.get('success'):
                return {'status': 'success', 'message': 'Webhook processed successfully'}
            else:
                return {'status': 'error', 'message': result.get('error', 'Unknown error')}
                
        except Exception as e:
            _logger.error(f"Brevo webhook processing failed: {str(e)}")
            
            # Log error
            try:
                request.env['brevo.sync.log'].log_error(
                    'webhook',
                    'brevo_to_odoo',
                    f'Webhook processing failed: {str(e)}',
                    error_message=str(e)
                )
            except:
                pass  # Avoid recursive errors
            
            return {'status': 'error', 'message': 'Internal server error'}

    @http.route('/brevo/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def brevo_webhook_http(self, **kwargs):
        """HTTP fallback: accept plain JSON body or form-encoded 'payload' without auth"""
        try:
            raw_data = request.httprequest.get_data()
            if not self._verify_webhook_signature(raw_data):
                _logger.warning("Brevo webhook signature verification failed (http)")
                return request.make_json_response({'status': 'error', 'message': 'Invalid signature'}, status=400)

            body = raw_data.decode('utf-8') or ''
            try:
                webhook_data = json.loads(body)
            except Exception:
                # Try form key
                payload = kwargs.get('payload') or request.params.get('payload')
                webhook_data = json.loads(payload) if payload else {}

            if not webhook_data:
                return request.make_json_response({'status': 'error', 'message': 'Empty body'}, status=400)

            result = self._process_webhook(webhook_data)
            status = 200 if result.get('success') else 400
            return request.make_json_response({'status': 'success' if status == 200 else 'error', 'message': result.get('message') or result.get('error')}, status=status)
        except Exception as e:
            _logger.error(f"Brevo webhook (http) failed: {str(e)}")
            return request.make_json_response({'status': 'error', 'message': 'Internal server error'}, status=500)

    @http.route('/brevo/booking', type='json', auth='public', methods=['POST'], csrf=False)
    def brevo_booking_json(self):
        """Dedicated booking endpoint without auth"""
        try:
            raw = request.httprequest.get_data()
            if not self._verify_webhook_signature(raw):
                _logger.warning("Brevo booking signature verification failed")
                return {'status': 'error', 'message': 'Invalid signature'}
            data = json.loads(raw.decode('utf-8'))
            # Ensure env user is public for anonymous calls
            request.env = request.env(user=request.env.ref('base.public_user').id)
            result = self._handle_booking_webhook(data.get('event') or 'booking.created', data.get('data') or data)
            return {'status': 'success' if result.get('success') else 'error', 'message': result.get('message') or result.get('error')}
        except Exception as e:
            _logger.error(f"Brevo booking (json) failed: {str(e)}")
            return {'status': 'error', 'message': 'Internal server error'}

    @http.route('/brevo/booking', type='http', auth='public', methods=['POST'], csrf=False)
    def brevo_booking_http(self, **kwargs):
        """HTTP fallback booking endpoint without auth"""
        try:
            raw = request.httprequest.get_data()
            if not self._verify_webhook_signature(raw):
                _logger.warning("Brevo booking signature verification failed (http)")
                return request.make_json_response({'status': 'error', 'message': 'Invalid signature'}, status=400)
            body = raw.decode('utf-8') or ''
            try:
                data = json.loads(body)
            except Exception:
                payload = kwargs.get('payload') or request.params.get('payload')
                data = json.loads(payload) if payload else {}
            request.env = request.env(user=request.env.ref('base.public_user').id)
            result = self._handle_booking_webhook(data.get('event') or 'booking.created', data.get('data') or data)
            return request.make_json_response({'status': 'success' if result.get('success') else 'error', 'message': result.get('message') or result.get('error')}, status=200 if result.get('success') else 400)
        except Exception as e:
            _logger.error(f"Brevo booking (http) failed: {str(e)}")
            return request.make_json_response({'status': 'error', 'message': 'Internal server error'}, status=500)
    
    def _verify_webhook_signature(self, raw_data):
        """Verify webhook signature from Brevo (optional). If brevo.webhook_require_signature is False or not set, skip verification."""
        try:
            ICP = request.env['ir.config_parameter'].sudo()
            require_sig = ICP.get_param('brevo.webhook_require_signature', default='0') in ('1', 'true', 'True', True)
            if not require_sig:
                return True

            webhook_secret = ICP.get_param('brevo.webhook_secret')
            if not webhook_secret:
                return True
            
            # Get signature from headers
            signature = request.httprequest.headers.get('X-Brevo-Signature')
            if not signature:
                return False
            
            # Verify signature
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                raw_data,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            _logger.error(f"Webhook signature verification failed: {str(e)}")
            return False
    
    def _process_webhook(self, webhook_data):
        """Process webhook data based on event type"""
        try:
            event_type = webhook_data.get('event')
            event_data = webhook_data.get('data', {})
            
            if not event_type:
                return {'success': False, 'error': 'No event type specified'}
            
            # Route to appropriate handler
            if event_type.startswith('contact.'):
                return self._handle_contact_webhook(event_type, event_data)
            elif event_type.startswith('list.'):
                return self._handle_list_webhook(event_type, event_data)
            elif event_type.startswith('booking.'):
                return self._handle_booking_webhook(event_type, event_data)
            else:
                _logger.warning(f"Unhandled webhook event type: {event_type}")
                return {'success': True, 'message': f'Unhandled event type: {event_type}'}
                
        except Exception as e:
            _logger.error(f"Webhook processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_contact_webhook(self, event_type, event_data):
        """Handle contact-related webhooks"""
        try:
            if event_type == 'contact.created':
                return self._handle_contact_created(event_data)
            elif event_type == 'contact.updated':
                return self._handle_contact_updated(event_data)
            elif event_type == 'contact.deleted':
                return self._handle_contact_deleted(event_data)
            else:
                return {'success': True, 'message': f'Unhandled contact event: {event_type}'}
                
        except Exception as e:
            _logger.error(f"Contact webhook handling failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_contact_created(self, event_data):
        """Handle contact creation webhook"""
        try:
            # Check if contact already exists
            existing_partner = request.env['res.partner'].search([
                ('brevo_id', '=', str(event_data.get('id')))
            ], limit=1)
            
            if existing_partner:
                # Update existing partner
                self._update_partner_from_brevo_data(existing_partner, event_data)
                return {'success': True, 'message': 'Existing partner updated'}
            else:
                # Create new partner
                partner = request.env['res.partner'].create_from_brevo_data(event_data)
                return {'success': True, 'message': f'New partner created: {partner.name}'}
                
        except Exception as e:
            _logger.error(f"Contact creation webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_contact_updated(self, event_data):
        """Handle contact update webhook"""
        try:
            # Find existing partner
            partner = request.env['res.partner'].search([
                ('brevo_id', '=', str(event_data.get('id')))
            ], limit=1)
            
            if partner:
                self._update_partner_from_brevo_data(partner, event_data)
                return {'success': True, 'message': f'Partner updated: {partner.name}'}
            else:
                # Create new partner if not found
                partner = request.env['res.partner'].create_from_brevo_data(event_data)
                return {'success': True, 'message': f'New partner created: {partner.name}'}
                
        except Exception as e:
            _logger.error(f"Contact update webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_contact_deleted(self, event_data):
        """Handle contact deletion webhook"""
        try:
            # Find existing partner
            partner = request.env['res.partner'].search([
                ('brevo_id', '=', str(event_data.get('id')))
            ], limit=1)
            
            if partner:
                # Mark partner as archived instead of deleting
                partner.write({'active': False})
                return {'success': True, 'message': f'Partner archived: {partner.name}'}
            else:
                return {'success': True, 'message': 'Partner not found'}
                
        except Exception as e:
            _logger.error(f"Contact deletion webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_list_webhook(self, event_type, event_data):
        """Handle list-related webhooks"""
        try:
            if event_type == 'list.created':
                return self._handle_list_created(event_data)
            elif event_type == 'list.updated':
                return self._handle_list_updated(event_data)
            elif event_type == 'list.deleted':
                return self._handle_list_deleted(event_data)
            else:
                return {'success': True, 'message': f'Unhandled list event: {event_type}'}
                
        except Exception as e:
            _logger.error(f"List webhook handling failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_list_created(self, event_data):
        """Handle list creation webhook"""
        try:
            # Check if list already exists
            existing_list = request.env['brevo.contact.list'].search([
                ('brevo_id', '=', str(event_data.get('id')))
            ], limit=1)
            
            if existing_list:
                # Update existing list
                existing_list.update_from_brevo_data(event_data)
                return {'success': True, 'message': 'Existing list updated'}
            else:
                # Create new list
                contact_list = request.env['brevo.contact.list'].create_from_brevo_data(event_data)
                return {'success': True, 'message': f'New list created: {contact_list.name}'}
                
        except Exception as e:
            _logger.error(f"List creation webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_list_updated(self, event_data):
        """Handle list update webhook"""
        try:
            # Find existing list
            contact_list = request.env['brevo.contact.list'].search([
                ('brevo_id', '=', str(event_data.get('id')))
            ], limit=1)
            
            if contact_list:
                contact_list.update_from_brevo_data(event_data)
                return {'success': True, 'message': f'List updated: {contact_list.name}'}
            else:
                # Create new list if not found
                contact_list = request.env['brevo.contact.list'].create_from_brevo_data(event_data)
                return {'success': True, 'message': f'New list created: {contact_list.name}'}
                
        except Exception as e:
            _logger.error(f"List update webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_list_deleted(self, event_data):
        """Handle list deletion webhook"""
        try:
            # Find existing list
            contact_list = request.env['brevo.contact.list'].search([
                ('brevo_id', '=', str(event_data.get('id')))
            ], limit=1)
            
            if contact_list:
                # Mark list as inactive instead of deleting
                contact_list.write({'active': False})
                return {'success': True, 'message': f'List archived: {contact_list.name}'}
            else:
                return {'success': True, 'message': 'List not found'}
                
        except Exception as e:
            _logger.error(f"List deletion webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_booking_webhook(self, event_type, event_data):
        """Handle booking-related webhooks"""
        try:
            if event_type == 'booking.created':
                return self._handle_booking_created(event_data)
            elif event_type == 'booking.updated':
                return self._handle_booking_updated(event_data)
            elif event_type == 'booking.cancelled':
                return self._handle_booking_cancelled(event_data)
            else:
                return {'success': True, 'message': f'Unhandled booking event: {event_type}'}
                
        except Exception as e:
            _logger.error(f"Booking webhook handling failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_booking_created(self, event_data):
        """Handle booking creation webhook"""
        try:
            # Create CRM lead from booking
            lead = request.env['crm.lead'].create_from_brevo_booking(event_data)
            return {'success': True, 'message': f'Lead created from booking: {lead.name}'}
            
        except Exception as e:
            _logger.error(f"Booking creation webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_booking_updated(self, event_data):
        """Handle booking update webhook"""
        try:
            # Update existing lead
            lead = request.env['crm.lead'].process_brevo_webhook({
                'event': 'booking.updated',
                'data': event_data
            })
            
            if lead:
                return {'success': True, 'message': f'Lead updated from booking: {lead.name}'}
            else:
                return {'success': True, 'message': 'No lead found to update'}
                
        except Exception as e:
            _logger.error(f"Booking update webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_booking_cancelled(self, event_data):
        """Handle booking cancellation webhook"""
        try:
            # Update existing lead
            lead = request.env['crm.lead'].process_brevo_webhook({
                'event': 'booking.cancelled',
                'data': event_data
            })
            
            if lead:
                return {'success': True, 'message': f'Lead updated from booking cancellation: {lead.name}'}
            else:
                return {'success': True, 'message': 'No lead found to update'}
                
        except Exception as e:
            _logger.error(f"Booking cancellation webhook failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _update_partner_from_brevo_data(self, partner, brevo_data):
        """Update partner with data from Brevo webhook"""
        try:
            attributes = brevo_data.get('attributes', {})
            
            update_vals = {
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
                'brevo_sync_error': False,
                'brevo_modified_date': brevo_data.get('modifiedAt'),
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
            request.env['brevo.sync.log'].log_success(
                'contact_update',
                'brevo_to_odoo',
                f'Partner {partner.name} updated from Brevo webhook',
                partner_id=partner.id,
                brevo_id=str(brevo_data.get('id')),
                brevo_email=brevo_data.get('email')
            )
            
        except Exception as e:
            _logger.error(f"Failed to update partner {partner.id} from Brevo webhook: {str(e)}")
            
            # Log error
            request.env['brevo.sync.log'].log_error(
                'contact_update',
                'brevo_to_odoo',
                f'Failed to update partner {partner.name} from Brevo webhook',
                error_message=str(e),
                partner_id=partner.id,
                brevo_id=str(brevo_data.get('id')),
                brevo_email=brevo_data.get('email')
            )
    
    @http.route('/brevo/webhook/test', type='http', auth='user', methods=['GET'])
    def test_webhook(self):
        """Test webhook endpoint (for debugging)"""
        try:
            # Get active config
            config = request.env['brevo.config'].get_active_config()
            
            if not config:
                return request.render('brevo_connector.webhook_test_template', {
                    'error': 'No active Brevo configuration found'
                })
            
            # Test webhook URL
            webhook_url = config.webhook_url
            
            return request.render('brevo_connector.webhook_test_template', {
                'webhook_url': webhook_url,
                'config': config,
                'success': True
            })
            
        except Exception as e:
            _logger.error(f"Webhook test failed: {str(e)}")
            return request.render('brevo_connector.webhook_test_template', {
                'error': str(e)
            })
