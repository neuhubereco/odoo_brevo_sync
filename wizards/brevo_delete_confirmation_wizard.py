# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BrevoDeleteConfirmationWizard(models.TransientModel):
    """Wizard for confirming deletion of partners with Brevo data"""
    _name = 'brevo.delete.confirmation.wizard'
    _description = 'Brevo Delete Confirmation Wizard'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Partners to Delete',
        required=True
    )
    
    brevo_partner_count = fields.Integer(
        string='Partners with Brevo Data',
        readonly=True
    )
    
    delete_from_brevo = fields.Boolean(
        string='Also delete from Brevo',
        default=True,
        help='If checked, contacts will also be deleted from Brevo'
    )
    
    confirmation_text = fields.Char(
        string='Type "DELETE" to confirm',
        help='Type "DELETE" to confirm the deletion'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values"""
        defaults = super().default_get(fields_list)
        if 'partner_ids' in self.env.context:
            defaults['partner_ids'] = [(6, 0, self.env.context['partner_ids'])]
        if 'brevo_partner_count' in self.env.context:
            defaults['brevo_partner_count'] = self.env.context['brevo_partner_count']
        return defaults

    def action_confirm_delete(self):
        """Confirm and execute deletion"""
        self.ensure_one()
        
        if self.confirmation_text != 'DELETE':
            raise ValidationError(_('Please type "DELETE" to confirm the deletion'))
        
        try:
            # Delete from Brevo if requested
            if self.delete_from_brevo:
                self._delete_from_brevo()
            
            # Delete from Odoo
            self.partner_ids.unlink()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Deletion Successful'),
                    'message': _('Partners deleted successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Failed to delete partners: {str(e)}")
            raise ValidationError(_('Failed to delete partners: %s') % str(e))

    def action_cancel(self):
        """Cancel deletion"""
        return {'type': 'ir.actions.act_window_close'}

    def _delete_from_brevo(self):
        """Delete contacts from Brevo"""
        try:
            from ..services.brevo_sync_service import BrevoSyncService
            config = self.env['brevo.config'].get_active_config()
            
            if not config:
                _logger.warning('No active Brevo configuration found')
                return
            
            sync_service = BrevoSyncService(config)
            
            for partner in self.partner_ids:
                if partner.brevo_id and partner.email:
                    try:
                        result = sync_service.brevo_service.delete_contact(partner.brevo_id)
                        if result.get('success'):
                            _logger.info(f"Deleted contact {partner.email} from Brevo")
                        else:
                            _logger.warning(f"Failed to delete contact {partner.email} from Brevo: {result.get('error')}")
                    except Exception as e:
                        _logger.error(f"Failed to delete contact {partner.email} from Brevo: {str(e)}")
                        
        except Exception as e:
            _logger.error(f"Failed to delete contacts from Brevo: {str(e)}")
            raise e
