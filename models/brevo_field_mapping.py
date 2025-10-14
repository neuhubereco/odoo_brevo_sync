# -*- coding: utf-8 -*-

import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BrevoFieldMapping(models.Model):
    """Model for mapping Brevo contact fields to Odoo partner fields"""
    _name = 'brevo.field.mapping'
    _description = 'Brevo Field Mapping'
    _rec_name = 'brevo_field_name'

    name = fields.Char(
        string='Mapping Name',
        required=True,
        help='Descriptive name for this field mapping'
    )
    
    brevo_field_name = fields.Char(
        string='Brevo Field Name',
        required=True,
        help='Name of the field in Brevo (e.g., FNAME, LNAME, SMS)'
    )
    
    odoo_field_name = fields.Char(
        string='Odoo Field Name',
        required=True,
        help='Name of the field in Odoo (e.g., name, mobile, street)'
    )
    
    field_type = fields.Selection([
        ('char', 'Text'),
        ('text', 'Long Text'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('selection', 'Selection'),
        ('many2one', 'Many2One'),
        ('many2many', 'Many2Many'),
    ], string='Field Type', required=True, default='char')
    
    selection_values = fields.Text(
        string='Selection Values',
        help='JSON format: [["value", "Label"], ["value2", "Label2"]]'
    )
    
    many2one_model = fields.Char(
        string='Many2One Model',
        help='Model name for Many2One fields (e.g., res.country)'
    )
    
    many2many_model = fields.Char(
        string='Many2Many Model',
        help='Model name for Many2Many fields (e.g., res.partner.category)'
    )
    
    is_required = fields.Boolean(
        string='Required',
        default=False,
        help='Whether this field is required in Odoo'
    )
    
    is_readonly = fields.Boolean(
        string='Read Only',
        default=False,
        help='Whether this field is read-only in Odoo'
    )
    
    default_value = fields.Char(
        string='Default Value',
        help='Default value for this field'
    )
    
    help_text = fields.Text(
        string='Help Text',
        help='Help text displayed in the field'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this mapping is active'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    @api.constrains('brevo_field_name', 'odoo_field_name', 'company_id')
    def _check_unique_mapping(self):
        """Ensure unique field mapping per company"""
        for record in self:
            existing = self.search([
                ('brevo_field_name', '=', record.brevo_field_name),
                ('odoo_field_name', '=', record.odoo_field_name),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(
                    _('A mapping for Brevo field "%s" to Odoo field "%s" already exists for this company.')
                    % (record.brevo_field_name, record.odoo_field_name)
                )
    
    @api.constrains('field_type', 'selection_values')
    def _check_selection_values(self):
        """Validate selection values for selection fields"""
        for record in self:
            if record.field_type == 'selection' and record.selection_values:
                try:
                    values = json.loads(record.selection_values)
                    if not isinstance(values, list):
                        raise ValidationError(_('Selection values must be a list'))
                    for value in values:
                        if not isinstance(value, list) or len(value) != 2:
                            raise ValidationError(
                                _('Each selection value must be a list with exactly 2 elements: [value, label]')
                            )
                except (json.JSONDecodeError, TypeError):
                    raise ValidationError(_('Invalid JSON format for selection values'))
    
    def create_odoo_field(self):
        """Create the corresponding field in res.partner model"""
        self.ensure_one()
        
        # This would require modifying the model at runtime
        # For now, we'll store the field data in brevo_dynamic_fields
        field_data = {
            'name': self.odoo_field_name,
            'type': self.field_type,
            'string': self.name,
            'help': self.help_text or '',
            'required': self.is_required,
            'readonly': self.is_readonly,
            'default': self.default_value,
        }
        
        if self.field_type == 'selection' and self.selection_values:
            field_data['selection'] = json.loads(self.selection_values)
        
        if self.field_type == 'many2one' and self.many2one_model:
            field_data['comodel_name'] = self.many2one_model
        
        if self.field_type == 'many2many' and self.many2many_model:
            field_data['comodel_name'] = self.many2many_model
        
        return field_data
    
    def get_field_value_from_brevo(self, brevo_contact_data):
        """Extract field value from Brevo contact data"""
        self.ensure_one()
        
        # Get value from Brevo attributes
        attributes = brevo_contact_data.get('attributes', {})
        value = attributes.get(self.brevo_field_name)
        
        if value is None:
            return None
        
        # Convert value based on field type
        if self.field_type == 'integer':
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        elif self.field_type == 'float':
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif self.field_type == 'boolean':
            return bool(value)
        elif self.field_type in ['date', 'datetime']:
            try:
                from datetime import datetime
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                return value
            except (ValueError, TypeError):
                return None
        
        return value
    
    def set_field_value_in_odoo(self, partner, value):
        """Set field value in Odoo partner record"""
        self.ensure_one()
        
        if value is None:
            return
        
        # For dynamic fields, we store them in brevo_dynamic_fields
        if not hasattr(partner, self.odoo_field_name):
            # Store in dynamic fields JSON
            dynamic_fields = {}
            if partner.brevo_dynamic_fields:
                try:
                    dynamic_fields = json.loads(partner.brevo_dynamic_fields)
                except (json.JSONDecodeError, TypeError):
                    dynamic_fields = {}
            
            dynamic_fields[self.odoo_field_name] = value
            partner.brevo_dynamic_fields = json.dumps(dynamic_fields)
        else:
            # Set the actual field if it exists
            setattr(partner, self.odoo_field_name, value)

    def get_field_value_from_odoo(self, partner):
        """Get field value from Odoo partner record"""
        self.ensure_one()
        
        try:
            if hasattr(partner, self.odoo_field_name):
                value = getattr(partner, self.odoo_field_name)
                
                # Convert Odoo objects to strings for Brevo API
                if hasattr(value, 'name'):
                    # Many2one fields (e.g., title, country_id, state_id)
                    return value.name
                elif hasattr(value, 'display_name'):
                    # Other relational fields
                    return value.display_name
                elif isinstance(value, (list, tuple)):
                    # Many2many fields - join with comma
                    return ', '.join([item.name if hasattr(item, 'name') else str(item) for item in value])
                elif isinstance(value, fields.Date):
                    # Convert Odoo date to ISO string
                    return value.isoformat()
                elif isinstance(value, fields.Datetime):
                    return value.isoformat()
                elif value is False:
                    return False
                elif value is True:
                    return True
                else:
                    # String, number, or other simple types
                    return value
            else:
                # Try to get from dynamic fields JSON
                if partner.brevo_dynamic_fields:
                    try:
                        dynamic_fields = json.loads(partner.brevo_dynamic_fields)
                        return dynamic_fields.get(self.odoo_field_name)
                    except (json.JSONDecodeError, TypeError):
                        pass
                return None
        except Exception as e:
            _logger.error(f"Failed to get field value from Odoo: {str(e)}")
            return None
