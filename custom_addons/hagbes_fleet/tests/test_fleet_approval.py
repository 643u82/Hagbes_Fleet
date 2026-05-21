# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestFleetApprovalIntegration(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.user.company_id
        self.user_group = self.env.ref('base.group_system')

        self.env['ir.config_parameter'].sudo().set_param('fleet.approval.maintenance_threshold', '10000')
        self.env['ir.config_parameter'].sudo().set_param('fleet.approval.enable_assignment', 'True')
        self.env['ir.config_parameter'].sudo().set_param('fleet.approval.enable_disposal', 'True')

        self.vehicle = self.env['hagbes.fleet.vehicle'].create({
            'name': 'Test Car',
            'plate_number': 'ABC123',
            'model': 'Model X',
            'brand': 'BrandY',
            'year': '2022',
            'engine_number': 'EN123',
            'chassis_number': 'CH123',
            'fuel_type': 'petrol',
            'acquisition_date': '2024-01-01',
            'cost': 50000,
        })
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Driver',
            'is_driver': True,
        })

        self.assignment_flow = self._create_flow(
            'Test Fleet Assignment',
            'fleet_assignment',
            'hagbes.fleet.vehicle.assign',
        )
        self.maintenance_flow = self._create_flow(
            'Test Fleet Maintenance',
            'fleet_maintenance',
            'hagbes.fleet.maintenance',
        )
        self.disposal_flow = self._create_flow(
            'Test Fleet Disposal',
            'fleet_disposal',
            'hagbes.fleet.vehicle',
        )

    def _create_flow(self, name, request_type, model_name):
        auto_initiate = self.env['approval.action'].search([('code', '=', 'auto_initiate')], limit=1)
        approve_action = self.env['approval.action'].search([('code', '=', 'approve')], limit=1)
        reject_action = self.env['approval.action'].search([('code', '=', 'reject')], limit=1)
        flow = self.env['approval.flow'].create({
            'name': name,
            'request_type': request_type,
            'request_model_id': self.env['ir.model']._get_id(model_name),
            'company_id': self.company.id,
        })
        initiator = self.env['approval.step'].create({
            'flow_id': flow.id,
            'name': '%s Initiator' % name,
            'sequence': 1,
            'is_initiator': True,
            'company_id': self.company.id,
        })
        manager = self.env['approval.step'].create({
            'flow_id': flow.id,
            'name': '%s Manager Review' % name,
            'sequence': 10,
            'role_id': self.user_group.id,
            'company_id': self.company.id,
        })
        final = self.env['approval.step'].create({
            'flow_id': flow.id,
            'name': '%s Final' % name,
            'sequence': 20,
            'is_final': True,
            'company_id': self.company.id,
        })
        self.env['approval.step.action'].create({
            'step_id': initiator.id,
            'action_id': auto_initiate.id,
            'next_step_id': manager.id,
        })
        self.env['approval.step.action'].create({
            'step_id': manager.id,
            'action_id': approve_action.id,
            'next_step_id': final.id,
        })
        self.env['approval.step.action'].create({
            'step_id': manager.id,
            'action_id': reject_action.id,
        })
        return flow

    def test_assignment_requires_approval(self):
        assign = self.env['hagbes.fleet.vehicle.assign'].create({
            'vehicle_id': self.vehicle.id,
            'employee_id': self.employee.id,
            'start_date': '2024-01-10',
        })

        assign.action_submit()

        request = self.env['approval.request'].search([
            ('res_model', '=', 'hagbes.fleet.vehicle.assign'),
            ('res_id', '=', assign.id),
        ], limit=1)
        self.assertTrue(request)
        self.assertEqual(assign.state, 'pending')
        self.assertEqual(request.current_step_id.role_id, self.user_group)
        self.assertTrue(request.approver_ids)

    def test_assignment_without_approval_activates_vehicle(self):
        self.env['ir.config_parameter'].sudo().set_param('fleet.approval.enable_assignment', 'False')
        assign = self.env['hagbes.fleet.vehicle.assign'].create({
            'vehicle_id': self.vehicle.id,
            'employee_id': self.employee.id,
            'start_date': '2024-01-10',
        })

        assign.action_submit()

        self.assertEqual(assign.state, 'active')
        self.assertEqual(self.vehicle.status, 'assigned')

    def test_assignment_approval_callback_activates_vehicle(self):
        assign = self.env['hagbes.fleet.vehicle.assign'].create({
            'vehicle_id': self.vehicle.id,
            'employee_id': self.employee.id,
            'start_date': '2024-01-10',
        })
        assign.action_submit()

        request = self.env['approval.request'].search([
            ('res_model', '=', 'hagbes.fleet.vehicle.assign'),
            ('res_id', '=', assign.id),
        ], limit=1)
        request.with_user(request.approver_ids[:1]).with_context(action_type='approve', comment='Looks good').process_action()

        self.assertEqual(request.status, 'approved')
        self.assertEqual(assign.state, 'active')
        self.assertEqual(self.vehicle.status, 'assigned')

    def test_assignment_rejection_callback_marks_record_rejected(self):
        assign = self.env['hagbes.fleet.vehicle.assign'].create({
            'vehicle_id': self.vehicle.id,
            'employee_id': self.employee.id,
            'start_date': '2024-01-10',
        })
        assign.action_submit()

        request = self.env['approval.request'].search([
            ('res_model', '=', 'hagbes.fleet.vehicle.assign'),
            ('res_id', '=', assign.id),
        ], limit=1)
        request.with_user(request.approver_ids[:1]).with_context(action_type='reject', comment='Rejected').process_action()

        self.assertEqual(request.status, 'rejected')
        self.assertEqual(assign.state, 'rejected')
        self.assertEqual(self.vehicle.status, 'available')

    def test_maintenance_threshold_logic(self):
        maint = self.env['hagbes.fleet.maintenance'].create({
            'vehicle_id': self.vehicle.id,
            'service_type': 'corrective',
            'service_date': '2024-02-01',
            'cost': 20000,
        })

        maint.action_submit()

        request = self.env['approval.request'].search([
            ('res_model', '=', 'hagbes.fleet.maintenance'),
            ('res_id', '=', maint.id),
        ], limit=1)
        self.assertTrue(request)
        self.assertEqual(maint.state, 'pending')

    def test_maintenance_without_approval_activates_vehicle(self):
        self.env['ir.config_parameter'].sudo().set_param('fleet.approval.maintenance_threshold', '50000')
        maint = self.env['hagbes.fleet.maintenance'].create({
            'vehicle_id': self.vehicle.id,
            'service_type': 'corrective',
            'service_date': '2024-02-01',
            'cost': 20000,
        })

        maint.action_submit()

        self.assertEqual(maint.state, 'active')
        self.assertEqual(self.vehicle.status, 'maintenance')

    def test_disposal_waits_for_approval_then_marks_out_of_service(self):
        self.vehicle.action_request_disposal()

        request = self.env['approval.request'].search([
            ('res_model', '=', 'hagbes.fleet.vehicle'),
            ('res_id', '=', self.vehicle.id),
        ], limit=1)
        self.assertTrue(request)
        self.assertEqual(self.vehicle.status, 'waiting_approval')

        request.with_user(request.approver_ids[:1]).with_context(action_type='approve', comment='Dispose it').process_action()

        self.assertEqual(request.status, 'approved')
        self.assertEqual(self.vehicle.status, 'out_of_service')

    def test_missing_approval_flow_error(self):
        self.assignment_flow.active = False
        self.env['approval.flow'].search([
            ('request_type', '=', 'fleet_assignment'),
            ('company_id', '=', False),
        ]).write({'active': False})

        assign = self.env['hagbes.fleet.vehicle.assign'].create({
            'vehicle_id': self.vehicle.id,
            'employee_id': self.employee.id,
            'start_date': '2024-01-10',
        })

        with self.assertRaises(ValidationError):
            assign.action_submit()

    def test_deleted_record_does_not_break_approval_rejection(self):
        maint = self.env['hagbes.fleet.maintenance'].create({
            'vehicle_id': self.vehicle.id,
            'service_type': 'preventive',
            'service_date': '2024-03-01',
            'cost': 20000,
        })
        maint.action_submit()
        request = self.env['approval.request'].search([
            ('res_model', '=', 'hagbes.fleet.maintenance'),
            ('res_id', '=', maint.id),
        ], limit=1)

        maint.unlink()
        request.with_user(request.approver_ids[:1]).with_context(action_type='reject', comment='Record removed').process_action()

        self.assertEqual(request.status, 'rejected')
