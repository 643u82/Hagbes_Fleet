try:
    import pyodbc
except ImportError:
    pyodbc = None
import logging
from psycopg2.errors import UniqueViolation
from odoo.tools import mute_logger
from odoo import models, api, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SyncSqlServerLedger(models.Model):
    _name = "sync.sqlserver.ledger"
    _description = "Sync SQL Server AGL Transact"

    @api.model
    def sync_ledger_from_sqlserver(self):
        if not pyodbc:
            raise UserError("The 'pyodbc' library or its system dependencies (like unixODBC) are missing on this server. Please install them to enable SQL Server synchronization.")
        Param = self.env['ir.config_parameter'].sudo()
        server = Param.get_param('sqlserver.server', default='10.10.1.9')
        database = Param.get_param('sqlserver.database', default='Hagbes')
        username = Param.get_param('sqlserver.username', default='zbx_monitor')
        password = Param.get_param('sqlserver.password', default='Hagbes1234')
        driver = Param.get_param('sqlserver.driver', default='ODBC Driver 17 for SQL Server')

        conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={username};PWD={password};"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT account, amount, dim_2, dim_7, voucher_date, voucher_no, 
                   voucher_type, period, client, agrtid 
            FROM agltransact 
            WHERE voucher_date > '2024-12-31 00:00:00.000'
              AND account LIKE '11%'
              AND client = 'HG'
              AND period != 202400
        """)

        Ledger = self.env["bank_reco.ledger"]
        rows = cursor.fetchall()

        # Normalize AGRTID
        agrtids = [str(row.agrtid) for row in rows]
        existing_records = Ledger.search([("agrtid", "in", agrtids)])
        existing_dict = {str(r.agrtid): r for r in existing_records}

        to_create = []
        updated_agrtids = set()
        affected_accounts_periods = set()

        for row in rows:
            row_agrtid = str(row.agrtid)
            values = {
                "agrtid": row_agrtid,
                "account_id": row.account,
                "voucher_no": row.voucher_no,
                "voucher_date": row.voucher_date,
                "voucher_type": row.voucher_type,
                "period": row.period,
                "amount": row.amount,
                "company_id": self.env.company.id,
                "reference": row.dim_7,
            }

            affected_accounts_periods.add((row.account, str(row.period)))

            if row_agrtid in existing_dict:
                existing_record = existing_dict[row_agrtid]
                has_changed = any(
                    existing_record[field] != value
                    for field, value in values.items()
                    if field != 'agrtid'
                )
                if has_changed:
                    existing_record.write(values)
                    updated_agrtids.add(row_agrtid)
            else:
                to_create.append(values)

        # Create new records safely
        if to_create:
            try:
                with mute_logger('odoo.sql_db'):
                    Ledger.create(to_create)
                updated_agrtids.update([v['agrtid'] for v in to_create])
            except Exception as e:
                if isinstance(e.__cause__, UniqueViolation):
                    _logger.warning("Duplicate agrtid found during create: %s", e)
                else:
                    raise

        cursor.close()
        conn.close()

        # Update affected headers and details
        BankHeader = self.env['bank_reco.header']
        for account, period in affected_accounts_periods:
            headers = BankHeader.search([
                ('account_id', '=', account),
                ('period', '=', period)
            ])

            for header in headers:
                if header.state == 'done':
                    _logger.info(
                        "Skipping header %s (account=%s, period=%s) because reconciliation is already done.",
                        header.name, account, period
                    )
                    # Optional: Log a warning to notify accounting team
                    _logger.warning(
                        "New transactions found for reconciled header %s. Manual review may be required.",
                        header.name
                    )
                    continue

                # Only fetch transactions for non-reconciled headers
                _logger.info(
                    "Refreshing ledger transactions for header %s (account=%s, period=%s).",
                    header.name, account, period
                )
                header.action_fetch_ledger_transactions()

        _logger.info("Ledger synchronization completed successfully.")
