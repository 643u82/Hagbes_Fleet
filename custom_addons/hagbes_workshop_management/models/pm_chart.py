from odoo import models, fields

class PreventiveMaintenanceChart(models.Model):
    _name = 'workshop.pm.chart'
    _description = 'Preventive Maintenance Chart'

    name = fields.Char(default="Preventive Maintenance Chart")
    vehicle_model_id = fields.Many2one('workshop.model', string="Vehicle Model")

    item_ids = fields.One2many(
        'workshop.pm.item',
        'chart_id',
        string="Maintenance Items"
    )


class PreventiveMaintenanceItem(models.Model):
    _name = 'workshop.pm.item'
    _description = 'Maintenance Item'

    chart_id = fields.Many2one('workshop.pm.chart')

    description = fields.Char(required=True)
    instruction = fields.Char(string="Instruction")

    interval_line_ids = fields.One2many(
        'workshop.pm.interval.line',
        'item_id',
        string="Intervals"
    )


class PreventiveMaintenanceIntervalLine(models.Model):
    _name = 'workshop.pm.interval.line'
    _description = 'Maintenance Interval Action'

    item_id = fields.Many2one('workshop.pm.item')

    interval = fields.Integer(
        string="KM Interval",
        help="e.g., 5000, 10000, 15000..."
    )

    action = fields.Selection([
        ('A', 'Adjust'),
        ('I', 'Inspect'),
        ('R', 'Replace'),
        ('C', 'Clean'),
        ('-', 'None'),
    ], string="Action")
