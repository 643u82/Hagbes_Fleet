from odoo import models, api

class HREmployee(models.Model):
    _inherit = 'hr.employee'
    

   

    # def _assign_parent_from_job(self):
    #     for emp in self:
    #         manager = False
    #         if emp.job_id and emp.job_id.parent_id:
    #             parent_job = emp.job_id.parent_id
    #             print("jobid parent",emp.job_id.parent_id)
    #             domain = [('job_id', '=', parent_job.id), ('active', '=', True)]
    #             if emp.company_id:
    #                 domain.append(('company_id', '=', emp.company_id.id))
    #             manager = self.env['hr.employee'].search(domain, limit=1)
    #         emp.parent_id = manager.id if manager else False
    #         print ("epmployee:",emp.parent_id)


    # @api.model_create_multi
    # def create(self, vals_list):
    #     employees = super().create(vals_list)
    #     employees._assign_parent_from_job()
    #     return employees

    # def write(self, vals):
    #     res = super().write(vals)
    #     if 'job_id' in vals or 'company_id' in vals:
    #         self._assign_parent_from_job()
    #     return res

    # @api.model
    # def recompute_all_parent_ids(self):
    #     employees = self.search([])
    #     employees._assign_parent_from_job()
    #     return True

    

    def _assign_parent_from_job(self):
        print("\n=== START _assign_parent_from_job ===")

        Employee = self.env['hr.employee'] \
            .sudo() \
            .with_context(active_test=False)

        for emp in self:
            print(f"\n-- Employee ID: {emp.id}")
            print(f"   Name       : {emp.name}")
            print(f"   Job        : {emp.job_id and emp.job_id.name}")
            print(f"   Company    : {emp.company_id and emp.company_id.name}")

            manager = False

            if not emp.job_id:
                print("   ❌ No job_id set")
                continue

            if not emp.job_id.parent_id:
                print("   ❌ Job has no parent job")
                continue

            parent_job = emp.job_id.parent_id
            print(f"   ✔ Parent Job: {parent_job.name} (ID {parent_job.id})")

            company = emp.company_id or self.env.company
            print(f"   ✔ Using Company: {company.name} (ID {company.id})")

            domain = [
                ('job_id', '=', parent_job.id),
                ('active', '=', True),
            ]

            print(f"   🔍 Search domain: {domain}")

            manager = Employee.with_company(company).search(
                domain,
                order='id asc',
                limit=1
            )

            if manager:
                print(f"   ✔ Manager FOUND: {manager.name} (ID {manager.id})")
            else:
                print("   ❌ Manager NOT FOUND")

            print(
                f"   ✍ Writing parent_id = "
                f"{manager.id if manager else False}"
            )

            emp.sudo().write({
                'parent_id': manager.id if manager else False
            })

        print("=== END _assign_parent_from_job ===\n")

    # ----------------------------------------------------
    # CREATE
    # ----------------------------------------------------
    # @api.model_create_multi
    # def create(self, vals_list):
    #     print("\n=== CREATE hr.employee ===")
    #     print(f"Incoming vals_list: {vals_list}")

    #     employees = super().create(vals_list)

    #     print(f"Created employee IDs: {employees.ids}")

    #     # Post-commit execution
    #     self.env.cr.postcommit.add(
    #         lambda: employees._assign_parent_from_job()
    #     )

    #     return employees


    @api.model_create_multi
    def create(self, vals_list):
        print("\n=== CREATE hr.employee ===")
        print(f"Incoming vals_list: {vals_list}")

        employees = super().create(vals_list)

        print(f"Created employee IDs: {employees.ids}")

        # Directly call the assignment (same as write) - this makes the manager visible immediately
        if employees:
            print("✔ Directly calling _assign_parent_from_job after create")
            employees._assign_parent_from_job()

        return employees

    # ----------------------------------------------------
    # WRITE
    # ----------------------------------------------------

    def write(self, vals):
        print("\n=== WRITE hr.employee ===")
        print(f"Employee IDs: {self.ids}")
        print(f"Incoming vals: {vals}")

        res = super().write(vals)

        if {'job_id', 'department_id', 'company_id', 'branch_id'} & set(vals):  # added department_id since you change it too
            print("✔ Directly calling _assign_parent_from_job")
            self._assign_parent_from_job()  # ← runs in same transaction, UI sees the change
        else:
            print("ℹ No relevant change, skipping")

        return res