from odoo import models, fields, api

class CrmTeam(models.Model):
    _inherit = 'crm.team'

    branch_id = fields.Many2one(
        'account.analytic.account',
        string="Branch",
        domain=lambda self: self._get_branch_domain(),
        help="Branch to which this Sales Team belongs"
    )

    @api.model
    def _get_branch_domain(self):
        user = self.env.user
        branch_ids = getattr(user, 'allowed_branch_ids', False)
        if branch_ids:
            return [('id', 'in', branch_ids.ids)]
        return []

    def write(self, vals):
        group_leader = self.env.ref('hagbes_crm_team_restriction.group_crm_sales_team_leader').sudo()
        group_sales_user = self.env.ref('sales_team.group_sale_salesman').sudo()

        for team in self:
            old_leader = team.user_id
            old_members = team.member_ids

            res = super(CrmTeam, team).write(vals)

            # =====  HANDLE LEADER GROUP =====
            new_leader = team.user_id
            if new_leader:
                new_leader.sudo().write({'groups_id': [(4, group_leader.id)]})

            if old_leader and old_leader != new_leader:
                other_teams = self.sudo().search([('user_id', '=', old_leader.id)])
                if not other_teams:
                    old_leader.sudo().write({'groups_id': [(3, group_leader.id)]})

            # =====  HANDLE MEMBER GROUP =====
            new_members = team.member_ids

            # Add group to new members
            for member in new_members:
                member.sudo().write({'groups_id': [(4, group_sales_user.id)]})

            # Optionally remove from users no longer in this or any other team
            removed_members = old_members - new_members
            for member in removed_members:
                other_teams = self.sudo().search([('member_ids', 'in', [member.id])])
                if not other_teams:
                    member.sudo().write({'groups_id': [(3, group_sales_user.id)]})

        return res


    @api.model_create_multi
    def create(self, vals_list):
        """Also apply group assignment when a team is first created."""
        group_leader = self.env.ref('hagbes_crm_team_restriction.group_crm_sales_team_leader').sudo()
        group_sales_user = self.env.ref('sales_team.group_sale_salesman').sudo()

        teams = super(CrmTeam, self).create(vals_list)

        for team in teams:
            # Assign group to leader
            if team.user_id:
                team.user_id.sudo().write({'groups_id': [(4, group_leader.id)]})

            # Assign group to members
            for member in team.member_ids:
                member.sudo().write({'groups_id': [(4, group_sales_user.id)]})

        return teams
