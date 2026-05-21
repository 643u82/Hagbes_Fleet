# Refactor Approval User Access UI - TODO Steps

## Approved Plan Steps:
1. [ ] Create models/res_users_approval.py (res.users extension with approval_step_ids computed).
2. [x] Create views/res_users_approval_views.xml (inherit base.view_users_form, add Approval Roles tab).\n3. [x] Edit models/__init__.py (add from . import res_users_approval).\n4. [x] Edit __manifest__.py (add new view to data[]).
5. [ ] Upgrade module & test.

Progress tracked here.
