# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestFleetDiscrepancy(TransactionCase):

    def setUp(self):
        super().setUp()
        
        # Create test requisition
        self.requisition = self.env['fleet.requisition'].create({
            'name': 'TEST-REQ-001',
            'date_of_request': '2027-01-15',
            'date_from': '2027-01-16 08:00:00',
            'date_to': '2027-01-16 18:00:00',
            'destination': 'Test Destination',
            'purpose': 'Test Purpose',
            'state': 'draft'
        })
        
        # Create test allocation
        self.vehicle = self.env['hagbes.fleet.vehicle'].create({
            'name': 'Test Vehicle',
            'plate_number': 'TEST-001',
            'model': 'Test Model',
            'brand': 'Test Brand',
            'engine_number': 'ENG-001',
            'chassis_number': 'CHS-001',
            'fuel_type': 'petrol',
            'acquisition_date': '2027-01-01'
        })
        
        self.driver = self.env['hr.employee'].create({
            'name': 'Test Driver'
        })
        
        self.allocation = self.env['hagbes.fleet.allocation'].create({
            'request_id': self.requisition.id,
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'allocation_date': '2027-01-15 08:00:00',
            'planned_distance': 100.0,
            'fuel_estimate': 20.0
        })

    def test_discrepancy_creation_with_allocation(self):
        """Test creating a discrepancy linked to an allocation"""
        discrepancy = self.env['hagbes.fleet.discrepancy'].create({
            'allocation_id': self.allocation.id,
            'type': 'fuel',
            'expected_value': 20.0,
            'actual_value': 25.0,
            'severity': 'medium'
        })
        
        self.assertEqual(discrepancy.variance_percent, 25.0)  # ((25-20)/20)*100 = 25%
        self.assertTrue(discrepancy.name)
        self.assertIn('Fuel Discrepancy', discrepancy.name)

    def test_discrepancy_creation_with_requisition(self):
        """Test creating a discrepancy linked to a requisition"""
        discrepancy = self.env['hagbes.fleet.discrepancy'].create({
            'request_id': self.requisition.id,
            'type': 'distance',
            'expected_value': 100.0,
            'actual_value': 120.0,
            'severity': 'low'
        })
        
        self.assertEqual(discrepancy.variance_percent, 20.0)  # ((120-100)/100)*100 = 20%

    def test_variance_percent_computation_zero_expected(self):
        """Test variance computation when expected value is zero"""
        discrepancy = self.env['hagbes.fleet.discrepancy'].create({
            'allocation_id': self.allocation.id,
            'type': 'time',
            'expected_value': 0.0,
            'actual_value': 5.0,
            'severity': 'high'
        })
        
        self.assertEqual(discrepancy.variance_percent, 0.0)

    def test_variance_percent_computation_negative(self):
        """Test variance computation with negative variance"""
        discrepancy = self.env['hagbes.fleet.discrepancy'].create({
            'allocation_id': self.allocation.id,
            'type': 'fuel',
            'expected_value': 20.0,
            'actual_value': 15.0,
            'severity': 'low'
        })
        
        self.assertEqual(discrepancy.variance_percent, -25.0)  # ((15-20)/20)*100 = -25%

    def test_constraint_no_linked_record(self):
        """Test that at least one of request_id or allocation_id must be set"""
        with self.assertRaises(ValidationError):
            self.env['hagbes.fleet.discrepancy'].create({
                'type': 'fuel',
                'expected_value': 20.0,
                'actual_value': 25.0,
                'severity': 'medium'
            })

    def test_constraint_both_linked_records(self):
        """Test that both request_id and allocation_id can be set"""
        discrepancy = self.env['hagbes.fleet.discrepancy'].create({
            'request_id': self.requisition.id,
            'allocation_id': self.allocation.id,
            'type': 'fuel',
            'expected_value': 20.0,
            'actual_value': 25.0,
            'severity': 'medium'
        })
        
        self.assertEqual(discrepancy.request_id, self.requisition)
        self.assertEqual(discrepancy.allocation_id, self.allocation)