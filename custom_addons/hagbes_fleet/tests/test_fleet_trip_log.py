# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestFleetTripLog(TransactionCase):
    def setUp(self):
        super().setUp()
        
        # Create test vehicle
        self.vehicle = self.env['hagbes.fleet.vehicle'].create({
            'name': 'Test Vehicle',
            'plate_number': 'TEST123',
            'model': 'Test Model',
            'brand': 'Test Brand',
            'year': '2024',
            'engine_number': 'ENG123',
            'chassis_number': 'CHS123',
            'fuel_type': 'petrol',
            'acquisition_date': '2027-01-01',
            'cost': 50000,
        })
        
        # Create test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Driver',
            'is_driver': True,
        })
        
        # Create test requisition
        self.requisition = self.env['fleet.requisition'].create({
            'date_of_request': '2027-01-01',
            'destination': 'Test Destination',
            'date_from': '2027-01-10 08:00:00',
            'date_to': '2027-01-10 18:00:00',
            'purpose': 'Test Purpose',
        })
        
        # Create test allocation
        self.allocation = self.env['hagbes.fleet.allocation'].create({
            'request_id': self.requisition.id,
            'vehicle_id': self.vehicle.id,
            'driver_id': self.employee.id,
            'assigned_odometer': 1000.0,
            'planned_distance': 100.0,
            'fuel_estimate': 10.0,
            'allocation_date': '2027-01-10 08:00:00',
        })

    def test_trip_log_creation(self):
        """Test basic trip log creation."""
        trip_log = self.env['hagbes.fleet.trip.log'].create({
            'allocation_id': self.allocation.id,
            'start_odometer': 1000.0,
            'end_odometer': 1100.0,
            'fuel_used': 8.5,
            'start_time': '2027-01-10 08:00:00',
            'end_time': '2027-01-10 18:00:00',
        })
        
        self.assertEqual(trip_log.allocation_id, self.allocation)
        self.assertEqual(trip_log.start_odometer, 1000.0)
        self.assertEqual(trip_log.end_odometer, 1100.0)
        self.assertEqual(trip_log.actual_distance, 100.0)

    def test_actual_distance_computation(self):
        """Test that actual_distance is computed correctly."""
        trip_log = self.env['hagbes.fleet.trip.log'].create({
            'allocation_id': self.allocation.id,
            'start_odometer': 1000.0,
            'end_odometer': 1250.5,
        })
        
        self.assertEqual(trip_log.actual_distance, 250.5)

    def test_odometer_validation(self):
        """Test that end_odometer must be >= start_odometer."""
        with self.assertRaises(ValidationError):
            self.env['hagbes.fleet.trip.log'].create({
                'allocation_id': self.allocation.id,
                'start_odometer': 1100.0,
                'end_odometer': 1000.0,
            })

    def test_time_validation(self):
        """Test that end_time must be >= start_time."""
        with self.assertRaises(ValidationError):
            self.env['hagbes.fleet.trip.log'].create({
                'allocation_id': self.allocation.id,
                'start_time': '2027-01-10 18:00:00',
                'end_time': '2027-01-10 08:00:00',
            })

    def test_multiple_trip_logs_per_allocation(self):
        """Test that multiple trip logs can be created for one allocation."""
        trip_log1 = self.env['hagbes.fleet.trip.log'].create({
            'allocation_id': self.allocation.id,
            'start_odometer': 1000.0,
            'end_odometer': 1050.0,
            'start_time': '2027-01-10 08:00:00',
            'end_time': '2027-01-10 12:00:00',
        })
        
        trip_log2 = self.env['hagbes.fleet.trip.log'].create({
            'allocation_id': self.allocation.id,
            'start_odometer': 1050.0,
            'end_odometer': 1100.0,
            'start_time': '2027-01-10 13:00:00',
            'end_time': '2027-01-10 18:00:00',
        })
        
        self.assertEqual(trip_log1.actual_distance, 50.0)
        self.assertEqual(trip_log2.actual_distance, 50.0)

    def test_trip_log_with_gps_coordinates(self):
        """Test trip log with GPS coordinates text."""
        trip_log = self.env['hagbes.fleet.trip.log'].create({
            'allocation_id': self.allocation.id,
            'start_odometer': 1000.0,
            'end_odometer': 1100.0,
            'gps_coordinates': 'Start: 9.0192° N, 38.7525° E\nEnd: 9.0300° N, 38.7600° E',
        })
        
        self.assertTrue(trip_log.gps_coordinates)
        self.assertIn('9.0192', trip_log.gps_coordinates)
