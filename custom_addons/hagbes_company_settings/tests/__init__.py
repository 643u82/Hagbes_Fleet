# -*- coding: utf-8 -*-

from odoo.tests import common


class TestCompanySettings(common.TransactionCase):
    """Tests for the Company Settings module."""

    def setUp(self):
        super().setUp()
        self.Company = self.env['res.company']
        self.Partner = self.env['res.partner']

    def test_company_has_tin_field(self):
        """Test that company has TIN field."""
        company = self.Company.create({
            'name': 'Test Company TIN',
        })
        self.assertTrue(hasattr(company, 'tin'))

    def test_company_has_vat_field(self):
        """Test that company has VAT field."""
        company = self.Company.create({
            'name': 'Test Company VAT',
        })
        self.assertTrue(hasattr(company, 'vat'))

    def test_company_has_prefix_field(self):
        """Test that company has document prefix field."""
        company = self.Company.create({
            'name': 'Test Company Prefix',
        })
        self.assertTrue(hasattr(company, 'document_prefix'))

    def test_company_settings_defaults(self):
        """Test company settings have correct defaults."""
        company = self.Company.create({
            'name': 'Defaults Test Company',
        })
        self.assertFalse(company.tin)
        self.assertFalse(company.vat)
        self.assertFalse(company.document_prefix)

    def test_company_settings_write(self):
        """Test writing company settings."""
        company = self.Company.create({
            'name': 'Write Test Company',
        })

        company.write({
            'tin': '1234567890',
            'vat': 'ET-VAT-001',
            'document_prefix': 'HAG',
        })

        self.assertEqual(company.tin, '1234567890')
        self.assertEqual(company.vat, 'ET-VAT-001')
        self.assertEqual(company.document_prefix, 'HAG')

    def test_partner_inherits_company_fields(self):
        """Test that partner inherits company fields if applicable."""
        company = self.Company.create({
            'name': 'Partner Test Company',
            'tin': '9876543210',
        })

        partner = self.Partner.create({
            'name': 'Partner Test',
            'company_id': company.id,
        })

        self.assertEqual(partner.company_id.tin, '9876543210')
