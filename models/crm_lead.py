# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    """Extend crm.lead with Brevo integration fields"""
    _inherit = 'crm.lead'

    # Brevo Integration Fields
    brevo_lead_id = fields.Char(
        string='Brevo Lead ID',
        help='Unique identifier for this lead in Brevo',
        index=True
    )
    
    brevo_source = fields.Char(
        string='Brevo Source',
        help='Source of the lead from Brevo (e.g., booking, form)'
    )
    
    brevo_booking_id = fields.Char(
        string='Brevo Booking ID',
        help='ID of the booking that created this lead'
    )
    
    brevo_booking_time = fields.Datetime(
        string='Brevo Booking Time',
        help='Scheduled time of the booking'
    )
    
    brevo_booking_notes = fields.Text(
        string='Brevo Booking Notes',
        help='Notes from the Brevo booking'
    )
    
    brevo_created_date = fields.Datetime(
        string='Brevo Created Date',
        help='Date when this lead was created in Brevo'
    )
    
    brevo_sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('error', 'Error'),
        ('never', 'Never Synced')
    ], string='Brevo Sync Status', default='never')
    
    brevo_sync_error = fields.Text(
        string='Brevo Sync Error',
        help='Last error message from Brevo synchronization'
    )
    
    brevo_last_sync = fields.Datetime(
        string='Last Brevo Sync',
        help='Last time this lead was synchronized with Brevo'
    )

    @api.model
    def create_from_brevo_booking(self, booking_data):
        """Create a new lead from Brevo booking/meeting data.
        Supports both legacy payloads (contact/startTime/title/notes)
        and the new Meeting/Phone webhook schema (meeting_name, event_participants, questions_and_answers).
        """
        try:
            # Normalize payload first
            normalized = self._normalize_brevo_meeting_payload(booking_data)
            contact_data = normalized.get('contact', {})
            email = contact_data.get('email')
            
            if not email:
                raise ValidationError(_('Email address is required for lead creation'))
            
            # Find or create partner
            partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
            if not partner:
                partner_vals = {
                    'name': f"{contact_data.get('firstName', '')} {contact_data.get('lastName', '')}".strip() or email,
                    'email': email,
                    'phone': contact_data.get('phone', ''),
                }
                partner = self.env['res.partner'].create(partner_vals)
            
            # Extract booking information
            booking_time = normalized.get('startTime')
            if booking_time:
                try:
                    booking_time = datetime.fromisoformat(booking_time.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    booking_time = False
            
            # Create lead
            lead_vals = {
                'name': normalized.get('title', _('Brevo Booking Lead')),
                'partner_id': partner.id,
                'email_from': email,
                'description': normalized.get('description', ''),
                'brevo_lead_id': str(normalized.get('id')) if normalized.get('id') else False,
                'brevo_source': 'booking',
                'brevo_booking_id': str(normalized.get('id')) if normalized.get('id') else False,
                'brevo_booking_time': booking_time,
                'brevo_booking_notes': normalized.get('notes', ''),
                'brevo_created_date': normalized.get('createdAt'),
                'brevo_sync_status': 'synced',
                'brevo_last_sync': fields.Datetime.now(),
            }
            
            # Set lead type based on booking type
            booking_type = (normalized.get('type') or '').lower()
            if 'meeting' in booking_type or 'call' in booking_type:
                lead_vals['type'] = 'opportunity'
            else:
                lead_vals['type'] = 'lead'
            
            lead = self.create(lead_vals)
            
            # Log the creation (disabled for public user)
            _logger.info(f'Lead created from Brevo booking: {lead.name}')
            
            return lead
            
        except Exception as e:
            _logger.error(f"Failed to create lead from Brevo booking: {str(e)}")
            
            # Log the error (disabled for public user)
            _logger.error(f'Failed to create lead from Brevo booking: {str(e)}')
            
            raise ValidationError(_('Failed to create lead from Brevo booking: %s') % str(e))

    def _normalize_brevo_meeting_payload(self, payload):
        """Return a normalized dict for booking/meeting payloads.
        Handles structures with keys like meeting_name, event_participants, questions_and_answers.
        """
        # Legacy keys passthrough
        title = payload.get('title') or payload.get('meeting_name')
        start_time = payload.get('startTime') or payload.get('meeting_start_timestamp')
        notes = payload.get('notes') or payload.get('meeting_notes') or ''

        # Compose description: include questions_and_answers if present
        description = payload.get('description') or ''
        qa = payload.get('questions_and_answers') or []
        if qa:
            lines = [description] if description else []
            lines.append(_('Questions and Answers:'))
            for item in qa:
                q = item.get('question')
                a = item.get('answer')
                if q or a:
                    lines.append(f"Q: {q or ''}")
                    lines.append(f"A: {a or ''}")
            description = '\n'.join(lines).strip()

        # Contact info
        contact = payload.get('contact') or {}
        participants = payload.get('event_participants') or []
        if not contact and participants:
            p = participants[0] or {}
            contact = {
                'email': p.get('EMAIL'),
                'firstName': p.get('FIRSTNAME'),
                'lastName': p.get('LASTNAME'),
                'phone': payload.get('phone') or '',
            }

        normalized = {
            'id': payload.get('id'),
            'type': payload.get('type') or 'meeting',
            'title': title,
            'startTime': start_time,
            'createdAt': payload.get('createdAt') or fields.Datetime.now(),
            'notes': notes,
            'description': description,
            'contact': contact,
        }
        return normalized

    def _get_default_stage_id(self):
        """Get the default stage for new leads"""
        stage = self.env['crm.stage'].search([
            ('is_won', '=', False),
            ('is_lost', '=', False)
        ], limit=1)
        return stage.id if stage else False

    def sync_to_brevo(self):
        """Manually sync this lead to Brevo"""
        try:
            if not self.partner_id or not self.partner_id.email:
                raise ValidationError(_('Partner with email is required for Brevo sync'))
            
            from ..services.brevo_sync_service import BrevoSyncService
            config = self.env['brevo.config'].get_active_config()
            
            if not config:
                raise ValidationError(_('No active Brevo configuration found'))
            
            sync_service = BrevoSyncService(config)
            result = sync_service.sync_lead_to_brevo(self)
            
            if result.get('success'):
                self.brevo_sync_status = 'synced'
                self.brevo_last_sync = fields.Datetime.now()
                self.brevo_sync_error = False
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Successful'),
                        'message': _('Lead synchronized to Brevo successfully'),
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
            _logger.error(f"Lead sync to Brevo failed: {str(e)}")
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
            'name': self.name,
            'email': self.partner_id.email if self.partner_id else self.email_from,
            'phone': self.partner_id.phone if self.partner_id else self.phone,
            'description': self.description or '',
            'stage': self.stage_id.name if self.stage_id else '',
            'value': self.expected_revenue or 0,
            'source': 'odoo_crm',
            'booking_time': self.brevo_booking_time.isoformat() if self.brevo_booking_time else None,
            'notes': self.brevo_booking_notes or '',
        }

    @api.model
    def get_leads_for_brevo_sync(self, limit=None):
        """Get leads that need Brevo synchronization"""
        domain = [
            ('brevo_sync_status', 'in', ['pending', 'error', 'never']),
            ('partner_id', '!=', False),
            ('partner_id.email', '!=', False),
        ]
        
        return self.search(domain, limit=limit)

    @api.model
    def process_brevo_webhook(self, webhook_data):
        """Process webhook data from Brevo"""
        try:
            event_type = webhook_data.get('event')
            
            if event_type in ('booking.created', 'meeting.booked'):
                return self.create_from_brevo_booking(webhook_data.get('data', {}))
            elif event_type in ('booking.updated', 'meeting.started'):
                # Update existing lead
                data = webhook_data.get('data', {})
                brevo_booking_id = str(data.get('id')) if data.get('id') else False
                lead = self.search([('brevo_booking_id', '=', brevo_booking_id)], limit=1)
                if lead:
                    # Update lead with new booking data
                    booking_data = data
                    normalized = self._normalize_brevo_meeting_payload(booking_data)
                    updates = {
                        'name': normalized.get('title') or lead.name,
                        'brevo_booking_time': normalized.get('startTime') or lead.brevo_booking_time,
                        'brevo_booking_notes': normalized.get('notes', '') or lead.brevo_booking_notes,
                        'description': normalized.get('description') or lead.description,
                        'brevo_last_sync': fields.Datetime.now(),
                    }
                    lead.write(updates)
                    return lead
            elif event_type in ('booking.cancelled', 'meeting.cancelled'):
                # Handle booking cancellation
                data = webhook_data.get('data', {})
                brevo_booking_id = str(data.get('id')) if data.get('id') else False
                lead = self.search([('brevo_booking_id', '=', brevo_booking_id)], limit=1)
                if lead:
                    # Mark lead as lost or update stage
                    lost_stage = self.env['crm.stage'].search([('is_lost', '=', True)], limit=1)
                    if lost_stage:
                        lead.stage_id = lost_stage.id
                    lead.brevo_last_sync = fields.Datetime.now()
                    return lead
            elif event_type == 'call.finished':
                # Create/Update a lead from finished call event
                data = webhook_data.get('data', {})
                return self.create_from_brevo_booking(data)
            
            return False
            
        except Exception as e:
            _logger.error(f"Failed to process Brevo webhook: {str(e)}")
            
            # Log the error
            self.env['brevo.sync.log'].log_error(
                'webhook',
                'brevo_to_odoo',
                f'Failed to process Brevo webhook: {str(e)}',
                error_message=str(e),
                details=str(webhook_data)
            )
            
            raise ValidationError(_('Failed to process Brevo webhook: %s') % str(e))
