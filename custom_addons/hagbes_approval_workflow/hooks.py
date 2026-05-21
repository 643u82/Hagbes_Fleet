from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE_NAME = 'approval_central'
NEW_MODULE_NAME = 'hagbes_approval_workflow'


def pre_init_hook(env):
    """Re-link seed data after module rename approval_central → hagbes_approval_workflow.

    Without this, install tries to CREATE approval.action rows that already exist
    (ir.model.data still points at the old module name) and hits unique(name).

    Note: runs before this module's models are registered — only touch ir.model.data.
    """
    _migrate_approval_central_xmlids(env)


def _migrate_approval_central_xmlids(env):
    """Move all external IDs from the retired module name to this module."""
    imd = env['ir.model.data'].sudo()
    legacy = imd.search([('module', '=', OLD_MODULE_NAME)])
    if not legacy:
        return

    # Avoid clobbering records already registered under the new module name.
    existing_new = set(
        imd.search([('module', '=', NEW_MODULE_NAME)]).mapped('name')
    )
    to_move = legacy.filtered(lambda row: row.name not in existing_new)
    if to_move:
        to_move.write({'module': NEW_MODULE_NAME})
        _logger.info(
            'Migrated %s ir.model.data row(s) from %s to %s.',
            len(to_move),
            OLD_MODULE_NAME,
            NEW_MODULE_NAME,
        )

    remaining = imd.search([('module', '=', OLD_MODULE_NAME)])
    if remaining:
        _logger.warning(
            '%s ir.model.data row(s) still on %s (name clash with %s).',
            len(remaining),
            OLD_MODULE_NAME,
            NEW_MODULE_NAME,
        )


def create_dynamic_menus(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    approval_requests = env['approval.request'].search_read([], ['res_model'])

    model_names = set(rec['res_model'] for rec in approval_requests if rec['res_model'])
    _logger.info("Found target models: %s", model_names)

    try:
        parent_menu = env.ref('hagbes_approval_workflow.menu_approval_root')
    except ValueError:
        _logger.error("Root menu not found. Check XML ID 'hagbes_approval_workflow.menu_approval_root'")
        return

    for model_name in model_names:
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not model:
            _logger.warning("Model not found in ir.model: %s", model_name)
            continue

        menu_name = f"{model.name} Approvals"

        # Prevent duplicate menus
        existing_menu = env['ir.ui.menu'].search([
            ('name', '=', menu_name),
            ('parent_id', '=', parent_menu.id)
        ], limit=1)
        if existing_menu:
            _logger.info("Menu already exists for model: %s", model.name)
            continue

        # Create action
        action = env['ir.actions.act_window'].create({
            'name': menu_name,
            'res_model': 'approval.request',
            'view_mode': 'tree,kanban,form',
            'domain': [('res_model', '=', model_name)],
        })

        # Register external ID
        xml_id_name = f"approval_action_{model.model.replace('.', '_')}"
        env['ir.model.data'].create({
            'name': xml_id_name,
            'model': 'ir.actions.act_window',
            'module': 'hagbes_approval_workflow',
            'res_id': action.id,
            'noupdate': True,
        })

        # Create menu
        env['ir.ui.menu'].create({
            'name': menu_name,
            'parent_id': parent_menu.id,
            'action': f'{action._name},{action.id}',
            'sequence': 10,
        })

        _logger.info("Created menu and action for model: %s", model.name)
