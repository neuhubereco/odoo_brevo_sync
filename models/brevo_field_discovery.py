# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BrevoFieldDiscovery(models.Model):
    """Model for discovering and mapping Brevo contact fields to Odoo partner fields"""
    _name = 'brevo.field.discovery'
    _description = 'Brevo Field Discovery'
    _rec_name = 'brevo_field_name'

    brevo_field_name = fields.Char(
        string='Brevo Field Name',
        required=True,
        help='Name of the field in Brevo (e.g., FNAME, LNAME, SMS)'
    )

    brevo_field_type = fields.Char(
        string='Brevo Field Type',
        help='Data type in Brevo (e.g., text, number, boolean)'
    )

    brevo_field_category = fields.Char(
        string='Brevo Category',
        help='Category of the field in Brevo'
    )

            odoo_field_name = fields.Selection(
                string='Odoo Field Name',
                selection='_get_odoo_field_selection',
                help='Name of the corresponding field in Odoo (e.g., name, mobile, street)'
            )

    odoo_field_type = fields.Char(
        string='Odoo Field Type',
        help='Data type in Odoo (e.g., char, text, integer)'
    )

    odoo_field_string = fields.Char(
        string='Odoo Field Label',
        help='Display name of the Odoo field'
    )

    is_mapped = fields.Boolean(
        string='Is Mapped',
        compute='_compute_is_mapped',
        store=True,
        help='Whether this field is currently mapped'
    )

    mapping_id = fields.Many2one(
        'brevo.field.mapping',
        string='Field Mapping',
        help='The field mapping record if this field is mapped'
    )

            company_id = fields.Many2one(
                'res.company',
                string='Company',
                default=lambda self: self.env.company
            )

            @api.model
            def _get_odoo_field_selection(self):
                """Get available Odoo partner fields for selection"""
                partner_model = self.env['res.partner']
                fields_list = []
                
                for field_name, field_obj in partner_model._fields.items():
                    if field_obj.type in ['char', 'text', 'integer', 'float', 'boolean', 'date', 'datetime', 'selection', 'many2one', 'many2many']:
                        fields_list.append((field_name, f"{field_name} ({field_obj.string})"))
                
                return fields_list

            @api.onchange('odoo_field_name')
            def _onchange_odoo_field_name(self):
                """Update Odoo field information when field is selected"""
                if self.odoo_field_name:
                    partner_model = self.env['res.partner']
                    field_obj = partner_model._fields.get(self.odoo_field_name)
                    if field_obj:
                        self.odoo_field_type = field_obj.type
                        self.odoo_field_string = field_obj.string

    @api.depends('brevo_field_name', 'odoo_field_name')
    def _compute_is_mapped(self):
        """Compute if this field combination is mapped"""
        for record in self:
            if record.brevo_field_name and record.odoo_field_name:
                mapping = self.env['brevo.field.mapping'].search([
                    ('brevo_field_name', '=', record.brevo_field_name),
                    ('odoo_field_name', '=', record.odoo_field_name),
                    ('company_id', '=', record.company_id.id)
                ], limit=1)
                record.is_mapped = bool(mapping)
                record.mapping_id = mapping.id if mapping else False
            else:
                record.is_mapped = False
                record.mapping_id = False

    def action_create_mapping(self):
        """Create a field mapping for this discovered field"""
        self.ensure_one()

        # Get Odoo field info
        odoo_field = self.env['res.partner']._fields.get(self.odoo_field_name)
        if not odoo_field:
            raise ValidationError(_('Odoo field %s does not exist') % self.odoo_field_name)

        # Determine field type
        field_type = 'char'
        if odoo_field.type == 'text':
            field_type = 'text'
        elif odoo_field.type == 'integer':
            field_type = 'integer'
        elif odoo_field.type == 'float':
            field_type = 'float'
        elif odoo_field.type == 'boolean':
            field_type = 'boolean'
        elif odoo_field.type == 'date':
            field_type = 'date'
        elif odoo_field.type == 'datetime':
            field_type = 'datetime'
        elif odoo_field.type == 'selection':
            field_type = 'selection'

        # Create mapping
        mapping_vals = {
            'name': f'{self.brevo_field_name} -> {self.odoo_field_name}',
            'brevo_field_name': self.brevo_field_name,
            'odoo_field_name': self.odoo_field_name,
            'field_type': field_type,
            'company_id': self.company_id.id,
        }

        mapping = self.env['brevo.field.mapping'].create(mapping_vals)
        return mapping
