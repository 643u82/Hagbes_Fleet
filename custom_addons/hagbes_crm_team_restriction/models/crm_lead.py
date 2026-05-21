# models/crm_lead.py
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import AccessError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    allowed_assignees = fields.Many2many(
        'res.users',
        compute='_compute_allowed_assignees',
        string="Allowed Assignees",
        store=False
    )

    user_id_readonly = fields.Boolean(
        compute='_compute_user_id_readonly',
        default=False
    )

    @api.depends('user_id')
    def _compute_user_id_readonly(self):
        """Make user_id readonly only for basic salesmen (not leaders/GMs/directors)."""
        for lead in self:
            user = self.env.user
            has_elevated_role = (
                user.has_group('hagbes_crm_team_restriction.group_crm_sales_team_leader') or
                user.has_group('hagbes_crm_team_restriction.group_crm_sales_general_manager') or
                user.has_group('hagbes_crm_team_restriction.group_operation_director') or
                user.has_group('base.group_system')
            )
            lead.user_id_readonly = (
                user.has_group('sales_team.group_sale_salesman') and not has_elevated_role
            )

    def _is_restricted_salesman(self):
        """True if user is ONLY a basic salesman (not leader, GM, or director)."""
        user = self.env.user
        has_elevated_role = (
            user.has_group('hagbes_crm_team_restriction.group_crm_sales_team_leader') or
            user.has_group('hagbes_crm_team_restriction.group_crm_sales_general_manager') or
            user.has_group('hagbes_crm_team_restriction.group_operation_director') or
            user.has_group('base.group_system')
        )
        return user.has_group('sales_team.group_sale_salesman') and not has_elevated_role

    # 🔥 CRITICAL: This ensures instant UI update when team changes
    @api.onchange("team_id")
    def _onchange_team_id_set_team_leader(self):
        """Auto-assign salesperson to team leader whenever team changes."""
        if self.team_id:
            self.user_id = self.team_id.user_id or False
        else:
            self.user_id = False

    @api.depends('team_id')
    def _compute_allowed_assignees(self):
        """Allowed assignees = team leader + team members."""
        for record in self:
            team = record.team_id.sudo() or self.env.user.sale_team_id.sudo()
            allowed = self.env['res.users']
            if team:
                allowed = team.member_ids | team.user_id
            record.allowed_assignees = allowed

    @api.model
    def create(self, vals):
        # 🔒 Block user_id assignment by restricted salesmen
        if 'user_id' in vals and self._is_restricted_salesman():
            raise exceptions.UserError(_(
                "You are not allowed to assign or change the Salesperson on leads."
            ))

        # Auto-set user_id from team if not provided
        if 'team_id' in vals and 'user_id' not in vals:
            team = self.env['crm.team'].sudo().browse(vals['team_id'])
            if team.exists() and team.user_id:
                vals['user_id'] = team.user_id.id
        elif 'team_id' not in vals and 'user_id' not in vals:
            user_team = self.env.user.sale_team_id
            if user_team:
                vals['team_id'] = user_team.id
                if user_team.user_id:
                    vals['user_id'] = user_team.user_id.id

        return super().create(vals)

    def write(self, vals):
        # 🔒 Block user_id changes by restricted salesmen
        if 'user_id' in vals and self._is_restricted_salesman():
            raise exceptions.UserError(_(
                "You are not allowed to assign or change the Salesperson on leads."
            ))

        # Auto-set user_id when team_id changes (only if user_id not explicitly set)
        if 'team_id' in vals and 'user_id' not in vals:
            team_id = vals['team_id']
            if team_id:
                team = self.env['crm.team'].sudo().browse(team_id)
                vals['user_id'] = team.user_id.id if team.exists() and team.user_id else False
            else:
                vals['user_id'] = False

        # 🔒 Restrict stage changes to owner only (unless Operation Director)
        if 'stage_id' in vals:
            for lead in self:
                if lead.user_id and lead.user_id != self.env.user:
                    if not self.env.user.has_group('hagbes_crm_team_restriction.group_operation_director'):
                        raise exceptions.UserError(_(
                            "You can only move opportunities that are assigned to you. "
                            "Lead '%s' belongs to %s."
                        ) % (lead.name, lead.user_id.name))

        res = super().write(vals)

        # Validation: salesperson must belong to the team
        for lead in self.sudo():
            if lead.team_id and lead.user_id:
                valid_users = lead.team_id.member_ids | lead.team_id.user_id
                if lead.user_id not in valid_users:
                    raise exceptions.ValidationError(_(
                        "The selected salesperson must be the leader or a member of the selected Sales Team."
                    ))
        return res

    def action_create_lead(self):
        self.ensure_one()
        real_user = self.env.user

        team = self.env['crm.team'].sudo().search([
            ('branch_id', '=', self.requester_branch_id.id)
        ], limit=1)

        if not team:
            raise AccessError(
                _("No CRM team found for branch %s") % self.requester_branch_id.display_name
            )

        if team.branch_id and real_user.allowed_branch_ids \
           and team.branch_id.id not in real_user.allowed_branch_ids.ids:
            raise AccessError(
                _("You are not allowed to create leads for this team/branch.")
            )

        lead_vals = {
            'name': "Auto: %s" % (self.name or 'Request'),
            'partner_id': self.partner_id.id,
            'team_id': team.id,
            'type': 'opportunity',
            'user_id': real_user.id,
        }
        lead = self.env['crm.lead'].sudo().create(lead_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Lead',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }