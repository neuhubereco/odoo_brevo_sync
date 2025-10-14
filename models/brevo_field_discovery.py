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
        try:
            partner_model = self.env['res.partner']
            fields_list = []
            
            # Add standard Odoo fields
            standard_fields = [
                ('name', 'Name'),
                ('email', 'Email'),
                ('phone', 'Phone'),
                ('mobile', 'Mobile'),
                ('street', 'Street'),
                ('street2', 'Street2'),
                ('city', 'City'),
                ('zip', 'ZIP'),
                ('website', 'Website'),
                ('comment', 'Notes'),
                ('title', 'Title'),
                ('function', 'Job Position'),
                ('parent_id', 'Company'),
                ('country_id', 'Country'),
                ('state_id', 'State'),
                ('category_id', 'Tags'),
                ('is_company', 'Is Company'),
                ('customer_rank', 'Customer Rank'),
                ('supplier_rank', 'Supplier Rank'),
                ('lang', 'Language'),
                ('tz', 'Timezone'),
                ('date', 'Date of Birth'),
                ('industry_id', 'Industry'),
                ('company_name', 'Company Name'),
                ('company_type', 'Company Type'),
                ('user_id', 'Salesperson'),
                ('team_id', 'Sales Team'),
                ('ref', 'Reference'),
                ('barcode', 'Barcode'),
                ('active', 'Active'),
            ]
            
            for field_name, field_label in standard_fields:
                if field_name in partner_model._fields:
                    fields_list.append((field_name, f"{field_name} ({field_label})"))
            
            # Add Brevo custom fields
            brevo_fields = [
                ('x_brevo_age', 'Brevo Age'),
                ('x_brevo_gender', 'Brevo Gender'),
                ('x_brevo_middlename', 'Brevo Middle Name'),
                ('x_brevo_nickname', 'Brevo Nickname'),
                ('x_brevo_fax', 'Brevo Fax'),
                ('x_brevo_skype', 'Brevo Skype'),
                ('x_brevo_linkedin', 'Brevo LinkedIn'),
                ('x_brevo_twitter', 'Brevo Twitter'),
                ('x_brevo_facebook', 'Brevo Facebook'),
                ('x_brevo_instagram', 'Brevo Instagram'),
                ('x_brevo_youtube', 'Brevo YouTube'),
                ('x_brevo_tiktok', 'Brevo TikTok'),
                ('x_brevo_latitude', 'Brevo Latitude'),
                ('x_brevo_longitude', 'Brevo Longitude'),
                ('x_brevo_department', 'Brevo Department'),
                ('x_brevo_company_size', 'Brevo Company Size'),
                ('x_brevo_annual_revenue', 'Brevo Annual Revenue'),
                ('x_brevo_employees', 'Brevo Employees'),
                ('x_brevo_company_website', 'Brevo Company Website'),
                ('x_brevo_company_phone', 'Brevo Company Phone'),
                ('x_brevo_company_email', 'Brevo Company Email'),
                ('x_brevo_source', 'Brevo Source'),
                ('x_brevo_campaign', 'Brevo Campaign'),
                ('x_brevo_utm_medium', 'Brevo UTM Medium'),
                ('x_brevo_utm_campaign', 'Brevo UTM Campaign'),
                ('x_brevo_utm_term', 'Brevo UTM Term'),
                ('x_brevo_utm_content', 'Brevo UTM Content'),
                ('x_brevo_referrer', 'Brevo Referrer'),
                ('x_brevo_landing_page', 'Brevo Landing Page'),
                ('x_brevo_subscriber_type', 'Brevo Subscriber Type'),
                ('x_brevo_subscription_status', 'Brevo Subscription Status'),
                ('x_brevo_opt_in_date', 'Brevo Opt-in Date'),
                ('x_brevo_opt_out_date', 'Brevo Opt-out Date'),
                ('x_brevo_last_activity', 'Brevo Last Activity'),
                ('x_brevo_last_open', 'Brevo Last Open'),
                ('x_brevo_last_click', 'Brevo Last Click'),
                ('x_brevo_email_frequency', 'Brevo Email Frequency'),
                ('x_brevo_communication_preference', 'Brevo Communication Preference'),
                ('x_brevo_custom_field_1', 'Brevo Custom Field 1'),
                ('x_brevo_custom_field_2', 'Brevo Custom Field 2'),
                ('x_brevo_custom_field_3', 'Brevo Custom Field 3'),
                ('x_brevo_custom_field_4', 'Brevo Custom Field 4'),
                ('x_brevo_custom_field_5', 'Brevo Custom Field 5'),
                ('x_brevo_segment', 'Brevo Segment'),
                ('x_brevo_score', 'Brevo Score'),
                ('x_brevo_priority', 'Brevo Priority'),
                ('x_brevo_status', 'Brevo Status'),
                ('x_brevo_stage', 'Brevo Stage'),
                ('x_brevo_type', 'Brevo Type'),
                ('x_brevo_rating', 'Brevo Rating'),
                ('x_brevo_salary', 'Brevo Salary'),
                ('x_brevo_budget', 'Brevo Budget'),
                ('x_brevo_interest', 'Brevo Interest'),
                ('x_brevo_hobby', 'Brevo Hobby'),
                ('x_brevo_education', 'Brevo Education'),
                ('x_brevo_experience', 'Brevo Experience'),
                ('x_brevo_skills', 'Brevo Skills'),
                ('x_brevo_certifications', 'Brevo Certifications'),
                ('x_brevo_languages', 'Brevo Languages'),
                ('x_brevo_availability', 'Brevo Availability'),
                ('x_brevo_preferred_contact_time', 'Brevo Preferred Contact Time'),
                ('x_brevo_preferred_contact_method', 'Brevo Preferred Contact Method'),
                ('x_brevo_consent_date', 'Brevo Consent Date'),
                ('x_brevo_consent_source', 'Brevo Consent Source'),
                ('x_brevo_consent_text', 'Brevo Consent Text'),
                ('x_brevo_gdpr_consent', 'Brevo GDPR Consent'),
                ('x_brevo_marketing_consent', 'Brevo Marketing Consent'),
                ('x_brevo_newsletter_consent', 'Brevo Newsletter Consent'),
                ('x_brevo_sms_consent', 'Brevo SMS Consent'),
                ('x_brevo_call_consent', 'Brevo Call Consent'),
                ('x_brevo_email_consent', 'Brevo Email Consent'),
            ]
            
            for field_name, field_label in brevo_fields:
                if field_name in partner_model._fields:
                    fields_list.append((field_name, f"{field_name} ({field_label})"))
            
            return fields_list
            
        except Exception as e:
            _logger.error(f"Error getting Odoo field selection: {str(e)}")
            return [('', 'Error loading fields')]

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
        elif odoo_field.type == 'many2one':
            field_type = 'many2one'
        elif odoo_field.type == 'many2many':
            field_type = 'many2many'

        # Create mapping
        mapping_vals = {
            'name': f'{self.brevo_field_name} -> {self.odoo_field_name}',
            'brevo_field_name': self.brevo_field_name,
            'odoo_field_name': self.odoo_field_name,
            'field_type': field_type,
            'company_id': self.company_id.id,
        }

        mapping = self.env['brevo.field.mapping'].create(mapping_vals)
        
        # Force refresh of computed fields
        self.invalidate_recordset()
        self.refresh()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mapping Created'),
                'message': _('Field mapping for %s created successfully.') % self.brevo_field_name,
                'type': 'success',
            }
        }
