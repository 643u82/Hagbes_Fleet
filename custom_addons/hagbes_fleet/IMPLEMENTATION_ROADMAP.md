# Hagbes Fleet Management - Prioritized Implementation Roadmap

**Date:** June 5, 2026  
**Version:** 18.0.1.1.0  
**Status:** Pre-Production (Deployment Blocked)

---

## Priority Classification

### 🔴 CRITICAL - Must Fix Before Deployment
Issues that block core functionality or create security vulnerabilities. Deployment is impossible until these are resolved.

### 🟠 HIGH PRIORITY - Required for Production
Issues that significantly impact user experience or system integrity. Should be fixed before production deployment.

### 🟡 MEDIUM PRIORITY - Important Improvements
Issues that improve functionality but don't block deployment. Can be addressed post-launch in early sprints.

### 🟢 LOW PRIORITY - Future Enhancements
Nice-to-have features and optimizations. Can be planned for future releases.

---

## 🔴 CRITICAL ISSUES (8 Total)

### CRIT-001: Requester Cannot Submit Own Requisitions
**Why It Matters:** Core workflow is broken. Users cannot submit their own vehicle requests, making the system unusable for its primary purpose.

**Impact:** Complete workflow failure for 90% of users

**Effort:** 5 minutes

**Affected Files:**
- `security/ir.model.access.csv` (line 23-24)

**Fix:**
```csv
# BEFORE:
access_fleet_requisition_user,access_fleet_requisition_user,model_fleet_requisition,base.group_user,1,1,0,0

# AFTER:
access_fleet_requisition_user,access_fleet_requisition_user,model_fleet_requisition,base.group_user,1,1,1,0
```

**Change:** Add write permission (third column: 0 → 1)

**Testing:**
1. Login as regular user (no fleet groups)
2. Create requisition
3. Click "Submit" button
4. Verify state changes to "submitted"

---

### CRIT-002: Requisition Completion Uses Non-Existent States
**Why It Matters:** The `action_complete()` method references states that don't exist in the state selection, causing Odoo validation to fail. Requisitions cannot be marked as complete.

**Impact:** Workflow dead-end after approval; business process cannot close

**Effort:** 30 minutes

**Affected Files:**
- `models/fleet_requisition.py` (lines 168-183 state selection, lines 400-407 action method)

**Fix:**
```python
# Add missing states to selection (line 168-183):
state = fields.Selection([
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('dept_review', 'Department Review'),
    ('fmo_review', 'FMO Review'),
    ('approved', 'Approved'),
    ('allocated', 'Allocated'),        # ADD THIS
    ('completed', 'Completed'),        # ADD THIS
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
], string='State', default='draft', required=True, tracking=True, index=True)

# Update action_complete to check correct state:
def action_complete(self):
    for rec in self:
        if rec.state != 'allocated':
            raise UserError(_('Only allocated requisitions can be completed.'))
        rec.state = 'completed'
        rec.message_post(body=_("Requisition marked as completed."))
```

**Testing:**
1. Create and approve requisition
2. Create allocation
3. Set requisition state to 'allocated' (manually for now)
4. Click "Complete" button
5. Verify state changes to 'completed'

---

### CRIT-003: Duplicate action_cancel() Method
**Why It Matters:** Two definitions of the same method means the second one silently replaces the first, creating dead code and unpredictable behavior.

**Impact:** First implementation unreachable; maintenance confusion; potential logic errors

**Effort:** 10 minutes

**Affected Files:**
- `models/fleet_requisition.py` (lines 394-398 and 409-413)

**Fix:**
```python
# Remove the duplicate at lines 409-413 or merge logic if different
# Keep only ONE action_cancel method

def action_cancel(self):
    """Cancel requisition - can be called by requester or manager"""
    for rec in self:
        if rec.state in ('completed', 'rejected'):
            raise UserError(_('Cannot cancel completed or rejected requisitions.'))
        
        # Cancel any pending approval requests
        if rec._is_approval_enabled():
            pending_approvals = self.env['approval.request'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', rec.id),
                ('status', '=', 'pending')
            ])
            pending_approvals.write({'status': 'cancelled'})
        
        rec.state = 'cancelled'
        rec.message_post(body=_("Requisition cancelled by %s.") % self.env.user.name)
```

**Testing:**
1. Create requisition in draft
2. Cancel and verify
3. Submit requisition
4. Cancel and verify approval request is cancelled

---

### CRIT-004: Vehicle Status Written Instead of Computed
**Why It Matters:** Code directly writes to a stored computed field, breaking the automatic status derivation logic. Status should be computed from related records.

**Impact:** Status becomes inconsistent with actual vehicle state

**Effort:** 20 minutes

**Affected Files:**
- `models/fleet_trip.py` (line 307-310)
- `wizard/fleet_trip_actual_wizard.py` (line 47-49)
- `models/fleet_vehicle.py` (line 72-86 - compute method)

**Fix:**
```python
# In fleet_trip.py (line ~307-310), REMOVE this:
# self.vehicle_id.status = 'assigned'  # DELETE THIS LINE

# In fleet_trip_actual_wizard.py (line ~47-49), REMOVE this:
# self.trip_id.vehicle_id.status = 'available'  # DELETE THIS LINE

# Status will automatically recompute based on:
# - allocation.state
# - maintenance.state  
# - disposal_state
# No manual writes needed!
```

**Testing:**
1. Create allocation → verify vehicle status = 'assigned'
2. Start trip → verify status still 'assigned' (via allocation)
3. Complete trip → verify status = 'available' (no active allocations)
4. Create maintenance → verify status = 'maintenance'

---

### CRIT-005: Property Manager Approval Not Restricted
**Why It Matters:** Security validation detected that Property Manager approval step doesn't verify the approver has the correct role.

**Impact:** Any user could potentially approve as Property Manager

**Effort:** 45 minutes

**Affected Files:**
- `data/fleet_approval_flows.xml` (Fleet Assignment, Maintenance, Disposal flows)
- May need to verify `approval.step` has proper `role_id` validation

**Fix:**
```xml
<!-- In fleet_approval_flows.xml, verify each Property Manager step has role_id -->
<record id="step_assignment_property_review" model="approval.step">
    <field name="name">Property Manager Review</field>
    <field name="sequence">20</field>
    <field name="flow_id" ref="flow_fleet_assignment"/>
    <!-- VERIFY THIS IS SET: -->
    <field name="role_id" ref="group_property_manager"/>
    <field name="action_type">approval</field>
</record>

<!-- Repeat for all Property Manager steps in:
     - flow_fleet_maintenance
     - flow_fleet_disposal
-->
```

**Testing:**
1. Submit vehicle assignment as requester
2. Try to approve as Property Manager step with non-Property Manager user
3. Verify rejection
4. Login as Property Manager and approve successfully

---

### CRIT-006: FMO Approval Not Restricted
**Why It Matters:** Same as CRIT-005 but for FMO Officer role.

**Impact:** Unauthorized users could approve FMO-level requests

**Effort:** 45 minutes

**Affected Files:**
- `data/fleet_approval_flows.xml` (Requisition FMO Officer step)

**Fix:**
```xml
<!-- In fleet_approval_flows.xml -->
<record id="step_requisition_fmo_review" model="approval.step">
    <field name="name">FMO Officer Review</field>
    <field name="sequence">30</field>
    <field name="flow_id" ref="flow_fleet_requisition"/>
    <!-- VERIFY THIS IS SET: -->
    <field name="role_id" ref="group_fmo"/>
    <field name="action_type">approval</field>
</record>
```

**Testing:**
1. Submit requisition
2. Approve as Department Manager
3. Try to approve FMO step as non-FMO user → should fail
4. Login as FMO and approve successfully

---

### CRIT-007: Allocation-Trip-Requisition Flow Disconnected
**Why It Matters:** The three core operational models don't auto-link, requiring manual data entry and creating potential for orphaned records.

**Impact:** 
- Requisitions don't auto-create allocations
- Allocations don't auto-create trips
- Trip completion doesn't update requisition
- Manual overhead, data inconsistency

**Effort:** 4 hours

**Affected Files:**
- `models/fleet_requisition.py` (add auto-allocation creation)
- `models/fleet_allocation.py` (add auto-trip creation)
- `models/fleet_trip.py` (add completion sync)

**Fix (Part 1 - Requisition → Allocation):**
```python
# In fleet_requisition.py, update _on_approval_approved:

def _on_approval_approved(self):
    """Called when requisition is fully approved"""
    self.ensure_one()
    self.state = 'approved'
    self.message_post(body=_("Requisition has been approved."))
    
    # AUTO-CREATE ALLOCATION (NEW CODE)
    if self._get_config_flag('fleet.auto_create_allocation', default=True):
        allocation_vals = {
            'request_id': self.id,
            'company_id': self.company_id.id,
            'expected_distance': 0,  # To be filled by FMO
            'allocation_date': self.date_from,
            'expected_return_date': self.date_to,
            # vehicle_id and driver_id to be assigned by FMO
        }
        allocation = self.env['hagbes.fleet.allocation'].create(allocation_vals)
        self.state = 'allocated'  # NEW STATE from CRIT-002
        self.message_post(
            body=_("Allocation %s created automatically.") % allocation.name
        )
```

**Fix (Part 2 - Allocation → Trip):**
```python
# In fleet_allocation.py, add method:

def action_create_trip(self):
    """Create trip from allocation"""
    self.ensure_one()
    if not self.vehicle_id or not self.driver_id:
        raise UserError(_('Vehicle and driver must be assigned before creating trip.'))
    
    trip_vals = {
        'allocation_id': self.id,
        'vehicle_id': self.vehicle_id.id,
        'driver_id': self.driver_id.id,
        'expected_start_date': self.allocation_date,
        'expected_end_date': self.expected_return_date,
        'expected_distance': self.expected_distance,
        'state': 'planning',
    }
    trip = self.env['fleet.trip'].create(trip_vals)
    self.message_post(body=_("Trip %s created.") % trip.name)
    return trip
```

**Fix (Part 3 - Trip Completion → Sync):**
```python
# In fleet_trip.py, update action_complete_trip:

def action_complete_trip(self):
    self.ensure_one()
    self.state = 'completed'
    
    # Update allocation
    if self.allocation_id:
        self.allocation_id.action_return_vehicle()
    
    # Update linked requisitions
    for req in self.requisition_ids:
        if req.state == 'allocated' and not req.has_active_allocations():
            req.state = 'completed'
            req.message_post(body=_("Auto-completed after trip %s.") % self.name)
```

**Testing:**
1. Approve requisition → verify allocation auto-created, state = 'allocated'
2. Assign vehicle/driver to allocation
3. Create trip → verify links correctly
4. Complete trip → verify allocation returned, requisition completed

---

### CRIT-008: Post Init Hook Not Registered
**Why It Matters:** The hook that initializes vehicle status is defined but never called because it's not registered in the manifest.

**Impact:** New installations won't have vehicles initialized properly

**Effort:** 2 minutes

**Affected Files:**
- `__manifest__.py` (line 44)
- `hooks.py`

**Fix:**
```python
# In __manifest__.py, verify this line exists (currently commented):
'post_init_hook': 'post_init_hook',

# Should be at line 44, after 'application': True
```

**Testing:**
1. Install module in test database
2. Check logs for "Starting hagbes_fleet post_init_hook"
3. Verify vehicles get initialized

---

## 🟠 HIGH PRIORITY ISSUES (12 Total)

### HIGH-001: Unrestricted Vehicle Creation by Base Users
**Why It Matters:** Any internal user can create vehicle master data, allowing unauthorized modifications to fleet assets.

**Impact:** Data integrity risk; unauthorized asset additions

**Effort:** 10 minutes

**Affected Files:**
- `security/ir.model.access.csv` (line 2)

**Fix:**
```csv
# BEFORE:
access_hagbes_fleet_vehicle_user,access_hagbes_fleet_vehicle_user,model_hagbes_fleet_vehicle,base.group_user,1,1,1,0

# AFTER:
access_hagbes_fleet_vehicle_user,access_hagbes_fleet_vehicle_user,model_hagbes_fleet_vehicle,base.group_user,1,0,0,0

# Add separate line for FMO with create permission:
access_hagbes_fleet_vehicle_fmo,access_hagbes_fleet_vehicle_fmo,model_hagbes_fleet_vehicle,group_fmo,1,1,1,0
```

---

### HIGH-002: Missing Multi-Company Record Rules
**Why It Matters:** 6 operational models lack multi-company isolation, allowing users to see/modify records from other companies.

**Impact:** Data leakage in multi-company environments

**Effort:** 1 hour

**Affected Files:**
- `security/security_rules.xml` (new rules needed)

**Fix:**
```xml
<!-- Add to security_rules.xml -->

<!-- Fleet Allocation Multi-Company Rule -->
<record id="fleet_allocation_company_rule" model="ir.rule">
    <field name="name">Fleet Allocation: Multi-Company</field>
    <field name="model_id" ref="model_hagbes_fleet_allocation"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>

<!-- Fleet Discrepancy Multi-Company Rule -->
<record id="fleet_discrepancy_company_rule" model="ir.rule">
    <field name="name">Fleet Discrepancy: Multi-Company</field>
    <field name="model_id" ref="model_hagbes_fleet_discrepancy"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>

<!-- Fleet Vehicle Status Log Multi-Company Rule -->
<record id="fleet_vehicle_status_log_company_rule" model="ir.rule">
    <field name="name">Fleet Vehicle Status Log: Multi-Company</field>
    <field name="model_id" ref="model_hagbes_fleet_vehicle_status_log"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>

<!-- Fleet Trip Log Multi-Company Rule (via allocation) -->
<record id="fleet_trip_log_company_rule" model="ir.rule">
    <field name="name">Fleet Trip Log: Multi-Company</field>
    <field name="model_id" ref="model_hagbes_fleet_trip_log"/>
    <field name="domain_force">[('allocation_id.company_id', 'in', company_ids)]</field>
</record>

<!-- Fleet Trip GPS Multi-Company Rule (via trip) -->
<record id="fleet_trip_gps_company_rule" model="ir.rule">
    <field name="name">Fleet Trip GPS: Multi-Company</field>
    <field name="model_id" ref="model_hagbes_fleet_trip_gps"/>
    <field name="domain_force">[('trip_id.company_id', 'in', company_ids)]</field>
</record>

<!-- Fleet Allocation Append Multi-Company Rule -->
<record id="fleet_allocation_append_company_rule" model="ir.rule">
    <field name="name">Fleet Allocation Append: Multi-Company</field>
    <field name="model_id" ref="model_hagbes_fleet_allocation_append"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>
```

**Note:** Some models need `company_id` field added first if missing.

---

### HIGH-003: CSS Assets Not Loaded
**Why It Matters:** Layout fix CSS exists but isn't loaded, causing potential UI issues in list views.

**Impact:** Poor user experience with misaligned tables

**Effort:** 2 minutes

**Affected Files:**
- `__manifest__.py` (line 44-47)

**Fix:**
```python
# In __manifest__.py, uncomment or add:
'assets': {
    'web.assets_backend': [
        'hagbes_fleet/static/src/css/fleet_layout_fix.css',
    ],
}
```

---

### HIGH-004: Settings Menu Not Exposed
**Why It Matters:** Configuration view exists but users cannot access it through the UI.

**Impact:** Admins cannot change settings without developer mode

**Effort:** 15 minutes

**Affected Files:**
- `views/fleet_menu.xml` (add menu item)
- `views/fleet_config_settings_views.xml` (verify action exists)

**Fix:**
```xml
<!-- In fleet_menu.xml, add under Configuration submenu: -->
<menuitem 
    id="menu_fleet_config_settings"
    name="Settings"
    parent="menu_fleet_config"
    action="base.action_general_configuration"
    sequence="10"
    groups="group_fleet_admin"/>
```

---

### HIGH-005: Driver License Validation Missing
**Why It Matters:** Allocations can be created with drivers who don't have valid licenses or aren't marked as drivers.

**Impact:** Compliance risk; unauthorized drivers operating vehicles

**Effort:** 1 hour

**Affected Files:**
- `models/fleet_allocation.py` (add constraints)
- `models/fleet_vehicle_assign.py` (add constraints)

**Fix:**
```python
# In fleet_allocation.py, add:

@api.constrains('driver_id')
def _check_driver_validity(self):
    for rec in self:
        if rec.driver_id:
            if not rec.driver_id.is_driver:
                raise ValidationError(
                    _('Employee %s is not marked as a driver.') % rec.driver_id.name
                )
            
            if rec.driver_id.license_expiry:
                if rec.driver_id.license_expiry < fields.Date.today():
                    raise ValidationError(
                        _("Driver %s license expired on %s.") % (
                            rec.driver_id.name,
                            rec.driver_id.license_expiry
                        )
                    )
                
                # Warn if expiring soon (within 30 days)
                days_until_expiry = (rec.driver_id.license_expiry - fields.Date.today()).days
                if days_until_expiry <= 30:
                    rec.message_post(
                        body=_("Warning: Driver license expires in %d days.") % days_until_expiry,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note'
                    )
```

---

### HIGH-006: Maintenance Cost Validation Missing
**Why It Matters:** Maintenance records can have negative or zero costs, creating data quality issues.

**Impact:** Inaccurate cost tracking and reporting

**Effort:** 10 minutes

**Affected Files:**
- `models/fleet_maintenance.py`

**Fix:**
```python
# Add constraint:
@api.constrains('cost')
def _check_cost_positive(self):
    for rec in self:
        if rec.cost <= 0:
            raise ValidationError(_('Maintenance cost must be greater than zero.'))
```

---

### HIGH-007: Cron Jobs Inactive
**Why It Matters:** Code references cron jobs for overdue returns and approval reminders, but cron definitions may be missing/inactive.

**Impact:** No automated notifications; manual monitoring required

**Effort:** 2 hours

**Affected Files:**
- `data/ir_cron.xml` (needs implementation)
- `models/fleet_allocation.py:418` (cron method exists)
- `models/fleet_requisition.py:940` (cron method exists)

**Fix:**
```xml
<!-- In data/ir_cron.xml -->
<odoo>
    <data noupdate="1">
        
        <!-- Check Overdue Allocation Returns -->
        <record id="ir_cron_check_overdue_returns" model="ir.cron">
            <field name="name">Fleet: Check Overdue Returns</field>
            <field name="model_id" ref="model_hagbes_fleet_allocation"/>
            <field name="state">code</field>
            <field name="code">model._cron_check_overdue_returns()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">days</field>
            <field name="numbercall">-1</field>
            <field name="active">True</field>
        </record>

        <!-- Approval Reminder -->
        <record id="ir_cron_approval_reminder" model="ir.cron">
            <field name="name">Fleet: Approval Reminder</field>
            <field name="model_id" ref="model_fleet_requisition"/>
            <field name="state">code</field>
            <field name="code">model._cron_approval_reminder()</field>
            <field name="interval_number">1</field>
            <field name="interval_type">days</field>
            <field name="numbercall">-1</field>
            <field name="active">True</field>
        </record>

        <!-- Driver License Expiry Check -->
        <record id="ir_cron_license_expiry_check" model="ir.cron">
            <field name="name">Fleet: Driver License Expiry Check</field>
            <field name="model_id" ref="hr.model_hr_employee"/>
            <field name="state">code</field>
            <field name="code">
# Check licenses expiring in next 30 days
expiry_date = (fields.Date.today() + timedelta(days=30))
drivers = model.search([
    ('is_driver', '=', True),
    ('license_expiry', '<=', expiry_date),
    ('license_expiry', '>=', fields.Date.today())
])
for driver in drivers:
    driver._schedule_license_expiry_activity()
            </field>
            <field name="interval_number">7</field>
            <field name="interval_type">days</field>
            <field name="numbercall">-1</field>
            <field name="active">True</field>
        </record>

    </data>
</odoo>
```

---

### HIGH-008: Remove 13 Unused Files
**Why It Matters:** Dead code increases maintenance burden and confusion.

**Impact:** Code bloat; potential confusion

**Effort:** 30 minutes (careful verification needed)

**Files to Remove:**
1. `models/fleet_requisition.py.backup`
2. `models/fleet_requisition_consolidated.py`
3. `models/fleet_requisition_fixed.py`
4. `models/fleet_trip_consolidated.py`
5. `models/fleet_trip_fixed.py`
6. `models/fleet_vehicle_consolidated.py`
7. `models/__init___consolidated.py`
8. `__manifest___consolidated.py`
9. `security/ir_model_access_consolidated.csv`
10. `security/ir_model_access_fixed.csv`
11. `security/record_rules_consolidated.xml`
12. `security/record_rules_fixed.xml`
13. `scripts/` directory (empty)

**Fix:**
```bash
# Run from module root:
cd models && rm -f *.backup *_consolidated.py *_fixed.py __init___consolidated.py
cd ../security && rm -f *_consolidated.* *_fixed.*
cd .. && rm -f __manifest___consolidated.py
rmdir scripts
```

**Verification:** Ensure no imports reference these files

---

### HIGH-009: Test Coverage Insufficient
**Why It Matters:** Only ~40% coverage leaves critical paths untested.

**Impact:** High risk of regression; undetected bugs

**Effort:** 1 week

**Files Needed:**
- `tests/test_fleet_requisition_workflow.py` (new)
- `tests/test_fleet_trip_execution.py` (new)
- `tests/test_fleet_maintenance.py` (new)
- `tests/test_fleet_vehicle_disposal.py` (new)
- `tests/test_security_acl.py` (new)

**Priority Tests:**
```python
# test_fleet_requisition_workflow.py
class TestRequisitionWorkflow(TransactionCase):
    def test_requester_can_submit_own_requisition(self):
        """Verify CRIT-001 fix"""
        
    def test_requisition_completion_with_new_states(self):
        """Verify CRIT-002 fix"""
        
    def test_auto_allocation_creation_on_approval(self):
        """Verify CRIT-007 fix"""

# test_security_acl.py
class TestSecurityACL(TransactionCase):
    def test_base_user_cannot_create_vehicles(self):
        """Verify HIGH-001 fix"""
        
    def test_requester_can_write_own_requisition(self):
        """Verify CRIT-001 fix"""
```

---

### HIGH-010: Vehicle Driver Field Inconsistency
**Why It Matters:** Vehicle has `driver` as Char, allocation has `driver_id` as Many2one. Confusing and prevents relational queries.

**Impact:** Data inconsistency; reporting difficulties

**Effort:** 2 hours (requires data migration)

**Affected Files:**
- `models/fleet_vehicle.py`
- Migration script needed

**Fix:**
```python
# In fleet_vehicle.py, change:
# FROM:
driver = fields.Char(string='Driver Name', index=True)

# TO:
driver_id = fields.Many2one(
    'hr.employee',
    string='Current Driver',
    domain=[('is_driver', '=', True)],
    index=True,
    help='Primary driver assigned to this vehicle'
)
driver_name = fields.Char(
    related='driver_id.name',
    string='Driver Name',
    readonly=True,
    store=True
)
```

**Migration Required:** Script to clear existing `driver` char values

---

### HIGH-011: SMS Module Unused
**Why It Matters:** Module depends on `sms` but has zero SMS implementation.

**Impact:** Unnecessary dependency; confusion

**Effort:** 30 minutes (decision + implementation)

**Options:**

**Option A - Remove Dependency:**
```python
# In __manifest__.py, remove 'sms' from depends list
'depends': [
    'base',
    'fleet',
    'hr',
    'mail',
    # 'sms',  # REMOVE THIS
    'hagbes_approval_workflow',
],
```

**Option B - Implement Basic SMS:**
```python
# In fleet_requisition.py, add SMS notification:
def _send_approval_sms(self, approver):
    if approver.mobile:
        self.env['sms.sms'].create({
            'number': approver.mobile,
            'body': _('Fleet requisition %s needs your approval.') % self.name,
        })
```

**Recommendation:** Remove dependency unless SMS is a business requirement

---

### HIGH-012: Department Manager Rule Uses Job Hierarchy
**Why It Matters:** Record rule uses `child_of` with job hierarchy which is fragile and unpredictable.

**Impact:** Department managers may not see their team's requisitions if job tree is wrong

**Effort:** 30 minutes

**Affected Files:**
- `security/fleet_requisition_rules.xml` (line ~26-31)

**Fix:**
```xml
<!-- BEFORE (fragile): -->
<field name="domain_force">[
    '|',
    ('request_by', '=', user.id),
    ('request_by.employee_id.job_id', 'child_of', user.employee_id.job_id)
]</field>

<!-- AFTER (reliable): -->
<field name="domain_force">[
    '|',
    ('request_by', '=', user.id),
    ('department_id', '=', user.employee_id.department_id.id)
]</field>
```

---

## 🟡 MEDIUM PRIORITY ISSUES (10 Total)

### MED-001: Dashboard with KPIs
**Why It Matters:** No overview of fleet status; users must navigate multiple menus

**Effort:** 1 week

**Components Needed:**
- Dashboard view with metric cards
- Python computed fields for KPIs
- Client action for dashboard

**KPIs to Include:**
- Total vehicles by status
- Active allocations
- Pending requisitions
- High-severity discrepancies
- Maintenance costs (MTD)
- Avg approval time

---

### MED-002: Smart Buttons Missing
**Why It Matters:** Users cannot easily navigate between related records

**Effort:** 4 hours

**Add To:**
- Vehicle → view assignments, maintenance, trips (3 buttons)
- Requisition → view allocation (1 button)
- Allocation → view trips, logs, appends (3 buttons)
- Employee → view assigned vehicles, trips (2 buttons)

---

### MED-003: Vehicle Status Compute Performance
**Why It Matters:** Python loop through all related records is O(n) per vehicle

**Effort:** 3 hours

**Fix:** Use SQL or limit search scope with state filters

---

### MED-004: Calendar View for Trips
**Why It Matters:** No visual trip scheduling/planning interface

**Effort:** 3 hours

**Implementation:**
```xml
<record id="view_fleet_trip_calendar" model="ir.ui.view">
    <field name="name">fleet.trip.calendar</field>
    <field name="model">fleet.trip</field>
    <field name="arch" type="xml">
        <calendar string="Trip Schedule" 
                  date_start="expected_start_date" 
                  date_stop="expected_end_date"
                  color="vehicle_id">
            <field name="name"/>
            <field name="vehicle_id"/>
            <field name="driver_id"/>
        </calendar>
    </field>
</record>
```

---

### MED-005: GPS Map Visualization
**Why It Matters:** GPS data collected but not visualized

**Effort:** 1 week (requires JS widget)

---

### MED-006: Fuel Management Module
**Why It Matters:** Core fleet feature completely missing

**Effort:** 2 weeks

**Models Needed:**
- `fleet.fuel.log` - Refueling transactions
- `fleet.fuel.card` - Fuel card management
- Integration with `fleet.trip` for fuel cost

---

### MED-007: Reporting Suite
**Why It Matters:** Only 2 basic reports; no analytics

**Effort:** 2 weeks

**Reports Needed:**
- Vehicle utilization
- Maintenance cost analysis
- Fuel efficiency trends
- Approval SLA
- Driver performance

---

### MED-008: Email Notifications
**Why It Matters:** No proactive notifications; users must check system

**Effort:** 1 week

**Notifications Needed:**
- Requisition approved/rejected
- Allocation assigned
- Trip started/completed
- Maintenance scheduled/completed
- Approval reminders

---

### MED-009: Vehicle Document Tracking
**Why It Matters:** No insurance/registration expiry tracking

**Effort:** 1 week

**Models Needed:**
- `fleet.vehicle.document`
- Expiry alerts
- Document upload

---

### MED-010: Recurring Maintenance Scheduling
**Why It Matters:** Preventive maintenance must be manually scheduled

**Effort:** 1 week

**Features:**
- Mileage-based intervals
- Time-based intervals
- Auto-schedule maintenance
- Due date reminders

---

## 🟢 LOW PRIORITY ISSUES (8 Total)

### LOW-001: Incident/Accident Management
**Effort:** 2 weeks

### LOW-002: Driver Performance Metrics
**Effort:** 1 week

### LOW-003: Vehicle Telematics Integration
**Effort:** 3 weeks

### LOW-004: Dispatch Board (Drag-Drop)
**Effort:** 2 weeks

### LOW-005: Mobile App Support
**Effort:** 4 weeks

### LOW-006: Vehicle Pool Management
**Effort:** 2 weeks

### LOW-007: Cost Depreciation Calculation
**Effort:** 1 week

### LOW-008: Multi-Stop Trip Support
**Effort:** 1 week

---

## 🎯 TOP 10 TASKS TO COMPLETE NEXT

### Sprint 1: Critical Fixes (Days 1-3)

#### 1️⃣ Fix Requester ACL [CRIT-001]
**Priority:** CRITICAL  
**Effort:** 5 minutes  
**Blocker:** Core workflow broken  
**File:** `security/ir.model.access.csv`  
**Action:** Add write permission for base.group_user on fleet.requisition

---

#### 2️⃣ Fix Requisition Completion States [CRIT-002]
**Priority:** CRITICAL  
**Effort:** 30 minutes  
**Blocker:** Workflow cannot complete  
**File:** `models/fleet_requisition.py`  
**Action:** Add 'allocated' and 'completed' to state selection

---

#### 3️⃣ Remove Duplicate action_cancel() [CRIT-003]
**Priority:** CRITICAL  
**Effort:** 10 minutes  
**Blocker:** Dead code, unpredictable behavior  
**File:** `models/fleet_requisition.py`  
**Action:** Remove duplicate method definition (lines 409-413)

---

#### 4️⃣ Stop Writing Computed Vehicle Status [CRIT-004]
**Priority:** CRITICAL  
**Effort:** 20 minutes  
**Blocker:** Status logic broken  
**Files:** `models/fleet_trip.py`, `wizard/fleet_trip_actual_wizard.py`  
**Action:** Remove direct writes to vehicle.status field

---

#### 5️⃣ Fix Property Manager Approval Restriction [CRIT-005]
**Priority:** CRITICAL  
**Effort:** 45 minutes  
**Blocker:** Security violation  
**File:** `data/fleet_approval_flows.xml`  
**Action:** Verify role_id set on all Property Manager steps

---

### Sprint 2: High Priority Security & Flow (Days 4-7)

#### 6️⃣ Fix FMO Approval Restriction [CRIT-006]
**Priority:** CRITICAL  
**Effort:** 45 minutes  
**Blocker:** Security violation  
**File:** `data/fleet_approval_flows.xml`  
**Action:** Verify role_id set on FMO Officer step

---

#### 7️⃣ Connect Allocation-Trip-Requisition Flow [CRIT-007]
**Priority:** CRITICAL  
**Effort:** 4 hours  
**Blocker:** Manual workflow, disconnected data  
**Files:** `models/fleet_requisition.py`, `models/fleet_allocation.py`, `models/fleet_trip.py`  
**Action:** Auto-create allocation on approval, auto-create trip, sync completion

---

#### 8️⃣ Register Post Init Hook [CRIT-008]
**Priority:** CRITICAL  
**Effort:** 2 minutes  
**Blocker:** New installations broken  
**File:** `__manifest__.py`  
**Action:** Uncomment post_init_hook registration

---

#### 9️⃣ Restrict Vehicle Creation [HIGH-001]
**Priority:** HIGH  
**Effort:** 10 minutes  
**Blocker:** Data integrity risk  
**File:** `security/ir.model.access.csv`  
**Action:** Remove create permission from base.group_user for vehicles

---

#### 🔟 Add Multi-Company Record Rules [HIGH-002]
**Priority:** HIGH  
**Effort:** 1 hour  
**Blocker:** Multi-company data leakage  
**File:** `security/security_rules.xml`  
**Action:** Add 6 missing multi-company rules

---

## Implementation Timeline

### Phase 1: Critical Fixes (Week 1)
**Goal:** Deployment-ready, core workflow functional

- ✅ All 8 CRITICAL issues resolved
- ✅ Basic security validated
- ✅ Workflow tested end-to-end
- ✅ Deployment validation passes

**Deliverable:** Production-ready v18.0.1.2.0

---

### Phase 2: High Priority Security & UX (Weeks 2-3)
**Goal:** Secure multi-company, better UX

- ✅ All 12 HIGH PRIORITY issues resolved
- ✅ Multi-company tested
- ✅ Driver validation working
- ✅ Settings accessible
- ✅ Cron jobs active
- ✅ Dead code removed
- ✅ 60% test coverage

**Deliverable:** Production v18.0.1.3.0

---

### Phase 3: Medium Priority Features (Weeks 4-8)
**Goal:** Feature-complete, analytics ready

- Dashboard with KPIs
- Smart buttons across all models
- Calendar view for trips
- Email notifications
- Reporting suite (5 reports)
- Fuel management basics
- Vehicle documents

**Deliverable:** v18.0.2.0.0

---

### Phase 4: Low Priority Enhancements (Weeks 9-16)
**Goal:** Enterprise-grade features

- Incident management
- Driver performance
- Telematics integration
- Dispatch board
- Mobile support

**Deliverable:** v18.0.3.0.0

---

## Quick Wins (Do These First)

These take <15 minutes each and provide immediate value:

1. ✅ Fix requester ACL (5 min) - **CRIT-001**
2. ✅ Remove duplicate method (10 min) - **CRIT-003**
3. ✅ Register post init hook (2 min) - **CRIT-008**
4. ✅ Remove vehicle create for base users (10 min) - **HIGH-001**
5. ✅ Load CSS assets (2 min) - **HIGH-003**
6. ✅ Add settings menu (15 min) - **HIGH-004**

**Total:** ~45 minutes for 6 fixes

---

## Risk Mitigation

### High-Risk Changes

**CRIT-007: Allocation-Trip-Requisition Flow**
- **Risk:** Could break existing workflows
- **Mitigation:** 
  - Add feature flag: `fleet.auto_create_allocation` (default True)
  - Comprehensive testing
  - Database backup before deployment
  - Rollback plan ready

**HIGH-010: Vehicle Driver Field Change**
- **Risk:** Data migration required
- **Mitigation:**
  - Test migration in staging
  - Keep old field as backup during transition
  - Gradual rollout

---

## Testing Strategy

### Critical Path Testing (Must Pass)

1. **Requisition Submission by Requester**
   - Create requisition as base user
   - Submit successfully
   - Verify state changes

2. **Approval Flow End-to-End**
   - Submit requisition
   - Approve as Dept Manager
   - Approve as FMO
   - Verify allocation created
   - Verify state = 'allocated'

3. **Trip Execution**
   - Assign vehicle/driver to allocation
   - Start trip
   - Complete trip with wizard
   - Verify allocation returned
   - Verify requisition completed

4. **Security Validation**
   - Base user cannot create vehicles
   - Property Manager must have role for approval
   - FMO must have role for approval
   - Multi-company isolation working

### Regression Testing

- Run full test suite after each critical fix
- Verify existing features still work
- Check chatter/activity functionality
- Validate reports still generate

---

## Success Criteria

### Phase 1 Complete When:
- [ ] All 8 critical issues resolved
- [ ] Deployment validation passes (0 failures)
- [ ] Security validation passes (0 violations)
- [ ] End-to-end workflow tested successfully
- [ ] Admin can access settings
- [ ] Multi-company isolation verified
- [ ] 50% test coverage achieved

### Production Ready When:
- [ ] Zero blocking issues
- [ ] All critical and high-priority fixes deployed
- [ ] 60% test coverage
- [ ] Performance tested with 100+ vehicles
- [ ] Documentation updated
- [ ] Training materials prepared
- [ ] Rollback plan documented

---

## Issue Summary by Priority

| Priority | Count | Estimated Effort | Status |
|----------|-------|------------------|--------|
| 🔴 Critical | 8 | 8 hours | Blocking |
| 🟠 High | 12 | 2-3 weeks | Important |
| 🟡 Medium | 10 | 6-8 weeks | Enhancement |
| 🟢 Low | 8 | 10-12 weeks | Future |
| **Total** | **38** | **~20 weeks** | - |

---

## Resource Recommendations

### Minimum Team (Phase 1):
- 1 Backend Developer (Python/Odoo)
- Budget: 40 hours

### Recommended Team (Phases 1-2):
- 1 Senior Backend Developer
- 1 QA Engineer (part-time)
- Budget: 160 hours

### Full Team (Phases 1-3):
- 1 Senior Backend Developer
- 1 Backend Developer
- 1 Frontend Developer (for dashboard/maps)
- 1 QA Engineer
- Budget: 400 hours

---

## Decision Points

### Immediate Decisions Needed:

1. **SMS Module:** Keep or remove?
   - **Recommendation:** Remove unless SMS is business requirement

2. **Auto-Allocation:** Enable by default?
   - **Recommendation:** Yes, but add feature flag

3. **Vehicle Driver Field:** Migrate now or defer?
   - **Recommendation:** Defer to Phase 2 (requires data migration)

4. **Fuel Management:** Build now or buy integration?
   - **Recommendation:** Defer to Phase 3; focus on core workflow first

5. **Test Coverage Target:** 60%, 80%, or 90%?
   - **Recommendation:** 60% for Phase 1, 80% for Phase 2

---

## Deployment Checklist

### Pre-Deployment:
- [ ] All critical fixes applied
- [ ] Test suite passes (0 failures)
- [ ] Security validation passes
- [ ] Database backup taken
- [ ] Rollback plan documented
- [ ] Performance tested (100+ vehicles)
- [ ] User acceptance testing complete

### Deployment:
- [ ] Deploy to staging first
- [ ] Smoke test all workflows
- [ ] Monitor logs for 24 hours
- [ ] Deploy to production
- [ ] Enable monitoring alerts

### Post-Deployment:
- [ ] Monitor approval workflows
- [ ] Check cron job execution
- [ ] Verify multi-company isolation
- [ ] Collect user feedback
- [ ] Address hotfixes within 48 hours

---

## Next Steps

### Immediate Action (This Week):
1. Review this roadmap with stakeholders
2. Prioritize Phase 1 tasks
3. Set up development environment
4. Create feature branch: `fix/critical-blockers`
5. Start with quick wins (45 minutes)
6. Test each fix before committing

### Week 1 Goal:
Complete all 8 critical fixes and deploy to staging

### Week 2-3 Goal:
Complete high-priority security and UX improvements

### Month 2 Goal:
Deploy production-ready v18.0.2.0.0 with analytics

---

**End of Roadmap**

For questions or clarifications, refer to:
- `HAGBES_FLEET_AUDIT_REPORT.md` - Technical details
- `DEVELOPMENT_STATUS_REPORT.md` - Current status
- `deployment/final_validation_report.txt` - Validation results
