# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class TestFleetVehicleStatusLog(TransactionCase):

    def setUp(self):
        super().setUp()
        # Create a test vehicle
        self.vehicle = self.env['hagbes.fleet.vehicle'].create({
            'name': 'Test Vehicle',
            'plate_number': 'TEST-001',
            'model': 'Test Model',
            'brand': 'Test Brand',
            'engine_number': 'ENG001',
            'chassis_number': 'CHS001',
            'fuel_type': 'petrol',
            'acquisition_date': date.today(),
        })

    def test_create_status_log(self):
        """Test creating a vehicle status log"""
        status_log = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 15000.0,
            'fuel_level': 45.5,
            'condition_notes': 'Vehicle in good condition',
            'date': date.today(),
        })
        
        self.assertEqual(status_log.vehicle_id, self.vehicle)
        self.assertEqual(status_log.odometer, 15000.0)
        self.assertEqual(status_log.fuel_level, 45.5)
        self.assertEqual(status_log.condition_notes, 'Vehicle in good condition')
        self.assertEqual(status_log.date, date.today())

    def test_unique_vehicle_date_constraint(self):
        """Test that only one status log per vehicle per date is allowed"""
        # Create first status log
        self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 15000.0,
            'fuel_level': 45.5,
            'date': date.today(),
        })
        
        # Try to create another status log for the same vehicle and date
        with self.assertRaises(ValidationError):
            self.env['hagbes.fleet.vehicle.status.log'].create({
                'vehicle_id': self.vehicle.id,
                'odometer': 15100.0,
                'fuel_level': 40.0,
                'date': date.today(),
            })

    def test_different_dates_allowed(self):
        """Test that multiple status logs for different dates are allowed"""
        # Create status log for today
        log1 = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 15000.0,
            'fuel_level': 45.5,
            'date': date.today(),
        })
        
        # Create status log for yesterday
        log2 = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 14950.0,
            'fuel_level': 50.0,
            'date': date.today() - timedelta(days=1),
        })
        
        self.assertEqual(len(self.vehicle.status_log_ids), 2)
        self.assertIn(log1, self.vehicle.status_log_ids)
        self.assertIn(log2, self.vehicle.status_log_ids)

    def test_display_name_computation(self):
        """Test display name computation"""
        status_log = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 15000.0,
            'date': date.today(),
        })
        
        expected_name = f"{self.vehicle.name} - {date.today()}"
        self.assertEqual(status_log.display_name, expected_name)

    def test_chatter_integration(self):
        """Test that creating a status log posts a message to the vehicle"""
        # Count initial messages
        initial_message_count = len(self.vehicle.message_ids)
        
        # Create status log
        self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 15000.0,
            'fuel_level': 45.5,
            'condition_notes': 'Test condition notes',
            'date': date.today(),
        })
        
        # Check that a message was posted
        self.assertGreater(len(self.vehicle.message_ids), initial_message_count)
        
        # Check message content
        latest_message = self.vehicle.message_ids[0]
        self.assertIn('Status log created', latest_message.body)
        self.assertIn('15000.0', latest_message.body)
        self.assertIn('45.5', latest_message.body)

    def test_default_order(self):
        """Test that status logs are ordered by date descending"""
        # Create logs for different dates
        log1 = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 14900.0,
            'date': date.today() - timedelta(days=2),
        })
        
        log2 = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 15000.0,
            'date': date.today(),
        })
        
        log3 = self.env['hagbes.fleet.vehicle.status.log'].create({
            'vehicle_id': self.vehicle.id,
            'odometer': 14950.0,
            'date': date.today() - timedelta(days=1),
        })
        
        # Search all logs and check order
        all_logs = self.env['hagbes.fleet.vehicle.status.log'].search([
            ('vehicle_id', '=', self.vehicle.id)
        ])
        
        # Should be ordered by date desc: log2 (today), log3 (yesterday), log1 (2 days ago)
        self.assertEqual(all_logs[0], log2)
        self.assertEqual(all_logs[1], log3)
        self.assertEqual(all_logs[2], log1)

        