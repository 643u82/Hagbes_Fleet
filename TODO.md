# TODO - Fleet workflow & UI restoration

## Step 1: Restore assignment → confirm → start trip workflow
- Inspect allocation + trip buttons/actions.
- Remove intermediate dispatch/open allocation steps from UI flow (ensure Confirm Assignment proceeds to Confirm Assignment then Start Trip).
- Keep existing business logic intact; avoid changing approval/security.

## Step 2: Manual starting odometer
- Remove any onchange/prefill logic for starting odometer in trip planning views/models.
- Ensure Starting odometer fields are blank at creation and only entered manually.

## Step 3: Update vehicle odometer only after trip completion
- Ensure vehicle.odometer is updated only in Trip action_complete_trip.
- Ensure cancel/draft/reject do not modify odometer.
- Ensure update uses km_at_end_actual from Record Return (not planned distance).
- Validate ending >= starting.

## Step 4: Replace return date/time with a single datetime picker
- Update wizard model: remove return_date/return_time fields exposed in UI.
- Add actual_return_datetime (Datetime widget) and internal mapping.
- Prevent invalid manual decimal inputs in time.
- Update wizard view and trip model write logic.

## Step 5: Improve return wizard terminology
- Ensure labels use Trip Origin and Final Destination.
- Align both wizard view and trip field labels.

## Step 6: Add Assigned column to vehicle kanban with transitions
- Confirm vehicle model already has status groups and kanban uses status.
- Update computed status transitions to include Assigned appropriately.
- Ensure status changes on allocation confirmation/cancel and trip start/complete.

## Step 7: Validation
- Run automated tests (if any) and/or do manual checks in UI:
  - Confirm assignment requires vehicle.
  - Starting odometer manually entered only.
  - Record Return uses single datetime.
  - Vehicle odometer updated after completion only.
  - Kanban transitions.
  - No regression in approvals/reports.

