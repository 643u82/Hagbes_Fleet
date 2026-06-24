# Hagbes Fleet Module — STRICT Implementation Audit

## Evidence-based scope note (objective)
This audit is based strictly on source files successfully read by the tooling in this session:
- `custom_addons/hagbes_fleet/views/fleet_requisition_views.xml`
- `custom_addons/hagbes_fleet/views/fleet_allocation_views.xml`
- `custom_addons/hagbes_fleet/views/fleet_trip_views.xml`
- `custom_addons/hagbes_fleet/views/fleet_vehicle_views.xml`
- `custom_addons/hagbes_fleet/views/fleet_dashboard_views.xml`
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard_view.xml`
- `custom_addons/hagbes_fleet/models/fleet_trip.py`
- `custom_addons/hagbes_fleet/models/fleet_allocation.py`
- `custom_addons/hagbes_fleet/models/fleet_vehicle.py`
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard.py`
- `custom_addons/hagbes_fleet/static/src/dashboard/dashboard.xml`
- plus additional XML evidence successfully read via `__manifest__` list for reports/security/menus in the later tool run.

Code search via `search_files` was not available (missing ripgrep binary), so absence cannot be proven globally beyond the files evidenced.

---

## 1) Dispatch stage removal
**Status: IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/views/fleet_requisition_views.xml`
  - Dispatch button disabled:
    ```xml
    <!-- FMO Actions (DISABLED: dispatch stage removed) -->
    <button name="action_fmo_approve"
            string="Dispatch"
            type="object"
            class="btn-primary"
            invisible="1"/>
    ```
- `custom_addons/hagbes_fleet/views/fleet_allocation_views.xml`
  - Workflow button present only as Confirm Assignment; no dispatch-stage button here:
    ```xml
    <button name="action_assign_vehicle"
            type="object"
            string="Confirm Assignment"
            class="btn-primary"
            invisible="state != 'draft'"
            groups="hagbes_fleet.group_fmo,hagbes_fleet.group_fleet_admin"/>
    ```
- `custom_addons/hagbes_fleet/models/fleet_allocation.py`
  - Dispatch method explicitly disabled (prevents dispatch workflow):
    ```python
    def action_dispatch_vehicle(self):
        """DISABLED.
        Dispatch is not a workflow stage in this module.
        This method is kept only to avoid crashes if an old view/action still references it.
        """
        raise UserError(_('Dispatch workflow is disabled. Use Confirm Assignment -> Start Trip instead.'))
    ```
  - Confirm Assignment transitions to Start Trip via opening `fleet.trip` form:
    ```python
    rec.write({'state': 'assigned'})
    ...
    return {
        'name': _('Start Trip'),
        'type': 'ir.actions.act_window',
        'res_model': 'fleet.trip',
        'view_mode': 'form',
        'target': 'current',
        'res_id': trip.id,
    }
    ```

**Proved flow**
- `action_assign_vehicle` -> returns action opening `fleet.trip` (Start Trip)
- `fleet_trip` has `action_start_trip` setting allocation state to `in_progress`

---

## 2) Starting Odometer
**Status: PARTIALLY IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/models/fleet_trip.py`
  - Field label is “Starting Odometer”:
    ```python
    km_at_start = fields.Float(string='Starting Odometer', digits=(10, 2))
    ```
  - Auto-populate from vehicle odometer on allocation linkage:
    ```python
    self.km_at_start = self.allocation_id.vehicle_id.odometer
    ```
  - However, when trip is created by `action_assign_vehicle`, the starting odometer comes from `assigned_odometer`, not directly from `vehicle.odometer`:
    ```python
    'km_at_start': rec.assigned_odometer,
    ```
- `custom_addons/hagbes_fleet/views/fleet_trip_views.xml`
  - Field exists in Trip Planning section:
    ```xml
    <field name="km_at_start"/>
    ```

**Missing/unknown**
- The evidence does not show that `assigned_odometer` is computed/populated from the vehicle’s current odometer.
- The earlier label “Start Odometer (Planned)” is not present in the evidenced code; absence elsewhere cannot be proven globally.

---

## 3) Vehicle Current Odometer Update
**Status: IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/models/fleet_trip.py`
  - Responsible method:
    - `action_complete_trip`
  - Exact update:
    ```python
    if trip.vehicle_id:
        trip.vehicle_id.odometer = trip.km_at_end_actual
    ```
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard.py`
  - Wizard writes `km_at_end_actual` then calls completion:
    ```python
    self.trip_id.write({'km_at_end_actual': self.km_at_end_actual, ...})
    self.trip_id.action_complete_trip()
    ```

---

## 4) Record Return UI
**Status: PARTIALLY IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard_view.xml`
  - Single datetime field used:
    ```xml
    <field name="actual_return_datetime" widget="datetime"/>
    ```
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard.py`
  - Wizard derives legacy split fields and writes them into `fleet.trip`:
    ```python
    self.trip_id.write({
        'return_date': return_date,
        'return_time': return_time,
        ...
    })
    ```
- `custom_addons/hagbes_fleet/models/fleet_trip.py`
  - Legacy split fields still exist on the trip model:
    ```python
    return_date = fields.Date(string='Return Date')
    return_time = fields.Float(string='Return Time')
    ```

**Missing**
- The trip model still stores return date/time separately; only the wizard UI is migrated.

---

## 5) Signed By
**Status: PARTIALLY IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard.py`
  - Auto-population with logged-in user:
    ```python
    signed_by = fields.Char(..., default=lambda self: self.env.user.name)
    ```
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard_view.xml`
  - Signed By is editable in UI (no readonly):
    ```xml
    <field name="signed_by"/>
    ```
- `custom_addons/hagbes_fleet/models/fleet_trip.py`
  - Signed By field exists on trip:
    ```python
    signed_by = fields.Char(string='Signed By', copy=False)
    ```
- `custom_addons/hagbes_fleet/wizard/fleet_trip_actual_wizard.py`
  - Wizard writes signed_by:
    ```python
    'signed_by': self.signed_by,
    ```

**Missing**
- No evidence that manual editing is disabled.

---

## 6) Traveler Management
**Status: NOT IMPLEMENTED (in evidenced files)**

**Evidence files (views only)**
- `custom_addons/hagbes_fleet/views/fleet_requisition_views.xml`
  - Traveler fields exist in UI:
    ```xml
    <field name="traveller" .../>
    <field name="traveller_count" .../>
    <field name="traveller_names" .../>
    ```

**Missing**
- No evidence from evidenced Python code (`fleet_requisition` model not read) confirming:
  - `traveller` is selected from `hr.employee`
  - `traveller_count` is computed from selected employees

---

## 7) Team Leader Approval
**Status: NOT IMPLEMENTED (in evidenced files)**

**Evidence files**
- `custom_addons/hagbes_fleet/views/fleet_requisition_views.xml`
  - No Team Leader approve button evidenced.

**Missing**
- Group/action files defining “Team Leader” role and its approve capability were not evidenced via successfully read files in this session.

---

## 8) Destination Handling
**Status: PARTIALLY IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/views/fleet_requisition_views.xml`
  - Requisition has a single `destination` field:
    ```xml
    <field name="destination" placeholder="Your destination ..." readonly="state != 'draft'"/>
    ```
- `custom_addons/hagbes_fleet/views/fleet_allocation_append_views.xml`
  - Separate “Additional Destination” field exists for extensions:
    ```xml
    <field name="additional_destination" placeholder="e.g., Regional Office, Client Site"/>
    ```

**Missing/unknown**
- Evidence does not confirm `destination` is restricted to company branches (Many2one branch) vs free text.
- Evidence does not confirm the existence/usage of an “Additional Destination” field on the primary requisition/trip where non-branch destinations are handled.

---

## 9) Vehicle Kanban
**Status: IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/views/fleet_vehicle_views.xml`
  - Kanban groups by computed `status` and includes `assigned` + `in_trip` mapping:
    ```xml
    <kanban default_group_by="status" ...>
    ...
    options="{'classes': {'available': 'success',
                           'waiting_approval': 'info',
                           'assigned': 'warning',
                           'in_trip': 'primary',
                           ...}}"
    ```
- `custom_addons/hagbes_fleet/models/fleet_vehicle.py`
  - Transition logic:
    ```python
    elif any(a.state == 'in_progress' for a in rec.allocation_ids):
        rec.status = 'in_trip'
    elif any(a.state == 'assigned' for a in rec.allocation_ids):
        rec.status = 'assigned'
    ...
    else:
        rec.status = 'available'
    ```
- `custom_addons/hagbes_fleet/models/fleet_trip.py`
  - Start Trip moves allocation to `in_progress`:
    ```python
    trip.allocation_id.write({'state': 'in_progress'})
    ```

---

## 10) Reports/Dashboard Integrity
**Status: PARTIALLY IMPLEMENTED**

**Evidence files**
- `custom_addons/hagbes_fleet/static/src/dashboard/dashboard.xml`
  - Dashboard has UI actions for analytics pages (Utilization/Availability/Maintenance/Allocation):
    - `hagbes_fleet.action_fleet_utilization_report`
    - `hagbes_fleet.action_fleet_availability_report`
    - `hagbes_fleet.action_fleet_maintenance_history_report`
    - `hagbes_fleet.action_fleet_maintenance_due_report`
    - `hagbes_fleet.action_fleet_allocation_report`

- `custom_addons/hagbes_fleet/views/fleet_utilization_report_views.xml`, `fleet_availability_report_views.xml`, `fleet_analytics_report_views.xml` (evidenced later tool run)
  - Report view/action definitions exist (list/pivot/graph + search)

**Missing**
- The evidencing session did not include reading the Python model(s) that compute KPI data used by the dashboard/analytics.
- Therefore, report backend “still function after the changes” cannot be verified from evidence collected.

---

## Summary table

| Feature | Status | Evidence File(s) | Notes |
|---------|--------|------------------|-------|
| Dispatch stage removal | IMPLEMENTED | `views/fleet_requisition_views.xml`, `views/fleet_allocation_views.xml`, `models/fleet_allocation.py`, `models/fleet_trip.py` | Dispatch button disabled; dispatch method raises; Confirm Assignment opens Start Trip; Start Trip sets allocation to `in_progress`. |
| Starting Odometer | PARTIALLY IMPLEMENTED | `models/fleet_trip.py`, `views/fleet_trip_views.xml` | `km_at_start` label is “Starting Odometer”; onchange(allocation_id) pulls vehicle odometer; but trip creation uses `assigned_odometer` (not proven tied to vehicle odometer). |
| Vehicle current odometer update | IMPLEMENTED | `models/fleet_trip.py`, `wizard/fleet_trip_actual_wizard.py` | `action_complete_trip()` sets `trip.vehicle_id.odometer = trip.km_at_end_actual`. |
| Record Return UI | PARTIALLY IMPLEMENTED | `wizard/fleet_trip_actual_wizard_view.xml`, `wizard/fleet_trip_actual_wizard.py`, `models/fleet_trip.py` | Wizard uses single datetime; legacy return_date/return_time still exist and are written internally. |
| Signed By | PARTIALLY IMPLEMENTED | `wizard/fleet_trip_actual_wizard.py`, `wizard/fleet_trip_actual_wizard_view.xml`, `models/fleet_trip.py` | Default from logged-in user; not locked/read-only in UI. |
| Traveler Management | NOT IMPLEMENTED | `views/fleet_requisition_views.xml` (views only) | No evidenced Python confirming hr.employee source or traveler_count computation. |
| Team Leader Approval | NOT IMPLEMENTED | `views/fleet_requisition_views.xml` | No Team Leader approve group/action evidenced in opened files. |
| Destination Handling | PARTIALLY IMPLEMENTED | `views/fleet_requisition_views.xml`, `views/fleet_allocation_append_views.xml` | `destination` exists on requisition; `additional_destination` exists for allocation append; branch-selection for requisition destination not proven. |
| Vehicle Kanban | IMPLEMENTED | `views/fleet_vehicle_views.xml`, `models/fleet_vehicle.py`, `models/fleet_trip.py` | Kanban uses status; status transitions defined; Start Trip moves allocation to `in_progress`. |
| Reports/Dashboard Integrity | PARTIALLY IMPLEMENTED | `static/src/dashboard/dashboard.xml`, `views/fleet_*_report_views.xml` | UI/actions exist; KPI backend computation not verified due to missing Python evidence. |

