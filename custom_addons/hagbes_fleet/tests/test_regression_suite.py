#!/usr/bin/env python3
"""
HAGBES FLEET AUTOMATED REGRESSION TEST SUITE
============================================

Comprehensive regression test suite that validates critical functionality
and prevents future regressions in the hagbes_fleet module.

Test Categories:
- Approval workflow integrity
- Security access control
- State transition validation
- Data consistency checks
- Integration functionality
"""

import unittest
import logging
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError, UserError
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


@tagged('hagbes_fleet', 'regression')
class TestFleetRequisitionRegressionSuite(TransactionCase):
    """Regression test suite for fleet requisition functionality."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test users for different roles
        cls.requester_user = cls.env['res.users'].create({
            'name': 'Test Requester',
            'login': 'test_requester',
            'email': 'requester@test.com',
            'groups_id': [(6, 0, [cls.env.ref('hagbes_fleet.group_fleet_requester').id])]
        })
        
        cls.dept_manager_user = cls.env['res.users'].create({
            'name': 'Test Dept Manager',
            'login': 'test_dept_manager',
            'email': 'dept_manager@test.com',
            'groups_id': [(6, 0, [cls.env.ref('hagbes_fleet.group_dept_manager').id])]
        })
        
        cls.fleet_manager_user = cls.env['res.users'].create({
            'name': 'Test Fleet Manager',
            'login': 'test_fleet_manager',
            'email': 'fleet_manager@test.com',
            'groups_id': [(6, 0, [cls.env.ref('hagbes_fleet.group_fleet_manager').id])]
        })
        
        cls.fmo_user = cls.env['res.users'].create({
            'name': 'Test FMO',
            'login': 'test_fmo',
            'email': 'fmo@test.com',
            'groups_id': [(6, 0, [cls.env.ref('hagbes_fleet.group_fmo').id])]
        })
        
        # Create test department
        cls.test_department = cls.env['hr.department'].create({
            'name': 'Test Department',
            'manager_id': cls.dept_manager_user.employee_id.id if cls.dept_manager_user.employee_id else False
        })
        
        # Create test employee for requester
        cls.requester_employee = cls.env['hr.employee'].create({
            'name': 'Test Requester Employee',
            'user_id': cls.requester_user.id,
            'department_id': cls.test_department.id
        })
    
    def setUp(self):
        super().setUp()
        
        # Create base test requisition
        self.test_requisition = self.env['fleet.requisition'].with_user(self.requester_user).create({
            'purpose': 'Test Trip for Regression Testing',
            'destination': 'Test Destination',
            'date_from': datetime.now() + timedelta(days=1),
            'date_to': datetime.now() + timedelta(days=2),
            'traveller_count': '1',
            'request_by': self.requester_user.id,
            'department_id': self.test_department.id
        })
    
    def test_01_approval_workflow_state_progression(self):
        """Test that approval workflow progresses through correct states."""
        _logger.info("🧪 Testing approval workflow state progression...")
        
        requisition = self.test_requisition
        
        # Initial state should be draft
        self.assertEqual(requisition.state, 'draft')
        
        # Submit requisition
        requisition.with_user(self.requester_user).action_submit()
        self.assertEqual(requisition.state, 'submitted')
        
        # Department manager approval should move to dept_approved
        requisition.with_user(self.dept_manager_user).action_dept_approve()
        self.assertEqual(requisition.state, 'dept_approved')
        
        # Fleet officer assignment should move to assigned
        requisition.with_user(self.fleet_manager_user).action_fleet_approve()
        self.assertEqual(requisition.state, 'assigned')
        
        # FMO dispatch should move to dispatched
        requisition.with_user(self.fmo_user).action_fmo_approve()
        self.assertEqual(requisition.state, 'dispatched')
        
        _logger.info("✅ Approval workflow state progression test passed")
    
    def test_02_security_access_control_enforcement(self):
        """Test that security access controls are properly enforced."""
        _logger.info("🧪 Testing security access control enforcement...")
        
        requisition = self.test_requisition
        
        # Requester should not be able to approve their own request
        with self.assertRaises((AccessError, UserError)):
            requisition.with_user(self.requester_user).action_approve()
        
        # Department manager should not be able to approve without submission
        with self.assertRaises((AccessError, UserError)):
            requisition.with_user(self.dept_manager_user).action_approve()
        
        # Submit first
        requisition.with_user(self.requester_user).action_submit()
        
        # Fleet manager should not be able to approve dept stage
        with self.assertRaises((AccessError, UserError)):
            requisition.with_user(self.fleet_manager_user).action_approve()
        
        # FMO should not be able to approve dept stage
        with self.assertRaises((AccessError, UserError)):
            requisition.with_user(self.fmo_user).action_approve()
        
        _logger.info("✅ Security access control enforcement test passed")
    
    def test_03_permission_field_computation(self):
        """Test that permission fields are computed correctly."""
        _logger.info("🧪 Testing permission field computation...")
        
        requisition = self.test_requisition
        
        # Test draft state permissions
        requisition.with_user(self.requester_user)._compute_permissions()
        self.assertTrue(requisition.can_submit)
        self.assertFalse(requisition.can_dept_approve)
        self.assertFalse(requisition.can_fleet_approve)
        self.assertFalse(requisition.can_fmo_approve)
        
        # Submit and test submitted state permissions
        requisition.with_user(self.requester_user).action_submit()
        
        # Department manager permissions
        requisition.with_user(self.dept_manager_user)._compute_permissions()
        self.assertTrue(requisition.can_dept_approve)
        self.assertFalse(requisition.can_fleet_approve)
        self.assertFalse(requisition.can_fmo_approve)
        
        # Fleet manager permissions in submitted state
        requisition.with_user(self.fleet_manager_user)._compute_permissions()
        self.assertFalse(requisition.can_dept_approve)
        self.assertFalse(requisition.can_fleet_approve)
        self.assertFalse(requisition.can_fmo_approve)
        
        _logger.info("✅ Permission field computation test passed")
    
    def test_04_state_transition_validation(self):
        """Test that invalid state transitions are prevented."""
        _logger.info("🧪 Testing state transition validation...")
        
        requisition = self.test_requisition
        
        # Cannot write invalid legacy states directly
        with self.assertRaises((AccessError, ValidationError, UserError)):
            requisition.write({'state': 'fmo_approved'})
        
        # Cannot skip approval steps
        requisition.with_user(self.requester_user).action_submit()
        
        with self.assertRaises((AccessError, UserError)):
            requisition.with_user(self.fmo_user).action_fmo_approve()
        
        # Must follow proper sequence
        requisition.with_user(self.dept_manager_user).action_dept_approve()
        self.assertEqual(requisition.state, 'dept_approved')
        
        # Now fleet manager can assign vehicle
        requisition.with_user(self.fleet_manager_user).action_fleet_approve()
        self.assertEqual(requisition.state, 'assigned')
        
        _logger.info("✅ State transition validation test passed")
    
    def test_05_data_consistency_validation(self):
        """Test data consistency validation rules."""
        _logger.info("🧪 Testing data consistency validation...")
        
        # Test date validation
        with self.assertRaises(ValidationError):
            self.env['fleet.requisition'].with_user(self.requester_user).create({
                'purpose': 'Invalid Date Test',
                'destination': 'Test Destination',
                'date_from': datetime.now() + timedelta(days=2),
                'date_to': datetime.now() + timedelta(days=1),  # End before start
                'traveller_count': '1',
                'request_by': self.requester_user.id,
                'department_id': self.test_department.id
            })
        
        # Test past date validation
        with self.assertRaises(ValidationError):
            self.env['fleet.requisition'].with_user(self.requester_user).create({
                'purpose': 'Past Date Test',
                'destination': 'Test Destination',
                'date_from': datetime.now() - timedelta(days=1),  # Past date
                'date_to': datetime.now() + timedelta(days=1),
                'traveller_count': '1',
                'request_by': self.requester_user.id,
                'department_id': self.test_department.id
            })
        
        _logger.info("✅ Data consistency validation test passed")
    
    def test_06_duplicate_prevention(self):
        """Test duplicate requisition prevention."""
        _logger.info("🧪 Testing duplicate requisition prevention...")
        
        requisition = self.test_requisition
        
        # Try to create duplicate requisition
        with self.assertRaises(ValidationError):
            self.env['fleet.requisition'].with_user(self.requester_user).create({
                'purpose': requisition.purpose,  # Same purpose
                'destination': 'Different Destination',
                'date_from': requisition.date_from,  # Same date
                'date_to': requisition.date_to,
                'traveller_count': '1',
                'request_by': self.requester_user.id,
                'department_id': self.test_department.id  # Same department
            })
        
        _logger.info("✅ Duplicate prevention test passed")
    
    def test_07_rejection_workflow(self):
        """Test rejection workflow functionality."""
        _logger.info("🧪 Testing rejection workflow...")
        
        requisition = self.test_requisition
        
        # Submit requisition
        requisition.with_user(self.requester_user).action_submit()
        
        # Department manager rejects
        requisition.with_user(self.dept_manager_user).action_reject()
        self.assertEqual(requisition.state, 'rejected')
        
        # Test resubmission
        requisition.with_user(self.requester_user).action_resubmit()
        self.assertEqual(requisition.state, 'draft')
        
        _logger.info("✅ Rejection workflow test passed")
    
    def test_08_cancellation_rules(self):
        """Test cancellation rules and restrictions."""
        _logger.info("🧪 Testing cancellation rules...")
        
        requisition = self.test_requisition
        
        # Can cancel in draft state
        requisition.with_user(self.requester_user).action_cancel()
        self.assertEqual(requisition.state, 'cancelled')
        
        # Create new requisition for further testing
        requisition2 = self.env['fleet.requisition'].with_user(self.requester_user).create({
            'purpose': 'Cancellation Test 2',
            'destination': 'Test Destination 2',
            'date_from': datetime.now() + timedelta(days=3),
            'date_to': datetime.now() + timedelta(days=4),
            'traveller_count': '1',
            'request_by': self.requester_user.id,
            'department_id': self.test_department.id
        })
        
        # Submit and advance to an operational stage
        requisition2.with_user(self.requester_user).action_submit()
        requisition2.with_user(self.dept_manager_user).action_dept_approve()
        requisition2.with_user(self.fleet_manager_user).action_fleet_approve()
        
        # Simulate dispatch
        requisition2.write({'state': 'dispatched'})
        
        # Cannot cancel dispatched requisition
        with self.assertRaises(UserError):
            requisition2.with_user(self.requester_user).action_cancel()
        
        _logger.info("✅ Cancellation rules test passed")
    
    def test_09_department_isolation(self):
        """Test department isolation in record rules."""
        _logger.info("🧪 Testing department isolation...")
        
        # Create another department and user
        other_department = self.env['hr.department'].create({
            'name': 'Other Department'
        })
        
        other_user = self.env['res.users'].create({
            'name': 'Other Dept User',
            'login': 'other_dept_user',
            'email': 'other@test.com',
            'groups_id': [(6, 0, [self.env.ref('hagbes_fleet.group_fleet_requester').id])]
        })
        
        other_employee = self.env['hr.employee'].create({
            'name': 'Other Dept Employee',
            'user_id': other_user.id,
            'department_id': other_department.id
        })
        
        # Create requisition in other department
        other_requisition = self.env['fleet.requisition'].with_user(other_user).create({
            'purpose': 'Other Department Test',
            'destination': 'Other Destination',
            'date_from': datetime.now() + timedelta(days=1),
            'date_to': datetime.now() + timedelta(days=2),
            'traveller_count': '1',
            'request_by': other_user.id,
            'department_id': other_department.id
        })
        
        # Original requester should not see other department's requisition
        visible_requisitions = self.env['fleet.requisition'].with_user(self.requester_user).search([])
        self.assertNotIn(other_requisition, visible_requisitions)
        
        _logger.info("✅ Department isolation test passed")
    
    def test_10_integration_approval_workflow(self):
        """Test integration with hagbes_approval_workflow module."""
        _logger.info("🧪 Testing approval workflow integration...")
        
        requisition = self.test_requisition
        
        # Submit should create approval request
        requisition.with_user(self.requester_user).action_submit()
        
        # Check that approval request was created
        approval_request = self.env['approval.request'].search([
            ('res_model', '=', 'fleet.requisition'),
            ('res_id', '=', requisition.id)
        ])
        
        self.assertTrue(approval_request, "Approval request should be created")
        self.assertEqual(approval_request.status, 'pending')
        
        _logger.info("✅ Approval workflow integration test passed")


@tagged('hagbes_fleet', 'regression', 'security')
class TestFleetSecurityRegressionSuite(TransactionCase):
    """Security-focused regression test suite."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test users
        cls.requester_user = cls.env['res.users'].create({
            'name': 'Security Test Requester',
            'login': 'security_requester',
            'email': 'security_requester@test.com',
            'groups_id': [(6, 0, [cls.env.ref('hagbes_fleet.group_fleet_requester').id])]
        })
        
        cls.admin_user = cls.env['res.users'].create({
            'name': 'Security Test Admin',
            'login': 'security_admin',
            'email': 'security_admin@test.com',
            'groups_id': [(6, 0, [cls.env.ref('hagbes_fleet.group_fleet_admin').id])]
        })
    
    def test_01_requester_cannot_access_sensitive_models(self):
        """Test that requesters cannot access sensitive operational models."""
        _logger.info("🧪 Testing requester access restrictions...")
        
        # Requesters should not be able to create allocations
        with self.assertRaises(AccessError):
            self.env['hagbes.fleet.allocation'].with_user(self.requester_user).create({
                'name': 'Unauthorized Allocation',
                'company_id': self.env.company.id
            })
        
        # Requesters should not be able to create discrepancies
        with self.assertRaises(AccessError):
            self.env['hagbes.fleet.discrepancy'].with_user(self.requester_user).create({
                'name': 'Unauthorized Discrepancy',
                'company_id': self.env.company.id
            })
        
        _logger.info("✅ Requester access restrictions test passed")
    
    def test_02_menu_visibility_restrictions(self):
        """Test that menu visibility is properly restricted."""
        _logger.info("🧪 Testing menu visibility restrictions...")
        
        # This would require UI testing framework
        # For now, we test the underlying access rights
        
        # Requesters should not have access to allocation model
        allocation_access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'hagbes.fleet.allocation'),
            ('group_id', '=', self.env.ref('hagbes_fleet.group_fleet_requester').id)
        ])
        
        if allocation_access:
            self.assertFalse(allocation_access.perm_write)
            self.assertFalse(allocation_access.perm_create)
            self.assertFalse(allocation_access.perm_unlink)
        
        _logger.info("✅ Menu visibility restrictions test passed")
    
    def test_03_field_level_security(self):
        """Test field-level security restrictions."""
        _logger.info("🧪 Testing field-level security...")
        
        # Create requisition as admin
        requisition = self.env['fleet.requisition'].with_user(self.admin_user).create({
            'purpose': 'Security Field Test',
            'destination': 'Test Destination',
            'date_from': datetime.now() + timedelta(days=1),
            'date_to': datetime.now() + timedelta(days=2),
            'traveller_count': '1',
            'request_by': self.requester_user.id
        })
        
        # Requester should not be able to modify approval fields
        with self.assertRaises((AccessError, ValidationError)):
            requisition.with_user(self.requester_user).write({
                'dept_approved_by': self.requester_user.id
            })
        
        _logger.info("✅ Field-level security test passed")


def run_regression_suite():
    """Run the complete regression test suite."""
    _logger.info("🚀 Starting HAGBES Fleet Regression Test Suite...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTest(unittest.makeSuite(TestFleetRequisitionRegressionSuite))
    suite.addTest(unittest.makeSuite(TestFleetSecurityRegressionSuite))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Report results
    if result.wasSuccessful():
        _logger.info("🎉 All regression tests passed!")
        return True
    else:
        _logger.error(f"❌ Regression tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
        return False


if __name__ == '__main__':
    run_regression_suite()
