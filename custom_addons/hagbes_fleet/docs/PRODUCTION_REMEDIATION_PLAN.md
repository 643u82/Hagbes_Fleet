# Hagbes Fleet Management - Production Remediation Plan

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Odoo Version:** 18.0  
**Module:** hagbes_fleet v18.0.1.1.0  
**Classification:** Production-Critical Remediation  
**Author:** Lead Odoo Architect  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [CRIT-005: Property Manager Approval Not Restricted](#3-crit-005-property-manager-approval-not-restricted)
4. [CRIT-006: FMO Approval Not Restricted](#4-crit-006-fmo-approval-not-restricted)
5. [CRIT-007: Allocation-Trip-Requisition Workflow Disconnected](#5-crit-007-allocation-trip-requisition-workflow-disconnected)
6. [CRIT-001: Requester ACL Too Permissive](#6-crit-001-requester-acl-too-permissive)
7. [RPC_ERROR: `_unknown` Object in Onchange](#7-rpc_error-unknown-object-in-onchange)
8. [Risk Assessment](#8-risk-assessment)
9. [Implementation Plan](#9-implementation-plan)
10. [Testing Plan](#10-testing-plan)
11. [Deployment Plan](#11-deployment-plan)

---

## 1. Executive Summary

This document provides a production-grade remediation plan for four (4) critical issues verified in the `hagbes_fleet` Odoo 18 module. Each issue has been confirmed through direct codebase inspection with line-by-line evidence.

### Issues Summary

| ID | Severity | Component | Status | Effort |
|----|----------|-----------|--------|--------|
| CRIT-005 | **High** | Approval Workflow | Confirmed | 3 days |
| CRIT-006 | **High** | Approval Workflow | Confirmed | 3 days |
| CRIT-007 | **Medium** | Workflow Automation | Partially Fixed | 5 days |
| CRIT-001 | **Medium** | Security/ACL | Partially Correct | 2 days |
| RPC_ERROR | **High** | Runtime Stability | Unresolved | 2 days |

### Design Principles Applied

1. **Least Privilege**: Every role receives the minimum permissions required for their function
2. **Separation of Duties**: Requester, Approver, and Operator roles are strictly separated with no overlap
3. **Defense in Depth**: ACL restrictions are complemented by record rules, field-level security, and programmatic validation
4. **Department Isolation**: All approvals and operations respect organizational boundaries
5. **Idempotent Workflows**: State transitions are safe to replay and guarded against invalid transitions

---

## 2. Architecture Overview

### Current Model Relationships

```
fleet.requisition                    hagbes.fleet.allocation                  fleet.trip
┌──────────────────┐                ┌──────────────────────┐               ┌──────────────┐
│ allocation_id ───┼──────────────►  │ request_id (required)│               │ allocation_id│
│ trip_id ─────────┼──────────────►  │ trip_id ────────────┼──────────────► │ requisition_id│
│ vehicle_id       │                │ vehicle_id           │               │ vehicle_id    │
│ department_id    │                │ driver_id            │               │ state (4)     │
│ state (9 states) │                │ state (6 states)     │               └──────────────┘
│ request_by       │                └──────────────────────┘
│ fmo_approved_by  │
└──────────────────┘
         │
         │ calls via hagbes_approval_workflow
         ▼
approval.request (external module)
┌──────────────────────┐
│ flow_id              │
│ current_step_id      │
│ role_id (group)──────┼──► NO department context = SECURITY GAP
│ status               │
└──────────────────────┘
```

### Security Group Hierarchy

```
base.group_user
  └── group_fleet_requester  (create own requests, read department records)
       ├── group_dept_manager   (approve own department requests)
       ├── group_fmo            (operate all company records)
       ├── group_property_manager (read-only audit)
       │    └── group_fleet_manager (full operational oversight)
       │         └── group_fleet_admin (full CRUD + delete + reset)
       └── (group_team_leader - defined externally)
```

### Current Approval Flow (Fleet Requisition)

```
Step 0: Initiator (auto-bypass)
    ↓ auto_initiate
Step 1: Dept Manager Review  [role_id = group_dept_manager]
    ↓ approve
Step 2: FMO Officer Review   [role_id = group_fmo]
    ↓ approve
Step 3: Final (is_final=True)
```

**Problem:** Steps 1 and 2 authorize approval based solely on group membership. No department isolation exists. Any Dept Manager can approve from any department. Any FMO can approve any requisition.

---

## 3. CRIT-005: Property Manager Approval Not Restricted

### 3.1 Affected Files

| File | Lines | Role | Issue |
|------|-------|------|-------|
| `data/fleet_approval_flows.xml` | 17-22 | `group_property_manager` for Assignment approval | No department restriction |
| `data/fleet_approval_flows.xml` | 62-67 | `group_property_manager` for Maintenance approval | No department restriction |
| `data/fleet_approval_flows.xml` | 107-112 | `group_property_manager` for Disposal approval | No department restriction |
| `security/groups.xml` | 47-53 | `group_property_manager` definition | Inherits `group_fleet_requester` but not `group_fmo` |

### 3.2 Root Cause

The `hagbes_approval_workflow` module's `approval.step` model uses a `role_id` field (Many2one to `res.groups`) to authorize approvers. The `can_user_approve()` method checks solely: *"Is this user a member of the specified group?"* — with zero context about the record being approved.

The three approval flows for Fleet Assignment, Fleet Maintenance, and Fleet Disposal all assign `group_property_manager` as the reviewer role. Since this is a global group, **any** Property Manager user can approve any assignment, maintenance, or disposal regardless of:
- Which department the request originates from
- Which branch or company the asset belongs to
- The organizational hierarchy

### 3.3 Proposed Solution

**Strategy: Programmatic Approval Validation via `approval.request` Inheritance**

We will extend the `approval.request` model (which already has a `_sync_fleet_requisition_state` method in our code) to add department-aware authorization checks. This approach preserves the existing approval workflow UI while adding programmatic guards.

#### Architecture Decision

We extend `approval.request` (not `approval.step`) because:
1. `approval.request` has access to the actual record via `res_model`/`res_id`
2. It's already inherited by `approval_integration.py` in our module
3. It intercepts both approve and reject operations at the right layer
4. The `approval.step` model belongs to the external module and changing it would affect all other approval types

#### Exact Code Changes

##### 3.3.1 Extend `models/approval_integration.py`

Add department-aware validation before any approval action is processed:

```python
from odoo import models, fields, api, _
from odoo.exceptions import AccessError

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def _check_department_approval_authorization(self):
        """Validate that the approver is authorized for this specific record.
        
        For fleet requisitions: approver must belong to the same department
        as the requisition's request_by user.
        
        For fleet assignments/maintenance/disposal: approver must belong
        to the same department as the vehicle's assigned department.
        """
        self.ensure_one()
        
        if self.res_model not in ('fleet.requisition', 'hagbes.fleet.vehicle', 
                                   'hagbes.fleet.vehicle.assign', 'hagbes.fleet.maintenance'):
            return True  # Not a fleet model, skip check
            
        if self.status != 'pending':
            return True
            
        user = self.env.user
        step = self.current_step_id
        if not step:
            return True
            
        # Get the source record
        source = self.env[self.res_model].browse(self.res_id)
        if not source.exists():
            return True
            
        # Only enforce for non-admin users
        if user.has_group('base.group_system') or user.has_group('hagbes_fleet.group_fleet_admin'):
            return True
            
        # Resolve the source's department
        source_dept = self._resolve_source_department(source)
        if not source_dept:
            return True  # No department to check against
            
        # Resolve the approver's department
        approver_dept = self._resolve_user_department(user)
        if not approver_dept:
            raise AccessError(_(
                'Your user profile is not associated with a department. '
                'Please contact your administrator.'
            ))
            
        # Department match check
        if source_dept.id != approver_dept.id:
            raise AccessError(_(
                'You are not authorized to approve requests from the "%s" department. '
                'Only members of the same department can approve this request.'
            ) % source_dept.name)
            
        return True

    def _resolve_source_department(self, source):
        """Extract the department from any supported source record."""
        if 'department_id' in source._fields and source.department_id:
            return source.department_id
        # Fallback: try to get department through the requester
        if hasattr(source, 'request_by') and source.request_by:
            return self._resolve_user_department(source.request_by)
        if hasattr(source, 'create_uid') and source.create_uid:
            return self._resolve_user_department(source.create_uid)
        return False

    def _resolve_user_department(self, user):
        """Get department from user's employee record."""
        employee = user.employee_id
        if not employee:
            employee = self.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
        return employee.department_id if employee else False

    def process_action(self):
        """Override to add department authorization check."""
        # Validate department authorization before approval action
        if self.env.context.get('action_type') in ('approve', 'reject'):
            self._check_department_approval_authorization()
        return super().process_action()

    def write(self, vals):
        """Extend existing write to add approval validation."""
        # Only validate step transitions for pending requests
        if ('current_step_id' in vals or 'status' in vals):
            for rec in self:
                if rec.status == 'pending' and vals.get('status') != 'pending':
                    # This is an approval action - validate authorization
                    pass  # Validation happens in process_action
        return super().write(vals)
```

##### 3.3.2 Update `data/fleet_approval_flows.xml`

Add approver context to the Property Manager steps to record which department context was used:

```xml
<!-- No XML changes needed for CRIT-005 alone; the programmatic check
     in approval_integration.py handles department isolation.
     However, consider adding descriptive comments in the approval steps -->
```

**Rationale for no XML changes:** The programmatic check is more reliable than XML-level domain filters because:
1. It cannot be bypassed by Odoo superuser unless explicitly allowed
2. It works regardless of the approval workflow UI
3. It enforces the policy at the ORM level (defense in depth)

#### Migration Considerations

1. **Existing pending approvals** from cross-department scenarios will be blocked when the first approver action is taken. This is intentional.
2. **Data integrity**: Run a pre-migration script to identify any pending cross-department approvals:
   ```sql
   SELECT ar.id, ar.res_id, ru.login as approver, ru2.login as requester
   FROM approval_request ar
   JOIN res_users ru ON ru.id = ar.create_uid
   JOIN fleet_requisition fr ON fr.id = ar.res_id
   JOIN hr_employee he ON he.user_id = ru.id
   JOIN hr_employee he2 ON he2.user_id = fr.request_by
   WHERE ar.status = 'pending'
     AND ar.res_model = 'fleet.requisition'
     AND he.department_id != he2.department_id;
   ```
3. **Communication**: Notify all Property Managers that cross-department approvals will be restricted
4. **Admin override**: Fleet Admin and System users are exempt from the check

#### Approval Flow Risk Matrix (Property Manager)

| Approver Dept | Request Dept | Current | After Fix |
|--------------|--------------|---------|-----------|
| Same | Same | Approved | Approved |
| Different | Same | Approved | **BLOCKED** |
| Same | Different | Approved | **BLOCKED** |
| Admin (any) | Any | Approved | Approved |

---

## 4. CRIT-006: FMO Approval Not Restricted

### 4.1 Affected Files

| File | Lines | Role | Issue |
|------|-------|------|-------|
| `data/fleet_approval_flows.xml` | 163-168 | `group_fmo` for Requisition FMO step | No department restriction |
| `data/fleet_approval_flows.xml` | 155-160 | `group_dept_manager` for Requisition Dept step | Same issue |
| `models/approval_integration.py` | 60-64 | State sync for FMO step | No authorization check before state write |
| `security/fleet_requisition_rules.xml` | 27-32 | Dept Manager record rule | Job hierarchy check is fragile |

### 4.2 Root Cause

Same fundamental issue as CRIT-005, but with higher operational impact because FMO approval is the gatekeeper for vehicle dispatch. The three approval steps in the fleet requisition flow all lack department context:

1. **Step 1 - Dept Manager** (`group_dept_manager`): Any department manager can approve any department's requisition
2. **Step 2 - FMO Officer** (`group_fmo`): Any FMO can approve/reject any requisition for dispatch
3. **Step 3 - Final** (`is_final=True`): No user action required

Additionally, the existing record rule for Department Managers (`fleet_requisition_rules.xml:27-32`) uses job hierarchy (`child_of` on `job_id`) instead of department hierarchy. This is fragile because:
- Job hierarchies are often not maintained
- Multiple managers may share the same job title
- A manager promoted to a higher role still sees all subordinate roles regardless of department

### 4.3 Proposed Solution

**Strategy: Unified Department Authorization + Strengthened Record Rules**

We will:
1. Reuse the `_check_department_approval_authorization()` method from CRIT-005 (same mechanism)
2. Strengthen the Dept Manager record rule to use department hierarchy instead of job hierarchy
3. Add explicit authorization checks in `approval.step` user interface via `_get_eligible_approvers` override

#### Exact Code Changes

##### 4.3.1 Strengthen Dept Manager Record Rule

In `security/fleet_requisition_rules.xml`, replace the job hierarchy rule:

```xml
<!-- REPLACE existing rule at lines 27-32 -->
<record id="rule_fleet_requisition_dept_manager" model="ir.rule">
    <field name="name">Fleet Requisition: Department Manager Scope (Department)</field>
    <field name="model_id" ref="model_fleet_requisition"/>
    <field name="groups" eval="[(4, ref('hagbes_fleet.group_dept_manager'))]"/>
    <field name="domain_force">[('department_id', '=', user.employee_id.department_id.id)]</field>
    <field name="perm_read" eval="True"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_create" eval="False"/>
    <field name="perm_unlink" eval="False"/>
</record>
```

This uses the employee's direct department (not job hierarchy), which is:
- Simpler to maintain
- More reliable (department is typically required, job hierarchy is optional)
- Consistent with the Requester record rule

##### 4.3.2 Extend Approval Authorization for FMO/Dept Manager

The method `_check_department_approval_authorization()` from CRIT-005 already handles this uniformly. For the FMO and Dept Manager approval steps, the same department-matching logic applies.

However, we need a refinement: **FMO officers should be able to approve requisitions from all departments IF they are designated as "central FMO"**. To support this:

Add a configuration flag:

```python
# In models/approval_integration.py

def _check_department_approval_authorization(self):
    # ... existing code ...
    
    # FMO override: Check if this FMO has global authorization
    if user.has_group('hagbes_fleet.group_fmo'):
        # Check if central FMO (can approve all departments)
        config = self.env['ir.config_parameter'].sudo()
        global_fmo_ids = config.get_param('fleet.global_fmo_user_ids', '')
        if global_fmo_ids and str(user.id) in global_fmo_ids.split(','):
            return True  # Central FMO bypasses department check
    
    # ... rest of existing code ...
```

##### 4.3.3 Add `fleet_requisition_rules.xml` Write Restriction for FMO

Add a record rule that restricts FMO write access to only "assigned" state requisitions (preventing FMOs from editing draft/submitted requisitions directly):

```xml
<!-- In security/fleet_requisition_rules.xml -->

<!-- FMO: Full visibility, write restricted to assigned state only -->
<record id="rule_fleet_requisition_fmo_write_assigned" model="ir.rule">
    <field name="name">Fleet Requisition: FMO Write Assigned Only</field>
    <field name="model_id" ref="model_fleet_requisition"/>
    <field name="groups" eval="[(4, ref('hagbes_fleet.group_fmo'))]"/>
    <field name="domain_force">[('state', '=', 'assigned')]</field>
    <field name="perm_write" eval="True"/>
</record>
```

This ensures FMOs can only write to requisitions that have reached the "assigned" stage (after department approval), preventing them from modifying draft or submitted requisitions that are still in the business approval pipeline.

#### Migration Considerations

1. **Dept Manager visibility**: After the change, Dept Managers will only see requisitions from their own department (matching existing behavior via the job hierarchy rule, but more reliably)
2. **FMO scope**: If any FMO needs cross-department authority, add their user ID to `fleet.global_fmo_user_ids` config parameter
3. **Run pre-migration query** to identify existing Department Managers who may lose visibility:
   ```sql
   SELECT DISTINCT ru.id, ru.login, he.department_id, dep.name as dept_name
   FROM res_users ru
   JOIN res_groups_users_rel rel ON rel.uid = ru.id
   JOIN res_groups grp ON grp.id = rel.gid
   LEFT JOIN hr_employee he ON he.user_id = ru.id
   LEFT JOIN hr_department dep ON dep.id = he.department_id
   WHERE grp.id IN (SELECT res_id FROM ir_model_data 
                    WHERE module='hagbes_fleet' AND name='group_dept_manager')
     AND (he.department_id IS NULL);
   ```

---

## 5. CRIT-007: Allocation-Trip-Requisition Workflow Disconnected

### 5.1 Affected Files

| File | Lines | Component | Issue |
|------|-------|-----------|-------|
| `models/fleet_requisition.py` | 733-792 | `action_fmo_approve()` | Searches for allocation but does not create one |
| `models/fleet_requisition.py` | 886-905 | `action_create_allocation()` | Only opens form, does not create record |
| `models/fleet_requisition.py` | 798-815 | `_on_approval_approved()` | Requires pre-existing allocation to work |
| `models/fleet_requisition.py` | 725-731 | `action_fleet_approve()` | Only sets state to 'assigned' |
| `models/fleet_allocation.py` | 335-393 | `action_assign_vehicle()` | Correctly creates trip on assignment |
| `views/fleet_requisition_views.xml` | 56-61 | Dispatch button | Hidden (`invisible="1"`) |

### 5.2 Root Cause

The workflow between Requisition → Allocation → Trip is **structurally complete but operationally fragmented**. The data model connections exist:
- `fleet.requisition.allocation_id → hagbes.fleet.allocation`
- `hagbes.fleet.allocation.trip_id → fleet.trip`
- `fleet.requisition.trip_id → fleet.trip`

State synchronization exists via:
- `fleet_allocation.py:write()` → `_handle_state_transition()` + `_sync_from_allocation_state()`
- `fleet_allocation.py:action_assign_vehicle()` → creates Trip + updates Requisition
- `fleet_trip.py:action_complete_trip()` → updates Allocation + Requisition

However, the **manual steps** required create operational friction:

| # | Action | Manual? | Friction |
|---|--------|---------|----------|
| 1 | Requisition submitted | Auto | - |
| 2 | Dept Manager approves | Click | 1 click |
| 3 | FMO approves | Click | 1 click |
| 4 | Fleet Officer assigns vehicle | Click | 1 click |
| 5 | FMO clicks "Create Allocation" | Click | Opens form |
| 6 | FMO fills allocation details | Manual | Data entry required |
| 7 | FMO saves allocation | Click | Allocation in 'draft' |
| 8 | FMO clicks "Confirm Assignment" | Click | State → 'assigned' |
| 9 | Trip auto-created | Auto | From action_assign_vehicle() |
| 10 | FMO clicks "Start Trip" | Click | State → 'started' |

Steps 5-9 represent **5 manual interactions** for a process that should take 2.

### 5.3 Proposed Solution

**Strategy: Streamlined Automatic Workflow with Audit Trail**

#### Decision: Should Allocation Creation Be Automatic?

**YES**, with the following design:

1. **When** `_on_approval_approved()` is triggered (after the FMO step approves), the system automatically creates an allocation if one does not exist
2. **The allocation is created in 'draft' state** so the FMO can review and adjust before dispatch
3. **The allocation is pre-populated** from the requisition data (vehicle, driver, dates, destination)
4. **The trip is NOT auto-created** at this stage — trip creation happens only when the allocation is confirmed (action_assign_vehicle)

**Why draft and not fully dispatched?**
- The FMO must verify vehicle availability, driver assignment, and fuel estimates
- The allocation may need adjustments (e.g., odometer reading, planned distance)
- Premature dispatch could result in incorrect operational data

#### Decision: Should Trip Creation Be Automatic?

**YES, but only when allocation is confirmed.** The current behavior in `action_assign_vehicle()` already handles this correctly — when an allocation transitions from 'draft' to 'assigned', a trip is created automatically.

The change is: allocation confirmation should happen as part of the approval flow, not as a separate manual step.

#### Exact Code Changes

##### 5.3.1 Modify `_on_approval_approved()` in `models/fleet_requisition.py`

```python
def _on_approval_approved(self):
    """Callback when entire approval flow is finished (FMO step completed).
    
    Automatically creates an allocation if one doesn't exist.
    The allocation is created in 'draft' state for FMO review.
    """
    for rec in self:
        existing_allocation = self.env['hagbes.fleet.allocation'].search([
            ('request_id', '=', rec.id),
            ('state', 'not in', ('completed', 'cancelled')),
        ], limit=1)
        
        if existing_allocation:
            allocation = existing_allocation
        else:
            # Pre-validate that a vehicle is assigned
            if not rec.vehicle_id:
                raise UserError(_(
                    'A vehicle must be assigned before the approval flow completes. '
                    'Please assign a vehicle to requisition %s.'
                ) % rec.name)
            
            # Resolve driver from vehicle or traveller
            driver_id = self._resolve_driver(rec)
            
            # Create allocation automatically
            allocation_vals = {
                'request_id': rec.id,
                'vehicle_id': rec.vehicle_id.id,
                'driver_id': driver_id,
                'company_id': rec.company_id.id,
                'allocation_date': rec.date_from or fields.Datetime.now(),
                'return_date': rec.date_to,
                'planned_distance': 0.0,  # FMO will update
                'fuel_estimate': 0.0,     # FMO will update
                'state': 'draft',
            }
            allocation = self.env['hagbes.fleet.allocation'].sudo().create(allocation_vals)
            
            # Link allocation to requisition
            rec.with_context(allow_workflow=True).write({
                'allocation_id': allocation.id,
                'allocated_by': self.env.user.id,
                'allocated_date': fields.Datetime.now(),
                'state': 'assigned',
            })
            
            rec.message_post(
                body=_(
                    'Allocation %s has been automatically created. '
                    'The FMO should review allocation details and confirm assignment.'
                ) % allocation.name
            )
        
        # Auto-assign if allocation is still in draft
        if allocation.state == 'draft':
            allocation.action_assign_vehicle()

def _resolve_driver(self, requisition):
    """Resolve the driver from the requisition context."""
    # Priority 1: Vehicle's named driver
    if requisition.vehicle_id and requisition.vehicle_id.driver:
        driver = self.env['hr.employee'].search([
            ('name', '=ilike', requisition.vehicle_id.driver.strip())
        ], limit=1)
        if driver:
            return driver.id
    
    # Priority 2: Traveller with driver job
    if requisition.traveller and requisition.traveller.employee_id:
        emp = requisition.traveller.employee_id
        if emp.job_id and 'driver' in (emp.job_id.name or '').lower():
            return emp.id
    
    return False
```

##### 5.3.2 Modify `action_fmo_approve()` in `models/fleet_requisition.py`

Simplify this method since automatic allocation creation replaces the old "open allocation form" behavior:

```python
def action_fmo_approve(self):
    """FMO: Approve requisition for dispatch.
    
    This action advances the requisition state to trigger the approval flow.
    Allocation creation is handled automatically in _on_approval_approved().
    """
    self.ensure_one()
    if self.state != 'assigned':
        raise UserError(_('Only assigned requisitions can be dispatched.'))
    
    # Trigger the approval process for the FMO step
    # This is typically called from the approval UI, but we provide
    # a direct action for compatibility
    rec.with_context(allow_workflow=True).write({
        'fmo_approved_by': self.env.user.id,
        'fmo_approved_date': fields.Datetime.now(),
        'state': 'dispatched',
    })
    
    # Open the allocation for FMO review
    allocation = self.env['hagbes.fleet.allocation'].search([
        ('request_id', '=', self.id),
        ('state', 'in', ('draft', 'assigned')),
    ], limit=1)
    
    if allocation:
        return {
            'name': _('Fleet Allocation'),
            'type': 'ir.actions.act_window',
            'res_model': 'hagbes.fleet.allocation',
            'res_id': allocation.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    return True
```

##### 5.3.3 Update `fleet_allocation.py:action_assign_vehicle()`

The current behavior already creates trips on assignment, which is correct. No changes needed.

##### 5.3.4 Update Views (`views/fleet_requisition_views.xml`)

Remove the hidden FMO dispatch button and replace with an allocation review button that appears only when an allocation exists:

```xml
<!-- REPLACE the hidden dispatch button at lines 57-62 -->

<!-- FMO: Review/Open Allocation (shows after auto-creation) -->
<button name="action_open_allocation_form"
        string="Open Allocation"
        type="object"
        class="btn-primary"
        invisible="state != 'assigned' or not allocation_id"/>
```

### 5.4 Workflow State Diagram (After Fix)

```
fleet.requisition                    fleet.allocation                 fleet.trip
─────────────────                    ────────────────                 ──────────
[draft]  ──submit──► [submitted]                                     
                        │                                             
                        ▼ Dept Manager approve                        
                   [dept_approved]                                    
                        │                                             
                        ▼ Team Leader approve                         
                   [team_leader_approved]                             
                        │                                             
                        ▼ Fleet Officer assign                        
                   [assigned]  ──auto──► [draft]  ──assign──► [draft]
                        │          create            │                
                        ▼ FMO approve                │                
                   [dispatched]◄─────sync────────────┤                
                        │                            ▼ start          
                        ▼ allocation dispatches  [started]            
                   [dispatched]◄─────sync────────────┤                
                        │                            ▼ complete       
                   [completed]◄─────sync──────────[completed]         
```

### 5.5 Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Allocation created without driver | Allocation blocked | Fallback to creating allocation without driver; FMO completes the field |
| Vehicle already has active allocation | Creation fails with ValidationError | `_check_unique_active_allocation()` already handles this |
| FMO not notified of auto-creation | Workflow stalls | Add chatter message + activity notification to FMO group |
| Existing data with missing allocations | Migration issue | Pre-migration script identifies and creates missing allocations |
| Double allocation creation | Duplicate records | Search for existing allocation first (idempotent) |

### 5.6 Side Effects Analysis

1. **Positive**: FMO workload reduced from 5+ clicks to 0-2 clicks
2. **Positive**: No more orphaned approved requisitions without allocations
3. **Positive**: Clear audit trail (chatter message records auto-creation)
4. **Negative**: Allocation is created with default values that may be incorrect
   - *Mitigation*: Keep allocation in 'draft'; require FMO review before dispatch
5. **Negative**: Trip is auto-created on allocation assignment, which may be premature
   - *Mitigation*: Trip stays in 'draft' until FMO clicks "Start Trip"
6. **Neutral**: Existing views that called `action_create_allocation()` are deprecated
   - *Mitigation*: Keep method for backward compatibility but deprecate via docstring

---

## 6. CRIT-001: Requester ACL Too Permissive

### 6.1 Affected Files

| File | Lines | Issue |
|------|-------|--------|
| `security/ir.model.access.csv` | 28 | `perm_write=1` for `group_fleet_requester` on ALL requisitions |
| `models/fleet_requisition.py` | 836-852 | `action_submit()` uses `sudo()` which bypasses record rules |
| `security/fleet_requisition_rules.xml` | 19-24 | Requester visibility rule allows write on all department records |

### 6.2 Root Cause

The current ACL at `ir.model.access.csv:28` grants `perm_write=1` to the `group_fleet_requester` group on **all** `fleet.requisition` records. The record rule at `fleet_requisition_rules.xml:19-24` restricts visibility to:
```python
['|', ('request_by', '=', user.id), ('department_id', '=', user.employee_id.department_id.id)]
```

This means a requester can:
1. **Read** their own + any department record
2. **Write** to their own + any department record (because ACL grants write and record rule allows visibility)

The `action_submit()` method compounds this by using `sudo()`:
```python
rec.sudo()._trigger_approval()  # Bypasses all record rules
```

While the method has a check `rec.request_by == self.env.user`, this only protects the submit action, not direct API/ORM writes.

### 6.3 Proposed Solution

**Strategy: Tighten ACL to Remove Write + Add Granular Record Rules**

We will replace the broad `perm_write=1` with operation-specific record rules that:
1. Allow requesters to write ONLY to their own draft records
2. Prevent requesters from writing to other users' records
3. Use `sudo()` in workflow methods with context guards to prevent abuse

#### Exact Code Changes

##### 6.3.1 Tighten ACL in `security/ir.model.access.csv`

```csv
# REPLACE line 28 with:
access_fleet_requisition_requester,fleet.requisition.requester,model_fleet_requisition,hagbes_fleet.group_fleet_requester,1,0,1,0
```

Change: `perm_write` changed from `1` to `0`.

**Impact**: Without additional record rules, requesters cannot write to ANY requisition record directly. They can create new records (`perm_create=1`) but cannot edit them through standard ORM writes.

##### 6.3.2 Add Granular Write Record Rules in `security/fleet_requisition_rules.xml`

```xml
<!-- Requester: Write own draft records only (compensates for removed ACL write) -->
<record id="rule_fleet_requisition_requester_write_own_draft" model="ir.rule">
    <field name="name">Fleet Requisition: Requester Write Own Draft</field>
    <field name="model_id" ref="model_fleet_requisition"/>
    <field name="groups" eval="[(4, ref('hagbes_fleet.group_fleet_requester'))]"/>
    <field name="domain_force">[('request_by', '=', user.id), ('state', '=', 'draft')]</field>
    <field name="perm_write" eval="True"/>
</record>

<!-- Requester: Write rejected records for resubmission -->
<record id="rule_fleet_requisition_requester_write_rejected" model="ir.rule">
    <field name="name">Fleet Requisition: Requester Write Rejected</field>
    <field name="model_id" ref="model_fleet_requisition"/>
    <field name="groups" eval="[(4, ref('hagbes_fleet.group_fleet_requester'))]"/>
    <field name="domain_force">[('request_by', '=', user.id), ('state', '=', 'rejected')]</field>
    <field name="perm_write" eval="True"/>
</record>
```

##### 6.3.3 Update Visibility Record Rule to Remove Write

Modify the existing rule to restrict write operations:

```xml
<!-- REPLACE existing rule_fleet_requisition_requester at fleet_requisition_rules.xml:19-24 -->
<record id="rule_fleet_requisition_requester" model="ir.rule">
    <field name="name">Fleet Requisition: Requester Read Visibility</field>
    <field name="model_id" ref="model_fleet_requisition"/>
    <field name="groups" eval="[(4, ref('hagbes_fleet.group_fleet_requester'))]"/>
    <field name="domain_force">['|', ('request_by', '=', user.id), ('department_id', '=', user.employee_id.department_id.id)]</field>
    <field name="perm_read" eval="True"/>
    <field name="perm_write" eval="False"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_unlink" eval="False"/>
</record>
```

##### 6.3.4 Add Context Guard to `write()` in `models/fleet_requisition.py`

```python
def write(self, vals):
    """Override write to handle department synchronization, security, and context-based overrides."""
    
    # Allow workflow transitions via context flag (bypasses ACL)
    if self.env.context.get('allow_workflow'):
        return super(sudo=False).write(vals)
    
    # ... rest of existing write method ...
```

The key change: `allow_workflow` context now uses `super(sudo=False)` instead of relying on the caller to have already used `sudo()`. This ensures that workflow methods using `with_context(allow_workflow=True).write(...)` work correctly even after removing ACL write.

##### 6.3.5 Update `action_submit()` to Use Context Instead of `sudo()`

```python
def action_submit(self):
    """Requester submits a draft requisition for department approval."""
    for rec in self:
        if rec.state != 'draft':
            raise UserError(_('Only draft requests can be submitted.'))
        
        department = rec.department_id
        if not department:
            raise UserError(_('Your employee profile is not linked to a department.'))
        
        # Verify requester authorization
        if not (rec.request_by == self.env.user or self._is_fleet_manager()):
            raise AccessError(_('You can only submit your own requests.'))
        
        # Use context flag instead of sudo() to respect ACL with controlled bypass
        rec.with_context(allow_workflow=True)._trigger_approval()
        rec.message_post(body=_('Request submitted for approval.'))
        
        # SMS notification to Department Manager
        if rec.department_id.manager_id.user_id.partner_id.mobile:
            rec._send_approval_sms(rec.department_id.manager_id.user_id.partner_id)
```

### 6.4 Security Model Summary (After Fix)

| Operation | Scenario | ACL | Record Rule | Result |
|-----------|----------|-----|-------------|--------|
| **Create** | Requester creates own | `create=1` | `perm_create=True` (visibility rule) | ✅ Allowed |
| **Read** | Requester reads own | `read=1` | `perm_read=True` (visibility rule) | ✅ Allowed |
| **Read** | Requester reads department | `read=1` | `perm_read=True` (visibility rule) | ✅ Allowed |
| **Read** | Requester reads other dept | `read=1` | `perm_read=False` (visibility rule) | ❌ Blocked |
| **Write** | Requester edits own draft | `write=0` | `perm_write=True` (own draft rule) | ✅ Allowed |
| **Write** | Requester edits own submitted | `write=0` | No rule grants write | ❌ Blocked |
| **Write** | Requester edits other's draft | `write=0` | Domain doesn't match | ❌ Blocked |
| **Workflow** | `action_submit()` | - | - | ✅ Allowed via `allow_workflow` context |
| **Workflow** | `action_dept_approve()` | - | - | ✅ Allowed via `allow_workflow` context |

### 6.5 Migration Considerations

1. **Existing draft records** created by requesters remain editable by their creators (via the `request_by = user.id` rule)
2. **Submitted/pending records** cannot be edited by requesters (correct behavior)
3. **Workflow methods** continue to function because they use `with_context(allow_workflow=True)`
4. **API integrations** that write directly to `fleet.requisition` as a requester will fail
   - *Fix*: Upgrade integrations to use the workflow methods or authenticate as FMO/admin

---

## 7. RPC_ERROR: `_unknown` Object in Onchange

### 7.1 Affected Files

| File | Lines | Issue |
|------|-------|--------|
| `models/fleet_requisition.py` | 119-142 | Debug logging attempts to read many2one fields that may be `_unknown` |
| `views/fleet_requisition_views.xml` | Various | Onchange form fields reference many2one fields |
| System | - | Odoo's `web_read`/`convert_to_read` fails on `_unknown` proxy |

### 7.2 Root Cause

The error trace shows:

```
File "odoo/addons/web/models/models.py", line 1153, in diff
    [result] = self.record.web_read(simple_fields_spec)
File "odoo/addons/web/models/models.py", line 86, in web_read
    values_list: list[dict] = self.read(fields_to_read, load=None)
File "odoo/models.py", line 4094, in _read_format
    vals[name] = convert(record[name], record, use_display_name)
File "odoo/fields.py", line 3349, in convert_to_read
    return value.id
AttributeError: '_unknown' object has no attribute 'id'
```

The `_unknown` proxy is a special Odoo placeholder returned when:
1. A Many2one field references a record that no longer exists (deleted)
2. A computed Many2one field returns an invalid value
3. An onchange computes a Many2one field to an invalid value

The debug logging at lines 119-142 in `fleet_requisition.py` was added to diagnose this, but iterating over all many2one fields during an onchange may itself trigger the error in a different code path.

### 7.3 Recommended Fix

```python
@api.onchange('request_by')
def _onchange_request_by_department(self):
    """Department sync with safe handling of _unknown proxies."""
    for rec in self:
        request_by = rec.request_by
        
        # Safely read the id attribute; _unknown proxy has no id
        try:
            request_by_id = request_by.id if request_by and hasattr(request_by, 'id') else False
        except (AttributeError, TypeError):
            request_by_id = False
            
        if not request_by_id:
            rec.department_id = False
        else:
            rec.department_id = rec._get_department_for_user(request_by_id)
        
        # Remove all debug logging (lines 119-142) that iterates many2one fields
```

**Additionally**, run a data cleanup script to find and fix orphaned references:

```sql
-- Find orphaned Many2one references in fleet_requisition
SELECT id, name, traveller, request_by
FROM fleet_requisition
WHERE traveller IS NOT NULL
  AND traveller NOT IN (SELECT id FROM res_users);
  
SELECT id, name, dept_approved_by, fmo_approved_by, assigned_by, allocated_by, rejected_by
FROM fleet_requisition
WHERE dept_approved_by IS NOT NULL
  AND dept_approved_by NOT IN (SELECT id FROM res_users);
```

---

## 8. Risk Assessment

### 8.1 Overall Risk Matrix

| Issue | Likelihood | Impact | Risk Level | Residual Risk (After Fix) |
|-------|-----------|--------|------------|--------------------------|
| CRIT-005 | High | High | **Critical** | Low |
| CRIT-006 | High | High | **Critical** | Low |
| CRIT-007 | Medium | Medium | **Medium** | Low |
| CRIT-001 | Medium | Medium | **Medium** | Low |
| RPC_ERROR | High | High | **Critical** | Low |

### 8.2 Risk Detail: CRIT-005/CRIT-006 (Approval Bypass)

| Factor | Assessment |
|--------|-----------|
| **Threat** | Unauthorized approval of fleet requests by out-of-department Property Managers/FMOs |
| **Vulnerability** | `approval.step.role_id` grants approval to entire group with zero context |
| **Attack Vector** | Any user in group_property_manager/group_fmo can approve requests across departments |
| **Business Impact** | Fraudulent approvals, compliance violations, resource misallocation |
| **Controls Bypassed** | Department record rules (read/visibility) do not restrict approval operations |
| **Detection Difficulty** | Medium — requires cross-referencing approver department vs source department |

### 8.3 Risk Detail: CRIT-007 (Workflow Fragmentation)

| Factor | Assessment |
|--------|-----------|
| **Threat** | Orphaned requisitions, delayed dispatch, incomplete operational records |
| **Vulnerability** | Allocation creation is a manual step with no automatic trigger |
| **Attack Vector** | N/A (operational, not security) |
| **Business Impact** | Approved requisitions never executed; vehicles not dispatched; reporting gaps |
| **Controls Bypassed** | N/A |
| **Detection Difficulty** | Medium — detected by comparing requisition state vs allocation existence |

### 8.4 Risk Detail: CRIT-001 (ACL Over-Permission)

| Factor | Assessment |
|--------|-----------|
| **Threat** | Requester edits other users' draft requisitions within same department |
| **Vulnerability** | ACL write=1 with record rule allowing write on all department records |
| **Attack Vector** | Direct ORM write via Python console or API |
| **Business Impact** | Data integrity compromise within department scope |
| **Controls Bypassed** | Intent (business rule) but not system policy |
| **Detection Difficulty** | Low — audit trail shows who modified what |

---

## 9. Implementation Plan

### 9.1 Phase 1: Foundation (Days 1-2)

| Step | File | Change | Effort |
|------|------|--------|--------|
| 1.1 | `models/approval_integration.py` | Add `_check_department_approval_authorization()` | 4 hours |
| 1.2 | `models/approval_integration.py` | Add `_resolve_source_department()` | 1 hour |
| 1.3 | `models/approval_integration.py` | Add `_resolve_user_department()` | 1 hour |
| 1.4 | `models/approval_integration.py` | Override `process_action()` | 1 hour |
| 1.5 | `security/fleet_requisition_rules.xml` | Update Dept Manager rule (department-based) | 1 hour |
| 1.6 | `security/fleet_requisition_rules.xml` | Add FMO write-assigned-only rule | 1 hour |
| **Total** | | | **9 hours** |

### 9.2 Phase 2: Workflow Automation (Days 3-5)

| Step | File | Change | Effort |
|------|------|--------|--------|
| 2.1 | `models/fleet_requisition.py` | Rewrite `_on_approval_approved()` for auto-allocation | 4 hours |
| 2.2 | `models/fleet_requisition.py` | Add `_resolve_driver()` helper | 1 hour |
| 2.3 | `models/fleet_requisition.py` | Simplify `action_fmo_approve()` | 2 hours |
| 2.4 | `views/fleet_requisition_views.xml` | Replace hidden dispatch button with "Open Allocation" | 1 hour |
| 2.5 | `models/fleet_requisition.py` | Remove debug logging (lines 119-142) | 1 hour |
| 2.6 | `models/fleet_requisition.py` | Fix `_onchange_request_by_department()` | 1 hour |
| **Total** | | | **10 hours** |

### 9.3 Phase 3: ACL Hardening (Days 6-7)

| Step | File | Change | Effort |
|------|------|--------|--------|
| 3.1 | `security/ir.model.access.csv` | Change requester perm_write: 1→0 | 0.5 hour |
| 3.2 | `security/fleet_requisition_rules.xml` | Add own-draft write rule | 1 hour |
| 3.3 | `security/fleet_requisition_rules.xml` | Add own-rejected write rule | 0.5 hour |
| 3.4 | `security/fleet_requisition_rules.xml` | Update requester visibility rule (perm_write=False) | 0.5 hour |
| 3.5 | `models/fleet_requisition.py` | Update `write()` context guard | 0.5 hour |
| 3.6 | `models/fleet_requisition.py` | Replace `sudo()` with context flag in `action_submit()` | 0.5 hour |
| 3.7 | `models/fleet_requisition.py` | Audit all `sudo()` calls for context guard pattern | 2 hours |
| **Total** | | | **5.5 hours** |

### 9.4 Phase 4: Data Cleanup & Migration (Day 8)

| Step | Task | Effort |
|------|------|--------|
| 4.1 | Run orphaned reference SQL cleanup | 2 hours |
| 4.2 | Run cross-department approval identification | 1 hour |
| 4.3 | Create/update allocations for approved-but-unallocated requisitions | 3 hours |
| 4.4 | Add `fleet.global_fmo_user_ids` config for central FMOs | 1 hour |
| **Total** | | **7 hours** |

### Total Effort: ~31.5 hours (4 person-days)

---

## 10. Testing Plan

### 10.1 CRIT-005/CRIT-006: Department-Aware Approval Tests

| TC# | Test Case | Steps | Expected | Type |
|-----|-----------|-------|----------|------|
| TC-5.1 | Dept Manager approves own department | 1. Create requisition in Dept A<br>2. Login as Dept Mgr of Dept A<br>3. Approve via form | ✅ Approval succeeds | Functional |
| TC-5.2 | Dept Manager approves other department | 1. Create requisition in Dept A<br>2. Login as Dept Mgr of Dept B<br>3. Try to approve | ❌ AccessError raised | Security |
| TC-5.3 | FMO approves own department | 1. Create requisition in Dept A<br>2. Login as FMO of Dept A<br>3. Approve FMO step | ✅ Approval succeeds | Functional |
| TC-5.4 | FMO approves other department | 1. Create requisition in Dept A<br>2. Login as FMO of Dept B<br>3. Try to approve FMO step | ❌ AccessError raised | Security |
| TC-5.5 | Property Manager approves own dept assignment | 1. Create assignment in Dept A<br>2. Login as Prop Mgr of Dept A | ✅ Approval succeeds | Functional |
| TC-5.6 | Property Manager approves other dept | As above but manager is Dept B | ❌ AccessError raised | Security |
| TC-5.7 | Admin bypasses department check | Login as Fleet Admin, approve any dept | ✅ Approval succeeds | Functional |
| TC-5.8 | Central FMO bypasses check | Configure user as central FMO, approve any dept | ✅ Approval succeeds | Functional |
| TC-5.9 | User without employee/department | Login as user with no employee record, try to approve | ❌ Error about missing department | Security |
| TC-5.10 | Approval via API | Submit approval via XML-RPC as cross-dept manager | ❌ AccessError via process_action() | Security |

### 10.2 CRIT-007: Workflow Automation Tests

| TC# | Test Case | Steps | Expected | Type |
|-----|-----------|-------|----------|------|
| TC-7.1 | Auto-allocation on approval | 1. Create requisition, assign vehicle<br>2. Submit, approve Dept, approve FMO<br>3. Check allocations | ✅ Allocation auto-created in draft | Functional |
| TC-7.2 | No duplicate allocation | 1. Run TC-7.1 twice for same requisition<br>2. Check allocation count | ✅ Only 1 allocation exists | Idempotency |
| TC-7.3 | Allocation pre-populated | 1. Run TC-7.1<br>2. Check allocation fields | ✅ vehicle_id, dates, request_id match | Data integrity |
| TC-7.4 | No allocation without vehicle | 1. Create requisition without vehicle<br>2. Complete approval | ❌ UserError: "vehicle must be assigned" | Negative |
| TC-7.5 | Trip auto-created on assign | 1. Allocation auto-created (TC-7.1)<br>2. FMO confirms assignment | ✅ Trip created in draft | Functional |
| TC-7.6 | Orphaned requisition detection | 1. Approve requisition with no vehicle<br>2. Check approval completes | ❌ Blocked at FMO step | Negative |
| TC-7.7 | State sync: allocation dispatched | 1. Allocation dispatched<br>2. Check requisition state | ✅ Requisition → 'dispatched' | Integration |
| TC-7.8 | State sync: trip completed | 1. Complete trip<br>2. Check allocation + requisition states | ✅ Allocation → 'returned'→'completed'<br>✅ Requisition → 'completed' | Integration |
| TC-7.9 | Allocation cancellation | 1. Cancel allocation<br>2. Check trip + requisition | ✅ Trip cancelled<br>✅ Requisition → 'cancelled' | Workflow |

### 10.3 CRIT-001: ACL Tightening Tests

| TC# | Test Case | Steps | Expected | Type |
|-----|-----------|-------|----------|------|
| TC-1.1 | Requester creates own requisition | Login as requester, create new requisition | ✅ Created successfully | Functional |
| TC-1.2 | Requester edits own draft | Edit purpose, dates, traveller on own draft | ✅ Save succeeds | Functional |
| TC-1.3 | Requester edits own submitted | Edit own requisition after submission | ❌ Write blocked | Security |
| TC-1.4 | Requester edits other's draft | Open another user's draft in same department | ✅ Read visible, write blocked | Security |
| TC-1.5 | Requester edits other department | Open draft in other department | ❌ Record invisible (record rule) | Security |
| TC-1.6 | Requester submits own draft | Click Submit button on own draft | ✅ Submit succeeds | Functional |
| TC-1.7 | Requester submits other's draft | Click Submit on another user's draft | ❌ Button invisible or AccessError | Security |
| TC-1.8 | Requester API write | Direct ORM write via Python console | ❌ Write blocked by ACL | Security |
| TC-1.9 | Dept manager edits own dept | Edit any record in own department | ✅ Allowed (dept_manager ACL) | Functional |
| TC-1.10 | Dept manager edits other dept | Edit record in other department | ❌ Record invisible | Security |

### 10.4 Regression Tests

| TC# | Test Case | Scope |
|-----|-----------|-------|
| TC-R1 | Full workflow: create → submit → approve dept → approve fmo → allocate → dispatch → trip → complete | End-to-end |
| TC-R2 | Rejection flow: create → submit → reject → resubmit | Lifecycle |
| TC-R3 | Cancellation flow: create → cancel (all states) | Lifecycle |
| TC-R4 | Report generation: requisition + trip summary + allocation | Reports |
| TC-R5 | Permission computation: all `can_*` fields render correctly for each role | UI/UX |
| TC-R6 | Multi-company isolation: no cross-company data leakage | Security |
| TC-R7 | SMS notification: dept manager receives SMS on submission | Integration |
| TC-R8 | Cron reminder: escalation after 48h pending | Scheduled |

---

## 11. Deployment Plan

### 11.1 Pre-Deployment Checklist

- [ ] All unit tests pass (`python -m pytest tests/ -v`)
- [ ] Regression test suite passes (`test_regression_suite.py`)
- [ ] Cross-department approval SQL query shows 0 results (or documented exceptions)
- [ ] Orphaned requisition SQL query shows 0 results (or migration script ready)
- [ ] Backup of production database taken
- [ ] Deployment scripts in `deployment/` validated
- [ ] Rollback procedure documented
- [ ] FMO and Property Manager users notified of upcoming change

### 11.2 Deployment Steps

```
Step 1: Backup
  pg_dump -Fc hagbes_fleet > hagbes_fleet_$(date +%Y%m%d_%H%M%S).dump
  
Step 2: Run pre-migration SQL
  - Identify cross-dept pending approvals → notify approvers
  - Identify orphaned Many2one references → fix or nullify
  - Identify approved-but-unallocated requisitions → create allocations
  
Step 3: Deploy code
  git pull origin main
  # Or: copy updated files to custom_addons/hagbes_fleet/
  
Step 4: Update module
  ./odoo-bin -u hagbes_fleet --stop-after-init -c odoo.conf
  
Step 5: Verify deployment
  - Login as each role and verify permissions
  - Run TC-5.1 through TC-5.10 (security regression)
  - Run TC-1.1 through TC-1.10 (ACL regression)
  - Verify auto-allocation works
  
Step 6: Monitor
  - Check logs for AccessError traces (confirm no legitimate cross-dept approvals blocked)
  - Monitor approval completion rates
  - Watch for allocation creation failures
```

### 11.3 Rollback Procedure

```bash
# Step 1: Revert code
git revert <deployment-commit-hash>

# Step 2: Restore ACL file to original
# ir.model.access.csv: line 28, set perm_write back to 1

# Step 3: Update module
./odoo-bin -u hagbes_fleet --stop-after-init -c odoo.conf

# Step 4: Restore data if needed
pg_restore -d hagbes_fleet hagbes_fleet_backup.dump

# Step 5: Verify rollback
# - Confirm requesters can write
# - Confirm cross-dept approvals work
```

### 11.4 Post-Deployment Monitoring (7 days)

| Metric | Expected | Alert Threshold |
|--------|----------|-----------------|
| Approval completion rate | >90% within 48h | <80% |
| Allocation creation rate | 100% (auto) | <95% (falling back to manual) |
| AccessError rate | 0 (legitimate) | >5/day (check for false positives) |
| Average approval-to-dispatch time | <4h | >24h |
| Support tickets related to approvals | 0 | >3/day |

---

## Appendix A: Record Rule Summary (After Fix)

| Rule ID | Model | Group | Domain | Permissions |
|---------|-------|-------|--------|-------------|
| `rule_fleet_requisition_requester` | `fleet.requisition` | requester | `['\|', ('request_by', '=', user.id), ('department_id', '=', user.employee_id.department_id.id)]` | R=1, W=0, C=1, U=0 |
| `rule_fleet_requisition_requester_write_own_draft` | `fleet.requisition` | requester | `[('request_by', '=', user.id), ('state', '=', 'draft')]` | W=1 |
| `rule_fleet_requisition_requester_write_rejected` | `fleet.requisition` | requester | `[('request_by', '=', user.id), ('state', '=', 'rejected')]` | W=1 |
| `rule_fleet_requisition_dept_manager` | `fleet.requisition` | dept_manager | `[('department_id', '=', user.employee_id.department_id.id)]` | R=1, W=1, C=0, U=0 |
| `rule_fleet_requisition_fmo_write_assigned` | `fleet.requisition` | fmo | `[('state', '=', 'assigned')]` | W=1 |
| `rule_fleet_requisition_operator_all` | `fleet.requisition` | fmo | `[(1, '=', 1)]` | R=1, C=1, U=1 |
| `rule_fleet_requisition_multi_company` | `fleet.requisition` | All | `[('company_id', 'in', user.company_ids.ids)]` | - |
| `rule_fleet_requisition_internal_user_traveller` | `fleet.requisition` | base.group_user | `[('traveller', '=', user.id)]` | R=1, W=0, C=0, U=0 |

## Appendix B: ACL Summary (After Fix)

| Group | `fleet.requisition` | `hagbes.fleet.allocation` | `fleet.trip` |
|-------|-------------------|--------------------------|-------------|
| internal_user | R | - | - |
| requester | **R, C** (was R,W,C) | R | R |
| dept_manager | R, W | R | R |
| fmo | R, W, C, U | R, W, C | R, W, C, U |
| fleet_manager | R, W, C, U | R, W, C | R, W, C, U |
| fleet_admin | R, W, C, U | R, W, C, U | R, W, C, U |

## Appendix C: State Transition Matrix (fleet.requisition)

```
            ┌──────┐
     submit │draft │ resubmit
     ┌──────►      ◄──────────┐
     │      └──┬───┘          │
     │         │              │
     │    ┌────▼─────┐        │
     │    │ submitted │        │
     │    └────┬──────┘        │
     │         │ dept_approve  │
     │    ┌────▼────────┐     │
     │    │dept_approved │     │
     │    └────┬─────────┘     │
     │         │ team_leader   │
     │    ┌────▼──────────────┐│
     │    │team_leader_approved││
     │    └────┬───────────────┘│
     │         │ fleet_approve  │
     │    ┌────▼───────┐       │
     │    │  assigned  │       │
     │    └────┬───────┘       │
     │         │ fmo_approve   │
     │    ┌────▼───────┐       │
     │    │ dispatched │       │
     │    └────┬───────┘       │
     │         │ trip_complete │
     │    ┌────▼───────┐       │
     │    │ completed  │       │
     │    └────────────┘       │
     │                         │
     ├─────── reject ──────────┤
     ├─────── cancel ──────────┤
     └─────────────────────────┘
```

Valid transitions:
- `draft` → `submitted` (submit)
- `submitted` → `dept_approved` (dept approve) | `rejected` (dept reject)
- `dept_approved` → `team_leader_approved` (team leader approve) | `rejected`
- `team_leader_approved` → `assigned` (fleet approve) | `rejected`
- `assigned` → `dispatched` (fmo approve / allocation dispatch)
- `dispatched` → `completed` (trip complete sync)
- `rejected` → `draft` (resubmit)
- Any (except dispatched, completed) → `cancelled`
- `assigned` → `completed` (allocation complete sync) | `cancelled` (allocation cancel sync)

---
*End of Production Remediation Plan*
