# -*- coding: utf-8 -*-

from odoo.tests import common


class TestCRUDLogger(common.TransactionCase):
    """Tests for the CRUD Logger module."""

    def setUp(self):
        super().setUp()
        self.CRUDLog = self.env['crud.log']
        self.Partner = self.env['res.partner']

    def test_create_partner_creates_log(self):
        """Test that creating a partner creates a log entry."""
        initial_count = self.CRUDLog.search_count([])

        self.Partner.create({
            'name': 'Test CRUD Partner',
            'email': 'test@example.com',
        })

        final_count = self.CRUDLog.search_count([])
        self.assertEqual(final_count, initial_count + 1)

    def test_update_partner_creates_log(self):
        """Test that updating a partner creates a log entry."""
        partner = self.Partner.create({
            'name': 'Update Test Partner',
        })

        initial_count = self.CRUDLog.search_count([])

        partner.write({'name': 'Updated Partner Name'})

        final_count = self.CRUDLog.search_count([])
        self.assertEqual(final_count, initial_count + 1)

    def test_delete_partner_creates_log(self):
        """Test that deleting a partner creates a log entry."""
        partner = self.Partner.create({
            'name': 'Delete Test Partner',
        })
        partner_id = partner.id

        initial_count = self.CRUDLog.search_count([])

        partner.unlink()

        final_count = self.CRUDLog.search_count([])
        self.assertEqual(final_count, initial_count + 1)

    def test_crud_log_fields(self):
        """Test that CRUD log contains required fields."""
        partner = self.Partner.create({
            'name': 'Fields Test Partner',
        })

        log = self.CRUDLog.search([
            ('model', '=', 'res.partner'),
            ('record_id', '=', partner.id),
            ('operation', '=', 'create'),
        ], limit=1)

        self.assertTrue(log.exists())
        self.assertEqual(log.model, 'res.partner')
        self.assertEqual(log.record_id, partner.id)
        self.assertEqual(log.operation, 'create')
        self.assertTrue(log.user_id)
        self.assertTrue(log.create_date)
