# TODO - Destination management improvements (Hagbes Fleet)

## Step 1: Gather & confirm model/view touch points
- [x] Reviewed `fleet.requisition` model (existing `destination` Char field).
- [x] Reviewed `fleet.trip` model (computed `combined_destination` uses requisition `destination`).
- [x] Reviewed `fleet.requisition` views (destination field shown in form/tree/kanban/search).
- [x] Reviewed allocation/trip planning views & trip actual wizard (no destination fields found beyond requisition/trip fields).

## Step 2: Implement new destination fields in `fleet.requisition`
- [ ] Add `destination_branch_id` (M2O) linking to registered company branches.
- [ ] Keep legacy `destination` Char for backward compatibility, mapping it from the selected branch + additional destination.
- [ ] Add `additional_destination` Char for non-branch locations.
- [ ] Ensure onchange + create/write sync keeps `destination` populated.
- [ ] Add validation: destination_branch_id required when additional_destination empty (or keep existing required destination semantics).

## Step 3: Ensure trip planning, approvals, reports, analytics remain functional
- [ ] Ensure `fleet.trip` still reads `requisition.destination` for `start_location`/combined destination.
- [ ] Ensure `_check_no_duplicate` and other constraints referencing `destination` do not break (likely none).
- [ ] Ensure ACL/workflow edit restrictions allow editing new destination fields after submission if existing `destination` was editable.

## Step 4: Update XML views for selection UX
- [ ] Update `fleet_requisition_views.xml` form/tree/kanban/search to show branch selection + additional destination.
- [ ] Maintain display of legacy `destination` or compute it invisibly.

## Step 5: Backward compatibility & data migration behavior
- [ ] Ensure existing records keep working without manual migration: when `destination` Char already filled, infer best matching branch if possible; otherwise leave branch empty and store `additional_destination`.

## Step 6: Testing checklist
- [ ] Create new requisition with branch-only destination.
- [ ] Create requisition with additional non-branch destination.
- [ ] Submit/approve flow and verify operational allocation/trip creation.
- [ ] Generate reports/analytics that rely on `fleet.trip.combined_destination` and requisition `destination`.

