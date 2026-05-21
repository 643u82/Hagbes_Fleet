# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HagbesFleetAllocationAppend(models.Model):
    _name = 'hagbes.fleet.allocation.append'
    _description = 'Fleet Allocation Append Request'
    _order = 'create_date desc, id desc'

    # ─── Core Relationships ───────────────────────────────────────────────────
    allocation_id = fields.Many2one(
        'hagbes.fleet.allocation',
        string='Allocation',
        required=True,
        ondelete='cascade',
        index=True,
        help='The allocation being extended',
    )
    
    # ─── Append Details ───────────────────────────────────────────────────────
    additional_destination = fields.Char(
        string='Additional Destination',
        required=True,
        help='New destination to be added to the trip',
    )
    additional_distance = fields.Float(
        string='Additional Distance (KM)',
        digits=(10, 2),
        required=True,
        help='Additional distance in kilometers for the new destination',
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        help='Justification for extending the allocation',
    )

    # ─── Metadata ─────────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # =========================================================================
    # Constraints
    # =========================================================================

    @api.constrains('additional_distance')
    def _check_additional_distance(self):
        """Ensure additional_distance is positive."""
        for rec in self:
            if rec.additional_distance <= 0:
                raise ValidationError(
                    _('Additional distance must be greater than zero.')
                )

    # =========================================================================
    # ORM Overrides
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Post chatter note to allocation on creation."""
        records = super().create(vals_list)
        for rec in records:
            rec._post_allocation_chatter_note()
        return records

    def write(self, vals):
        """Post chatter note to allocation on significant changes."""
        result = super().write(vals)
        # Post chatter note if any of the key fields changed
        if any(field in vals for field in ['additional_destination', 'additional_distance', 'reason']):
            for rec in self:
                rec._post_allocation_chatter_note()
        return result

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _post_allocation_chatter_note(self):
        """Post a summary note to the linked allocation's chatter."""
        self.ensure_one()
        if self.allocation_id:
            message = _(
                'Allocation extended with additional destination: <strong>%s</strong><br/>'
                'Additional distance: <strong>%.2f KM</strong><br/>'
                'Reason: %s'
            ) % (
                self.additional_destination,
                self.additional_distance,
                self.reason or _('No reason provided'),
            )
            self.allocation_id.message_post(
                body=message,
                subtype_xmlid='mail.mt_note',
            )

    # =========================================================================
    # Display Methods
    # =========================================================================

    def name_get(self):
        """Custom display name for the record."""
        result = []
        for rec in self:
            name = _('Append: %s (+%.2f KM)') % (
                rec.additional_destination,
                rec.additional_distance,
            )
            result.append((rec.id, name))
        return result
