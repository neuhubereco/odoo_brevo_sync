# -*- coding: utf-8 -*-

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """Post-installation hook to set up initial configuration"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Set default configuration parameters
    config_params = env['ir.config_parameter']
    
    # Default sync interval (15 minutes)
    if not config_params.get_param('brevo.sync_interval'):
        config_params.set_param('brevo.sync_interval', '15')
    
    # Default batch size for API calls
    if not config_params.get_param('brevo.batch_size'):
        config_params.set_param('brevo.batch_size', '100')
    
    # Enable webhooks by default
    if not config_params.get_param('brevo.webhooks_enabled'):
        config_params.set_param('brevo.webhooks_enabled', 'True')
    
    _logger.info("Brevo Connector module initialized successfully")
