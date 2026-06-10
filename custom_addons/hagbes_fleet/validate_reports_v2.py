import sqlite3

def run_validation():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # Setup Tables
    cursor.execute("CREATE TABLE hagbes_fleet_vehicle (id INTEGER, name TEXT, plate_number TEXT, brand TEXT, model TEXT, engine_number TEXT, chassis_number TEXT, fuel_type TEXT, acquisition_date TEXT, cost REAL, vehicle_type TEXT, company_id INTEGER, status TEXT)")
    cursor.execute("CREATE TABLE fleet_requisition (id INTEGER, name TEXT, date_of_request TEXT, request_by INTEGER, department_id INTEGER, company_id INTEGER, date_from TEXT, date_to TEXT, purpose TEXT, traveller_count TEXT, destination TEXT, state TEXT)")
    cursor.execute("CREATE TABLE hagbes_fleet_allocation (id INTEGER, name TEXT, request_id INTEGER, vehicle_id INTEGER, driver_id INTEGER, company_id INTEGER, allocation_date TEXT, state TEXT, planned_distance REAL)")
    cursor.execute("CREATE TABLE fleet_trip (id INTEGER, name TEXT, vehicle_id INTEGER, allocation_id INTEGER, company_id INTEGER, km_at_start_actual REAL, km_at_end_actual REAL, actual_distance REAL, return_date TEXT, state TEXT)")
    cursor.execute("CREATE TABLE hagbes_fleet_maintenance (id INTEGER, vehicle_id INTEGER, company_id INTEGER, service_type TEXT, service_date TEXT, cost REAL, state TEXT)")

    # Load Data
    with open('fleet_uat_data.sql', 'r') as f:
        for line in f:
            if line.strip().startswith('INSERT'):
                cursor.execute(line)

    # Create Views
    cursor.execute("""
    CREATE VIEW fleet_utilization_report AS
    SELECT 
        v.id as id, v.id as vehicle_id, v.plate_number, v.company_id, v.status as vehicle_status,
        COUNT(t.id) as trip_count, SUM(COALESCE(t.actual_distance, 0)) as total_distance,
        MAX(COALESCE(t.km_at_end_actual, 0)) as odometer, ls.last_service_date
    FROM hagbes_fleet_vehicle v
    LEFT JOIN fleet_trip t ON v.id = t.vehicle_id AND t.state = 'completed'
    LEFT JOIN (SELECT vehicle_id, MAX(service_date) as last_service_date FROM hagbes_fleet_maintenance WHERE state = 'completed' GROUP BY vehicle_id) ls ON v.id = ls.vehicle_id
    GROUP BY v.id
    """)

    cursor.execute("""
    CREATE VIEW fleet_maintenance_history_report AS
    SELECT vehicle_id, service_type, service_date, state, COUNT(id) as maintenance_count, SUM(cost) as total_cost
    FROM hagbes_fleet_maintenance
    GROUP BY vehicle_id, service_type, service_date, state
    """)

    cursor.execute("""
    CREATE VIEW fleet_allocation_report AS
    SELECT vehicle_id, COUNT(id) as allocation_count, SUM(CASE WHEN state IN ('assigned', 'dispatched', 'in_progress') THEN 1 ELSE 0 END) as active_allocations
    FROM hagbes_fleet_allocation
    GROUP BY vehicle_id
    """)

    cursor.execute("""
    CREATE VIEW fleet_dashboard AS
    SELECT 
        (SELECT SUM(total_distance) FROM fleet_utilization_report) as total_fleet_distance,
        (SELECT COUNT(id) FROM fleet_trip WHERE state = 'completed') as total_trips,
        (SELECT SUM(cost) FROM hagbes_fleet_maintenance WHERE state = 'completed') as total_maintenance_cost
    """)

    print(f"{'Report':<25} | {'Record':<30} | {'Report Output':<30} | {'SQL Calculation':<30} | {'Status'}")
    print("-" * 130)

    # --- REPORT 1: FLEET UTILIZATION ---
    cursor.execute("SELECT vehicle_id, total_distance, odometer FROM fleet_utilization_report LIMIT 5")
    for vid, dist, odo in cursor.fetchall():
        cursor.execute(f"SELECT SUM(actual_distance), MAX(km_at_end_actual) FROM fleet_trip WHERE vehicle_id={vid} AND state='completed'")
        raw = cursor.fetchone()
        status = "PASS" if abs(dist - (raw[0] or 0)) < 0.01 and abs(odo - (raw[1] or 0)) < 0.01 else "FAIL"
        print(f"{'Fleet Utilization':<25} | {f'Vehicle {vid}':<30} | {f'Dist:{dist:.2f}, Odo:{odo:.2f}':<30} | {f'Dist:{(raw[0] or 0):.2f}, Odo:{(raw[1] or 0):.2f}':<30} | {status}")

    # --- REPORT 3: MAINTENANCE HISTORY ---
    cursor.execute("SELECT vehicle_id, service_date, total_cost, maintenance_count FROM fleet_maintenance_history_report LIMIT 5")
    for vid, sdate, cost, count in cursor.fetchall():
        cursor.execute(f"SELECT SUM(cost), COUNT(id) FROM hagbes_fleet_maintenance WHERE vehicle_id={vid} AND service_date='{sdate}'")
        raw = cursor.fetchone()
        status = "PASS" if abs(cost - raw[0]) < 0.01 and count == raw[1] else "FAIL"
        print(f"{'Maintenance History':<25} | {f'Vehicle {vid} on {sdate}':<30} | {f'Cost:{cost:.2f}, Count:{count}':<30} | {f'Cost:{raw[0]:.2f}, Count:{raw[1]}':<30} | {status}")

    # --- REPORT 4: ALLOCATION ANALYTICS ---
    cursor.execute("SELECT vehicle_id, allocation_count, active_allocations FROM fleet_allocation_report LIMIT 5")
    for vid, count, active in cursor.fetchall():
        cursor.execute(f"SELECT COUNT(id), SUM(CASE WHEN state IN ('assigned', 'dispatched', 'in_progress') THEN 1 ELSE 0 END) FROM hagbes_fleet_allocation WHERE vehicle_id={vid}")
        raw = cursor.fetchone()
        status = "PASS" if count == raw[0] and active == raw[1] else "FAIL"
        print(f"{'Allocation Analytics':<25} | {f'Vehicle {vid}':<30} | {f'Count:{count}, Active:{active}':<30} | {f'Count:{raw[0]}, Active:{raw[1]}':<30} | {status}")

    # --- REPORT 6: FLEET DASHBOARD ---
    cursor.execute("SELECT total_fleet_distance, total_trips, total_maintenance_cost FROM fleet_dashboard")
    dash = cursor.fetchone()
    cursor.execute("SELECT SUM(actual_distance), COUNT(id) FROM fleet_trip WHERE state='completed'")
    raw_trip = cursor.fetchone()
    cursor.execute("SELECT SUM(cost) FROM hagbes_fleet_maintenance WHERE state='completed'")
    raw_maint = cursor.fetchone()
    
    status_dist = "PASS" if abs(dash[0] - raw_trip[0]) < 0.01 else "FAIL"
    print(f"{'Dashboard':<25} | {'Total Distance':<30} | {f'{dash[0]:.2f}':<30} | {f'{raw_trip[0]:.2f}':<30} | {status_dist}")
    
    status_trips = "PASS" if dash[1] == raw_trip[1] else "FAIL"
    print(f"{'Dashboard':<25} | {'Total Trips':<30} | {f'{dash[1]}':<30} | {f'{raw_trip[1]}':<30} | {status_trips}")
    
    status_cost = "PASS" if abs(dash[2] - raw_maint[0]) < 0.01 else "FAIL"
    print(f"{'Dashboard':<25} | {'Maintenance Cost':<30} | {f'{dash[2]:.2f}':<30} | {f'{raw_maint[0]:.2f}':<30} | {status_cost}")

    conn.close()

if __name__ == '__main__':
    run_validation()
