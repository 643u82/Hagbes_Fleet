CREATE OR REPLACE VIEW hr_job_org_chart_view AS (
    SELECT
        job.id AS id,
        job.id AS job_id,
        job.name AS job_name,
        job.parent_id AS parent_job_id,
        job.company_id AS company_id,
        job.department_id AS department_id,
        job.analytic_account_id AS branch_id,
        -- number of expected employees
        job.expected_employees,
        -- count active employees assigned to job
        (SELECT COUNT(*) FROM hr_employee emp WHERE emp.job_id = job.id AND emp.active = TRUE) AS no_of_employee
    FROM
        hr_job job
);
