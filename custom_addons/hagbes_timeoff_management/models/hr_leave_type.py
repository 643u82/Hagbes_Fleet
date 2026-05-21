def get_allocation_data_request(self, date, some_flag=False):
    holidays = super().get_allocation_data_request(date, some_flag)
    result = []
    employee_id = self.env.context.get('employee_id')
    for h in holidays:
        leave_type_id = h[3]
        allocation = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', employee_id),
            ('holiday_status_id', '=', leave_type_id),
            ('state', '=', 'validate')
        ], limit=1)

        result.append({
            'name': h[0],
            'requires_allocation': h[2] == 'yes',
            'holidayStatusId': leave_type_id,
            'year2_balance': allocation.year_2_balance if allocation else 0,
            'year1_balance': allocation.year_1_balance if allocation else 0,
            'current_balance': allocation.current_year_balance if allocation else 0,
            'number_of_days': (allocation.year_2_balance + allocation.year_1_balance + allocation.current_year_balance) if allocation else 0,
        })
    return result
