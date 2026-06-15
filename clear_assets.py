#!/usr/bin/env python3
import os
import sys

# Add the Odoo directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'odoo'))

import odoo
from odoo.tools import config

# Set up config
config.parse_config(['-c', 'odoo/odoo.conf', '-d', 'hag_db', '--no-http'])

# Initialize Odoo
with odoo.api.Environment.manage():
    registry = odoo.registry(config['db_name'])
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        
        print("Finding and deleting corrupted asset attachments...")
        
        # Find and delete ONLY asset attachments! This will NOT touch business files!
        domain = ['|', ('name', 'ilike', 'assets_'), ('url', 'ilike', 'web/assets/')]
        attachments = env['ir.attachment'].search(domain)
        
        count = len(attachments)
        if count > 0:
            print(f"Deleting {count} old/corrupted asset attachments...")
            attachments.unlink()
            cr.commit()
            print("Success! Old assets deleted, Odoo will regenerate fresh ones!")
        else:
            print("No old asset attachments found.")
