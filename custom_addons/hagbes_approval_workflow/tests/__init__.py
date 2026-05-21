# -*- coding: utf-8 -*-

from odoo.tests import common


class TestApprovalWorkflow(common.TransactionCase):
    """Tests for the Approval Workflow module."""

    def setUp(self):
        super().setUp()
        self.ApprovalFlow = self.env['approval.flow']
        self.ApprovalStep = self.env['approval.step']
        self.ApprovalRequest = self.env['approval.request']

    def test_create_approval_flow(self):
        """Test creating an approval flow with steps."""
        flow = self.ApprovalFlow.create({
            'name': 'Test Approval Flow',
            'model_id': self.env.ref('base.model_res_partner').id,
            'active': True,
        })
        self.assertTrue(flow.exists())
        self.assertEqual(flow.name, 'Test Approval Flow')

    def test_create_approval_flow_with_steps(self):
        """Test creating an approval flow with multiple steps."""
        flow = self.ApprovalFlow.create({
            'name': 'Multi-Step Approval Flow',
            'model_id': self.env.ref('base.model_res_partner').id,
            'active': True,
        })

        step1 = self.ApprovalStep.create({
            'name': 'Manager Approval',
            'sequence': 1,
            'flow_id': flow.id,
            'approval_type': 'user',
            'user_ids': [(6, 0, [self.env.ref('base.user_admin').id])],
        })

        step2 = self.ApprovalStep.create({
            'name': 'Director Approval',
            'sequence': 2,
            'flow_id': flow.id,
            'approval_type': 'user',
            'user_ids': [(6, 0, [self.env.ref('base.user_root').id])],
        })

        self.assertEqual(len(flow.step_ids), 2)
        self.assertEqual(step1.sequence, 1)
        self.assertEqual(step2.sequence, 2)

    def test_approval_flow_archive(self):
        """Test archiving an approval flow."""
        flow = self.ApprovalFlow.create({
            'name': 'Archive Test Flow',
            'model_id': self.env.ref('base.model_res_partner').id,
            'active': True,
        })
        flow.write({'active': False})
        self.assertFalse(flow.active)

    def test_approval_flow_steps_order(self):
        """Test that approval steps are ordered by sequence."""
        flow = self.ApprovalFlow.create({
            'name': 'Sequence Test Flow',
            'model_id': self.env.ref('base.model_res_partner').id,
            'active': True,
        })

        self.ApprovalStep.create({
            'name': 'Step C',
            'sequence': 3,
            'flow_id': flow.id,
        })
        self.ApprovalStep.create({
            'name': 'Step A',
            'sequence': 1,
            'flow_id': flow.id,
        })
        self.ApprovalStep.create({
            'name': 'Step B',
            'sequence': 2,
            'flow_id': flow.id,
        })

        steps = flow.step_ids.sorted('sequence')
        self.assertEqual(steps[0].name, 'Step A')
        self.assertEqual(steps[1].name, 'Step B')
        self.assertEqual(steps[2].name, 'Step C')
