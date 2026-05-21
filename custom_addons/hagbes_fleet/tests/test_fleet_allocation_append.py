# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestFleetAllocationAppend(TransactionCase):

    def setUp(self):
        super().setUp()
        
        # Create test data
        self.company = self.env.ref('base.main_company')
        
        # Create a test employee (driver)
        self.driver = self.env['hr.employee'].create({
            'name': 'Test Driver',
            'company_id': self.company.id,
        })
        
        # Create a test vehicle
        self.vehicle = self.env['hagbes.fleet.vehicle'].create({
            'name': 'Test Vehicle',
            'plate_number': 'TEST-001',
            'model': 'Test Model',
            'brand': 'Test Brand',
            'engine_number': 'ENG-001',
            'chassis_number': 'CHS-001',
            'fuel_type': 'petrol',
            'acquisition_date': '2024-01-01',
            'company_id': self.company.id,
        })
        
        # Create a test requisition
        self.requisition = self.env['fleet.requisition'].create({
            'name': 'TEST-REQ-001',
            'date_of_request': '2024-01-01',
            'department_id': self.env.ref('hr.dep_administration').id,
            'date_from': '2024-01-02 08:00:00',
            'date_to': '2024-01-02 18:00:00',
            'purpose': 'Test purpose',
            'company_id': self.company.id,
        })
        
        # Create a test allocation
        self.allocation = self.env['hagbes.fleet.allocation'].create({
            'request_id': self.requisition.id,
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'allocation_date': '2024-01-02 08:00:00',
            'planned_distance': 100.0,
            'fuel_estimate': 15.0,
            'company_id': self.company.id,
        })

    def test_create_allocation_append(self):
        """Test creating an allocation append request."""
        append_request = self.env['hagbes.fleet.allocation.append'].create({
            'allocation_id': self.allocation.id,
            'additional_destination': 'Regional Office',
            'additional_distance': 50.0,
            'reason': 'Need to visit regional office for additional meeting',
            'company_id': self.company.id,
        })
        
        self.assertEqual(append_request.allocation_id, self.allocation)
        self.assertEqual(append_request.additional_destination, 'Regional Office')
        self.assertEqual(append_request.additional_distance, 50.0)
        self.assertEqual(append_request.reason, 'Need to visit regional office for additional meeting')

    def test_allocation_append_validation_positive_distance(self):
        """Test that additional_distance must be positive."""
        with self.assertRaises(ValidationError):
            self.env['hagbes.fleet.allocation.append'].create({
                'allocation_id': self.allocation.id,
                'additional_destination': 'Regional Office',
                'additional_distance': -10.0,  # Negative distance should fail
                'reason': 'Test reason',
                'company_id': self.company.id,
            })

    def test_allocation_append_validation_zero_distance(self):
        """Test that additional_distance cannot be zero."""
        with self.assertRaises(ValidationError):
            self.env['hagbes.fleet.allocation.append'].create({
                'allocation_id': self.allocation.id,
                'additional_destination': 'Regional Office',
                'additional_distance': 0.0,  # Zero distance should fail
                'reason': 'Test reason',
                'company_id': self.company.id,
            })

    def test_allocation_append_name_get(self):
        """Test the custom name_get method."""
        append_request = self.env['hagbes.fleet.allocation.append'].create({
            'allocation_id': self.allocation.id,
            'additional_destination': 'Regional Office',
            'additional_distance': 50.0,
            'reason': 'Test reason',
            'company_id': self.company.id,
        })
        
        name = append_request.name_get()[0][1]
        expected_name = 'Append: Regional Office (+50.00 KM)'
        self.assertEqual(name, expected_name)

    def test_allocation_append_chatter_integration(self):
        """Test that creating an append request posts a chatter note to the allocation."""
        # Count initial messages
        initial_message_count = len(self.allocation.message_ids)
        
        # Create append request
        self.env['hagbes.fleet.allocation.append'].create({
            'allocation_id': self.allocation.id,
            'additional_destination': 'Regional Office',
            'additional_distance': 50.0,
            'reason': 'Need to visit regional office',
            'company_id': self.company.id,
        })
        
        # Check that a new message was posted
        self.assertGreater(len(self.allocation.message_ids), initial_message_count)
        
        # Check the content of the latest message
        latest_message = self.allocation.message_ids[0]  # Messages are ordered by date desc
        self.assertIn('Regional Office', latest_message.body)
        self.assertIn('50.00 KM', latest_message.body)

    def test_allocation_one2many_relationship(self):
        """Test the One2many relationship from allocation to append requests."""
        # Initially no append requests
        self.assertEqual(len(self.allocation.append_request_ids), 0)
        
        # Create append request
        append_request = self.env['hagbes.fleet.allocation.append'].create({
            'allocation_id': self.allocation.id,
            'additional_destination': 'Regional Office',
            'additional_distance': 50.0,
            'reason': 'Test reason',
            'company_id': self.company.id,
        })
        
        # Check the relationship
        self.assertEqual(len(self.allocation.append_request_ids), 1)
        self.assertEqual(self.allocation.append_request_ids[0], append_request)

    def test_multiple_append_requests(self):
        """Test that multiple append requests can be created for one allocation."""
        # Create first append request
        append1 = self.env['hagbes.fleet.allocation.append'].create({
            'allocation_id': self.allocation.id,
            'additional_destination': 'Regional Office',
            'additional_distance': 50.0,
            'reason': 'First extension',
            'company_id': self.company.id,
        })
        
        # Create second append request
        append2 = self.env['hagbes.fleet.allocation.append'].create({
            'allocation_id': self.allocation.id,
            'additional_destination': 'Client Site',
            'additional_distance': 30.0,
            'reason': 'Second extension',
            'company_id': self.company.id,
        })
        
        # Check both are linked to the allocation
        self.assertEqual(len(self.allocation.append_request_ids), 2)
        self.assertIn(append1, self.allocation.append_request_ids)
        self.assertIn(append2, self.allocation.append_request_ids)