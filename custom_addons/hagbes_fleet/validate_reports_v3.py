import sqlite3

def run_validation():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # Setup Tables
    cursor.execute("CREATE TABLE hagbes_fleet_vehicle (id INTEGER, name TEXT, plate_number TEXT, brand TEXT, model TEXT, engine_number TEXT, chassis_number TEXT, fuel_type TEXT, acquisition_date TEXT, cost REAL, vehicle_type TEXT, company_id INTEGER, status TEXT, driver TEXT)")
    cursor.execute("CREATE TABLE fleet_requisition (id INTEGER, name TEXT, date_of_request TEXT, request_by INTEGER, department_id INTEGER, company_id INTEGER, date_from TEXT, date_to TEXT, purpose TEXT, traveller_count TEXT, destination TEXT, state TEXT)")
    cursor.execute("CREATE TABLE hagbes_fleet_allocation (id INTEGER, name TEXT, request_id INTEGER, vehicle_id INTEGER, driver_id INTEGER, company_id INTEGER, allocation_date TEXT, state TEXT, planned_distance REAL)")
    cursor.execute("CREATE TABLE fleet_trip (id INTEGER, name TEXT, vehicle_id INTEGER, allocation_id INTEGER, company_id INTEGER, km_at_start_actual REAL, km_at_end_actual REAL, actual_distance REAL, return_date TEXT, state TEXT)")
    cursor.execute("CREATE TABLE hagbes_fleet_maintenance (id INTEGER, vehicle_id INTEGER, company_id INTEGER, service_type TEXT, service_date TEXT, cost REAL, state TEXT)")

    # Load Data
    with open('fleet_uat_data.sql', 'r') as f:
        for line in f:
            if line.strip().startswith('INSERT'):
                # Handle missing driver column in some inserts if any
                cursor.execute(line)

    # --- VIEWS ---
    
    # Utilization
    cursor.execute("""
    CREATE VIEW fleet_utilization_report AS
    SELECT 
        v.id as vehicle_id, SUM(COALESCE(t.actual_distance, 0)) as total_distance,
        MAX(COALESCE(t.km_at_end_actual, 0)) as odometer, ls.last_service_date
    FROM hagbes_fleet_vehicle v
    LEFT JOIN fleet_trip t ON v.id = t.vehicle_id AND t.state = 'completed'
    LEFT JOIN (SELECT vehicle_id, MAX(service_date) as last_service_date FROM hagbes_fleet_maintenance WHERE state = 'completed' GROUP BY vehicle_id) ls ON v.id = ls.vehicle_id
    GROUP BY v.id
    """)

    # Availability
    cursor.execute("""
    CREATE VIEW fleet_availability_report AS
    SELECT 
        v.id as vehicle_id, 
        lt.return_date as last_trip_date,
        CASE WHEN lt.return_date IS NOT NULL THEN (julianday('now') - julianday(lt.return_date)) ELSE 999 END as days_idle
    FROM hagbes_fleet_vehicle v
    LEFT JOIN (SELECT vehicle_id, MAX(return_date) as return_date FROM fleet_trip WHERE state = 'completed' GROUP BY vehicle_id) lt ON v.id = lt.vehicle_id
    """)

    # Maintenance Due
    cursor.execute("""
    CREATE VIEW fleet_maintenance_due_report AS
    SELECT 
        v.vehicle_id, v.odometer, v.total_distance - COALESCE(lsk.service_km, 0) as km_since_service
    FROM fleet_utilization_report v
    LEFT JOIN (
        SELECT m.vehicle_id, MAX(COALESCE(t.km_at_end_actual, 0)) as service_km
        FROM hagbes_fleet_maintenance m
        LEFT JOIN fleet_trip t ON m.vehicle_id = t.vehicle_id AND t.state = 'completed' AND t.return_date <= m.service_date
        WHERE m.state = 'completed'
        GROUP BY m.vehicle_id
    ) lsk ON v.vehicle_id = lsk.vehicle_id
    """)

    print(f"{'Report':<25} | {'Metric':<30} | {'Report Output':<20} | {'SQL Calculation':<20} | {'Status'}")
    print("-" * 110)

    # 1. Availability Idle Days Check
    cursor.execute("SELECT vehicle_id, days_idle FROM fleet_availability_report LIMIT 5")
    for vid, idle in cursor.fetchall():
        cursor.execute(f"SELECT MAX(return_date) FROM fleet_trip WHERE vehicle_id={vid} AND state='completed'")
        raw_date = cursor.fetchone()[0]
        from datetime import datetime
        raw_idle = (datetime.now() - datetime.strptime(raw_date, '%Y-%m-%d')).days if raw_date else 999
        status = "PASS" if abs(idle - raw_idle) <= 1 else "FAIL"
        print(f"{'Vehicle Availability':<25} | {f'Vehicle {vid} Days Idle':<30} | {f'{idle:.1f}':<20} | {f'{raw_idle:.1f}':<20} | {status}")

    # 2. Maintenance Due KM Check
    cursor.execute("SELECT vehicle_id, km_since_service FROM fleet_maintenance_due_report LIMIT 5")
    for vid, km in cursor.fetchall():
        cursor.execute(f"SELECT MAX(COALESCE(km_at_end_actual, 0)) FROM fleet_trip WHERE vehicle_id={vid} AND state='completed'")
        current_odo = cursor.fetchone()[0] or 0
        cursor.execute(f"SELECT MAX(service_date) FROM hagbes_fleet_maintenance WHERE vehicle_id={vid} AND state='completed'")
        last_maint_date = cursor.fetchone()[0]
        if last_maint_date:
            cursor.execute(f"SELECT MAX(km_at_end_actual) FROM fleet_trip WHERE vehicle_id={vid} AND state='completed' AND return_date <= '{last_maint_date}'")
            maint_odo = cursor.fetchone()[0] or 0
        else:
            maint_odo = 0
        raw_km = current_odo - maint_odo
        status = "PASS" if abs(km - raw_km) < 0.01 else "FAIL"
        print(f"{'Maintenance Due':<25} | {f'Vehicle {vid} KM Since Svc':<30} | {f'{km:.2f}':<20} | {f'{raw_km:.2f}':<20} | {status}")

    conn.close()

if __name__ == '__main__':
    run_validation()
