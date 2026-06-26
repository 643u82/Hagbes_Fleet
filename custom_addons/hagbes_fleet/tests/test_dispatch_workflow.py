# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError
from datetime import datetime, timedelta

@tagged('dispatch_workflow', 'post_install', '-at_install')
class TestDispatchWorkflow(TransactionCase):

    def setUp(self):
        super().setUp()

        self.future_date_from = datetime.now() + timedelta(days=1)
        self.future_date_to = datetime.now() + timedelta(days=2)

        # Create test requisition with future dates
        self.requisition = self.env['fleet.requisition'].create({
            'name': 'TEST-REQ-100',
            'date_from': self.future_date_from,
            'date_to': self.future_date_to,
            'destination': 'Addis Ababa',
            'purpose': 'Official Meeting',
            'state': 'draft',
        })

        self.vehicle = self.env['hagbes.fleet.vehicle'].create({
            'name': 'Toyota Hilux Test',
            'plate_number': 'TEST-HILUX-123',
            'model': 'Hilux',
            'brand': 'Toyota',
            'engine_number': 'ENG-HILUX-123',
            'chassis_number': 'CHS-HILUX-123',
            'fuel_type': 'diesel',
            'acquisition_date': '2027-01-01',
            'kmperl': 12.5,
        })

        self.driver = self.env['hr.employee'].create({
            'name': 'Abebe Driver',
            'is_driver': True,
        })

    def test_dispatch_workflow_from_requisition(self):
        """Test that confirming allocation creates a trip and links all records."""
        # 1. Transition requisition state to team_leader_approved, then assigned
        self.requisition.write({'state': 'team_leader_approved'})
        self.requisition.write({'state': 'assigned'})

        # 2. Create allocation in draft
        allocation = self.env['hagbes.fleet.allocation'].create({
            'request_id': self.requisition.id,
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'allocation_date': self.future_date_from,
            'planned_distance': 150.0,
            'fuel_estimate': 15.0,
            'assigned_odometer': 12000.0,
        })

        # Verify allocation linked back to requisition
        self.assertEqual(self.requisition.allocation_id, allocation)

        # 3. Call action_assign_vehicle (Confirm Assignment button on allocation)
        action = allocation.action_assign_vehicle()

        # 4. Verify states and linkages
        self.assertEqual(self.requisition.state, 'assigned')
        self.assertEqual(allocation.state, 'assigned')

        # Verify trip was created and linked
        self.assertTrue(allocation.trip_id)
        self.assertEqual(self.requisition.trip_id, allocation.trip_id)

        # Verify the returned action opens the start trip form view
        self.assertEqual(action.get('res_model'), 'fleet.trip')
        self.assertEqual(action.get('res_id'), allocation.trip_id.id)
        self.assertEqual(action.get('view_mode'), 'form')

        # 5. Verify the trip has correctly inherited all values from requisition and allocation
        trip = allocation.trip_id
        self.assertEqual(trip.vehicle_id, self.vehicle)
        self.assertEqual(trip.driver_name, self.driver.name)
        self.assertEqual(trip.km_at_start, 12000.0)
        self.assertEqual(trip.planned_route_distance, 150.0)
        self.assertEqual(trip.fuel_at_start, 15.0)
        self.assertIn(self.requisition, trip.requisition_ids)

    def test_onchange_allocation_auto_population(self):
        """Test that allocation onchange handler correctly auto-populates fields on the trip form."""
        allocation = self.env['hagbes.fleet.allocation'].create({
            'request_id': self.requisition.id,
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'allocation_date': self.future_date_from,
            'planned_distance': 250.0,
            'fuel_estimate': 25.0,
            'assigned_odometer': 15500.0,
        })

        # Create a new blank trip (not linked yet)
        trip = self.env['fleet.trip'].new({
            'allocation_id': allocation.id,
        })

        # Trigger onchange manually
        trip._onchange_allocation_id()

        # Verify auto-populated values on UI form proxy
        self.assertEqual(trip.vehicle_id, self.vehicle)
        self.assertEqual(trip.planned_route_distance, 250.0)
        self.assertEqual(trip.km_at_start, 15500.0)
        self.assertEqual(trip.fuel_at_start, 25.0)
