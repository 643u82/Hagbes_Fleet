# Critical Issues Verification Report

**Date:** June 5, 2026  
**Purpose:** Evidence-based validation of all 8 critical issues  
**Method:** Direct code inspection with line numbers and snippets

---

## CRIT-001: Requester Cannot Submit Own Requisitions

### ✅ STATUS: **CONFIRMED**

### Evidence 1: ACL Permissions
**File:** `security/ir.model.access.csv`  
**Line:** 23

```csv
access_fleet_requisition_internal_user,fleet.requisition.internal.user,model_fleet_requisition,base.group_user,1,0,0,0
```

**Analysis:**
- Columns: `id, name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink`
- For `base.group_user` (internal users): `1,0,0,0` = READ only
- No WRITE permission (column 5 = 0)

### Evidence 2: Requester Group Has Write
**File:** `security/ir.model.access.csv`  
**Line:** 24

```csv
access_fleet_requisition_requester,fleet.requisition.requester,model_fleet_requisition,hagbes_fleet.group_fleet_requester,1,1,1,0
```

**Analysis:**
- For `hagbes_fleet.group_fleet_requester`: `1,1,1,0` = READ, WRITE, CREATE
- BUT: requester group is implied by base.group_user, not directly assigned

### Evidence 3: Submit Action Requires Write
**File:** `models/fleet_requisition.py`  
**Lines:** 685-706

```python
def action_submit(self):
    """Requester submits a draft requisition for department approval."""
    for rec in self:
        if rec.state != 'draft':
            raise UserError(_('Only draft requests can be submitted.'))
        
        # ... validation code ...
        
        rec.sudo()._trigger_approval()  # Line 703 - NEEDS WRITE TO CHANGE STATE
        rec.message_post(body=_('Request submitted for approval.'))
```

