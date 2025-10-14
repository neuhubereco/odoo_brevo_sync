# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartnerBrevoFields(models.Model):
    """Add Brevo fields to res.partner model"""
    _inherit = 'res.partner'

    # Personal Information Fields
    x_brevo_age = fields.Integer(
        string='Brevo Age',
        help='Age from Brevo'
    )
    
    x_brevo_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Brevo Gender', help='Gender from Brevo')
    
    x_brevo_middlename = fields.Char(
        string='Brevo Middle Name',
        help='Middle name from Brevo'
    )
    
    x_brevo_nickname = fields.Char(
        string='Brevo Nickname',
        help='Nickname from Brevo'
    )

    # Contact Information Fields
    x_brevo_fax = fields.Char(
        string='Brevo Fax',
        help='Fax number from Brevo'
    )
    
    x_brevo_skype = fields.Char(
        string='Brevo Skype',
        help='Skype ID from Brevo'
    )
    
    x_brevo_linkedin = fields.Char(
        string='Brevo LinkedIn',
        help='LinkedIn profile from Brevo'
    )
    
    x_brevo_twitter = fields.Char(
        string='Brevo Twitter',
        help='Twitter handle from Brevo'
    )
    
    x_brevo_facebook = fields.Char(
        string='Brevo Facebook',
        help='Facebook profile from Brevo'
    )
    
    x_brevo_instagram = fields.Char(
        string='Brevo Instagram',
        help='Instagram profile from Brevo'
    )
    
    x_brevo_youtube = fields.Char(
        string='Brevo YouTube',
        help='YouTube channel from Brevo'
    )
    
    x_brevo_tiktok = fields.Char(
        string='Brevo TikTok',
        help='TikTok profile from Brevo'
    )

    # Address Fields
    x_brevo_latitude = fields.Float(
        string='Brevo Latitude',
        help='Latitude from Brevo'
    )
    
    x_brevo_longitude = fields.Float(
        string='Brevo Longitude',
        help='Longitude from Brevo'
    )

    # Company Information Fields
    x_brevo_department = fields.Char(
        string='Brevo Department',
        help='Department from Brevo'
    )
    
    x_brevo_company_size = fields.Integer(
        string='Brevo Company Size',
        help='Company size from Brevo'
    )
    
    x_brevo_annual_revenue = fields.Float(
        string='Brevo Annual Revenue',
        help='Annual revenue from Brevo'
    )
    
    x_brevo_employees = fields.Integer(
        string='Brevo Employees',
        help='Number of employees from Brevo'
    )
    
    x_brevo_company_website = fields.Char(
        string='Brevo Company Website',
        help='Company website from Brevo'
    )
    
    x_brevo_company_phone = fields.Char(
        string='Brevo Company Phone',
        help='Company phone from Brevo'
    )
    
    x_brevo_company_email = fields.Char(
        string='Brevo Company Email',
        help='Company email from Brevo'
    )

    # Marketing Fields
    x_brevo_source = fields.Char(
        string='Brevo Source',
        help='Lead source from Brevo'
    )
    
    x_brevo_campaign = fields.Char(
        string='Brevo Campaign',
        help='Campaign from Brevo'
    )
    
    x_brevo_utm_medium = fields.Char(
        string='Brevo UTM Medium',
        help='UTM medium from Brevo'
    )
    
    x_brevo_utm_campaign = fields.Char(
        string='Brevo UTM Campaign',
        help='UTM campaign from Brevo'
    )
    
    x_brevo_utm_term = fields.Char(
        string='Brevo UTM Term',
        help='UTM term from Brevo'
    )
    
    x_brevo_utm_content = fields.Char(
        string='Brevo UTM Content',
        help='UTM content from Brevo'
    )
    
    x_brevo_referrer = fields.Char(
        string='Brevo Referrer',
        help='Referrer from Brevo'
    )
    
    x_brevo_landing_page = fields.Char(
        string='Brevo Landing Page',
        help='Landing page from Brevo'
    )
    
    x_brevo_subscriber_type = fields.Char(
        string='Brevo Subscriber Type',
        help='Subscriber type from Brevo'
    )
    
    x_brevo_subscription_status = fields.Selection([
        ('subscribed', 'Subscribed'),
        ('unsubscribed', 'Unsubscribed'),
        ('blacklisted', 'Blacklisted')
    ], string='Brevo Subscription Status', help='Subscription status from Brevo')
    
    x_brevo_opt_in_date = fields.Date(
        string='Brevo Opt-in Date',
        help='Opt-in date from Brevo'
    )
    
    x_brevo_opt_out_date = fields.Date(
        string='Brevo Opt-out Date',
        help='Opt-out date from Brevo'
    )
    
    x_brevo_last_activity = fields.Datetime(
        string='Brevo Last Activity',
        help='Last activity from Brevo'
    )
    
    x_brevo_last_open = fields.Datetime(
        string='Brevo Last Open',
        help='Last email open from Brevo'
    )
    
    x_brevo_last_click = fields.Datetime(
        string='Brevo Last Click',
        help='Last email click from Brevo'
    )
    
    x_brevo_email_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('never', 'Never')
    ], string='Brevo Email Frequency', help='Email frequency preference from Brevo')
    
    x_brevo_communication_preference = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('phone', 'Phone'),
        ('none', 'None')
    ], string='Brevo Communication Preference', help='Communication preference from Brevo')

    # Custom Fields
    x_brevo_custom_field_1 = fields.Char(
        string='Brevo Custom Field 1',
        help='Custom field 1 from Brevo'
    )
    
    x_brevo_custom_field_2 = fields.Char(
        string='Brevo Custom Field 2',
        help='Custom field 2 from Brevo'
    )
    
    x_brevo_custom_field_3 = fields.Char(
        string='Brevo Custom Field 3',
        help='Custom field 3 from Brevo'
    )
    
    x_brevo_custom_field_4 = fields.Char(
        string='Brevo Custom Field 4',
        help='Custom field 4 from Brevo'
    )
    
    x_brevo_custom_field_5 = fields.Char(
        string='Brevo Custom Field 5',
        help='Custom field 5 from Brevo'
    )

    # Additional Fields
    x_brevo_segment = fields.Char(
        string='Brevo Segment',
        help='Segment from Brevo'
    )
    
    x_brevo_score = fields.Integer(
        string='Brevo Score',
        help='Score from Brevo'
    )
    
    x_brevo_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Brevo Priority', help='Priority from Brevo')
    
    x_brevo_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended')
    ], string='Brevo Status', help='Status from Brevo')
    
    x_brevo_stage = fields.Char(
        string='Brevo Stage',
        help='Stage from Brevo'
    )
    
    x_brevo_type = fields.Char(
        string='Brevo Type',
        help='Type from Brevo'
    )
    
    x_brevo_rating = fields.Integer(
        string='Brevo Rating',
        help='Rating from Brevo'
    )
    
    x_brevo_salary = fields.Float(
        string='Brevo Salary',
        help='Salary from Brevo'
    )
    
    x_brevo_budget = fields.Float(
        string='Brevo Budget',
        help='Budget from Brevo'
    )
    
    x_brevo_interest = fields.Char(
        string='Brevo Interest',
        help='Interest from Brevo'
    )
    
    x_brevo_hobby = fields.Char(
        string='Brevo Hobby',
        help='Hobby from Brevo'
    )
    
    x_brevo_education = fields.Char(
        string='Brevo Education',
        help='Education from Brevo'
    )
    
    x_brevo_experience = fields.Char(
        string='Brevo Experience',
        help='Experience from Brevo'
    )
    
    x_brevo_skills = fields.Char(
        string='Brevo Skills',
        help='Skills from Brevo'
    )
    
    x_brevo_certifications = fields.Char(
        string='Brevo Certifications',
        help='Certifications from Brevo'
    )
    
    x_brevo_languages = fields.Char(
        string='Brevo Languages',
        help='Languages from Brevo'
    )
    
    x_brevo_availability = fields.Char(
        string='Brevo Availability',
        help='Availability from Brevo'
    )
    
    x_brevo_preferred_contact_time = fields.Char(
        string='Brevo Preferred Contact Time',
        help='Preferred contact time from Brevo'
    )
    
    x_brevo_preferred_contact_method = fields.Selection([
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('sms', 'SMS'),
        ('mail', 'Mail')
    ], string='Brevo Preferred Contact Method', help='Preferred contact method from Brevo')
    
    x_brevo_consent_date = fields.Date(
        string='Brevo Consent Date',
        help='Consent date from Brevo'
    )
    
    x_brevo_consent_source = fields.Char(
        string='Brevo Consent Source',
        help='Consent source from Brevo'
    )
    
    x_brevo_consent_text = fields.Text(
        string='Brevo Consent Text',
        help='Consent text from Brevo'
    )

    # GDPR Consent Fields
    x_brevo_gdpr_consent = fields.Boolean(
        string='Brevo GDPR Consent',
        help='GDPR consent from Brevo'
    )
    
    x_brevo_marketing_consent = fields.Boolean(
        string='Brevo Marketing Consent',
        help='Marketing consent from Brevo'
    )
    
    x_brevo_newsletter_consent = fields.Boolean(
        string='Brevo Newsletter Consent',
        help='Newsletter consent from Brevo'
    )
    
    x_brevo_sms_consent = fields.Boolean(
        string='Brevo SMS Consent',
        help='SMS consent from Brevo'
    )
    
    x_brevo_call_consent = fields.Boolean(
        string='Brevo Call Consent',
        help='Call consent from Brevo'
    )
    
    x_brevo_email_consent = fields.Boolean(
        string='Brevo Email Consent',
        help='Email consent from Brevo'
    )
