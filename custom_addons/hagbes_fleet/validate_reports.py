import sqlite3
import re

def validate_reports():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 1. Create Base Tables
    cursor.execute("""
    CREATE TABLE hagbes_fleet_vehicle (
        id INTEGER PRIMARY KEY, name TEXT, plate_number TEXT, brand TEXT, model TEXT,
        engine_number TEXT, chassis_number TEXT, fuel_type TEXT, acquisition_date TEXT,
        cost REAL, vehicle_type TEXT, company_id INTEGER, status TEXT
    )""")
    cursor.execute("""
    CREATE TABLE fleet_requisition (
        id INTEGER PRIMARY KEY, name TEXT, date_of_request TEXT, request_by INTEGER,
        department_id INTEGER, company_id INTEGER, date_from TEXT, date_to TEXT,
        purpose TEXT, traveller_count TEXT, destination TEXT, state TEXT
    )""")
    cursor.execute("""
    CREATE TABLE hagbes_fleet_allocation (
        id INTEGER PRIMARY KEY, name TEXT, request_id INTEGER, vehicle_id INTEGER,
        driver_id INTEGER, company_id INTEGER, allocation_date TEXT, state TEXT,
        planned_distance REAL, active_allocations INTEGER
    )""")
    cursor.execute("""
    CREATE TABLE fleet_trip (
        id INTEGER PRIMARY KEY, name TEXT, vehicle_id INTEGER, allocation_id INTEGER,
        company_id INTEGER, km_at_start_actual REAL, km_at_end_actual REAL,
        actual_distance REAL, return_date TEXT, state TEXT
    )""")
    cursor.execute("""
    CREATE TABLE hagbes_fleet_maintenance (
        id INTEGER PRIMARY KEY, vehicle_id INTEGER, company_id INTEGER,
        service_type TEXT, service_date TEXT, cost REAL, state TEXT
    )""")

    # 2. Load UAT Data
    with open('fleet_uat_data.sql', 'r') as f:
        sql_content = f.read()
        # Filter only INSERT statements
        inserts = [line for line in sql_content.split('\n') if line.strip().startswith('INSERT')]
        for cmd in inserts:
            cursor.execute(cmd)

    # 3. Create Views (Adapted for SQLite)
    
    # Fleet Utilization View
    cursor.execute("""
    CREATE VIEW fleet_utilization_report AS
    SELECT 
        v.id as id,
        v.id as vehicle_id,
        v.plate_number as plate_number,
        v.company_id as company_id,
        v.status as vehicle_status,
        COUNT(t.id) as trip_count,
        SUM(COALESCE(t.actual_distance, 0)) as total_distance,
        CASE 
            WHEN COUNT(t.id) > 0 THEN SUM(COALESCE(t.actual_distance, 0)) / COUNT(t.id)
            ELSE 0 
        END as avg_distance,
        MAX(t.return_date) as last_trip_date,
        MAX(COALESCE(t.km_at_end_actual, 0)) as odometer,
        ls.last_service_date,
        MAX(CASE 
            WHEN ls.last_service_date IS NOT NULL AND t.return_date <= ls.last_service_date 
            THEN COALESCE(t.km_at_end_actual, 0) 
            ELSE 0 
        END) as last_service_km,
        SUM(CASE 
            WHEN ls.last_service_date IS NULL OR t.return_date > ls.last_service_date 
            THEN COALESCE(t.actual_distance, 0) 
            ELSE 0 
        END) as wear_since_service
    FROM 
        hagbes_fleet_vehicle v
    LEFT JOIN 
        fleet_trip t ON v.id = t.vehicle_id AND t.state = 'completed'
    LEFT JOIN (
        SELECT vehicle_id, MAX(service_date) as last_service_date
        FROM hagbes_fleet_maintenance
        WHERE state = 'completed'
        GROUP BY vehicle_id
    ) ls ON v.id = ls.vehicle_id
    GROUP BY 
        v.id, v.plate_number, v.company_id, v.status, ls.last_service_date
    """)

    # Maintenance History View
    cursor.execute("""
    CREATE VIEW fleet_maintenance_history_report AS
    SELECT 
        MIN(m.id) as id,
        m.vehicle_id as vehicle_id,
        m.company_id as company_id,
        m.service_type as service_type,
        m.service_date as service_date,
        m.state as state,
        COUNT(m.id) as maintenance_count,
        SUM(COALESCE(m.cost, 0)) as total_cost,
        AVG(COALESCE(m.cost, 0)) as avg_cost,
        MIN(m.service_date) as first_service_date,
        MAX(m.service_date) as last_service_date
    FROM 
        hagbes_fleet_maintenance m
    GROUP BY 
        m.vehicle_id, m.company_id, m.service_type, m.service_date, m.state
    """)

    # Allocation Report View
    cursor.execute("""
    CREATE VIEW fleet_allocation_report AS
    SELECT 
        MIN(a.id) as id,
        a.vehicle_id as vehicle_id,
        a.company_id as company_id,
        a.driver_id as driver_id,
        COUNT(a.id) as allocation_count,
        SUM(CASE WHEN a.state IN ('assigned', 'dispatched', 'in_progress') THEN 1 ELSE 0 END) as active_allocations,
        SUM(COALESCE(a.planned_distance, 0)) as total_planned_distance,
        AVG(COALESCE(a.planned_distance, 0)) as avg_planned_distance,
        MIN(a.allocation_date) as first_allocation_date,
        MAX(a.allocation_date) as last_allocation_date
    FROM 
        hagbes_fleet_allocation a
    GROUP BY 
        a.vehicle_id, a.company_id, a.driver_id
    """)

    # Maintenance Due View
    cursor.execute("""
    CREATE VIEW fleet_maintenance_due_report AS
    WITH latest_service_km AS (
        SELECT 
            m.vehicle_id,
            MAX(COALESCE(t.km_at_end_actual, 0)) AS service_km
        FROM hagbes_fleet_maintenance m
        LEFT JOIN fleet_trip t ON m.vehicle_id = t.vehicle_id AND t.state = 'completed' AND t.return_date <= m.service_date
        WHERE m.state = 'completed'
        GROUP BY m.vehicle_id
    )
    SELECT 
        vh.vehicle_id AS id,
        vh.vehicle_id,
        vh.company_id,
        vh.total_distance AS current_odometer,
        vh.last_service_date,
        COALESCE(lsk.service_km, 0) AS last_service_km,
        vh.wear_since_service,
        90 as days_since_service, -- Placeholder
        vh.total_distance - COALESCE(lsk.service_km, 0) as km_since_service,
        'normal' as due_status -- Placeholder
    FROM fleet_utilization_report vh
    LEFT JOIN latest_service_km lsk ON vh.vehicle_id = lsk.vehicle_id
    """)

    # Dashboard View
    cursor.execute("""
    CREATE VIEW fleet_dashboard AS
    WITH vehicle_counts AS (
        SELECT 
            COUNT(id) AS total_vehicles,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available_vehicles,
            SUM(CASE WHEN status = 'assigned' THEN 1 ELSE 0 END) AS allocated_vehicles,
            SUM(CASE WHEN status = 'maintenance' THEN 1 ELSE 0 END) AS in_maintenance_vehicles,
            SUM(CASE WHEN status = 'out_of_service' THEN 1 ELSE 0 END) AS out_of_service_vehicles
        FROM hagbes_fleet_vehicle
    ),
    utilization_kpis AS (
        SELECT 
            SUM(total_distance) AS total_fleet_distance,
            AVG(avg_distance) AS average_distance,
            SUM(trip_count) AS total_trips
        FROM fleet_utilization_report
    ),
    maintenance_kpis AS (
        SELECT 
            COUNT(id) AS total_maintenance_events,
            SUM(total_cost) AS total_maintenance_cost
        FROM fleet_maintenance_history_report
    ),
    maintenance_due_kpis AS (
        SELECT 
            SUM(CASE WHEN due_status IN ('due', 'warning') THEN 1 ELSE 0 END) AS vehicles_due,
            SUM(CASE WHEN due_status = 'overdue' THEN 1 ELSE 0 END) AS vehicles_overdue
        FROM fleet_maintenance_due_report
    ),
    allocation_kpis AS (
        SELECT 
            SUM(active_allocations) AS active_allocations,
            SUM(allocation_count) AS allocation_count
        FROM fleet_allocation_report
    )
    SELECT 
        1 AS id,
        vc.total_vehicles,
        vc.available_vehicles,
        vc.allocated_vehicles,
        vc.in_maintenance_vehicles,
        vc.out_of_service_vehicles,
        COALESCE(uk.total_fleet_distance, 0) AS total_fleet_distance,
        COALESCE(uk.average_distance, 0) AS average_distance,
        COALESCE(uk.total_trips, 0) AS total_trips,
        COALESCE(mk.total_maintenance_events, 0) AS total_maintenance_events,
        COALESCE(mk.total_maintenance_cost, 0) AS total_maintenance_cost,
        COALESCE(mdk.vehicles_due, 0) AS vehicles_due,
        COALESCE(mdk.vehicles_overdue, 0) AS vehicles_overdue,
        COALESCE(ak.active_allocations, 0) AS active_allocations,
        COALESCE(ak.allocation_count, 0) AS allocation_count
    FROM vehicle_counts vc
    CROSS JOIN utilization_kpis uk
    CROSS JOIN maintenance_kpis mk
    CROSS JOIN maintenance_due_kpis mdk
    CROSS JOIN allocation_kpis ak
    """)

    print("--- VALIDATION START ---")
    
    # 1. Dashboard vs Raw Trip Data Distance Validation
    cursor.execute("SELECT total_fleet_distance FROM fleet_dashboard")
    dashboard_dist = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(actual_distance) FROM fleet_trip WHERE state = 'completed'")
    raw_dist = cursor.fetchone()[0]
    
    print(f"Dashboard Distance: {dashboard_dist:.4f}")
    print(f"Raw Trip Distance: {raw_dist:.4f}")
    print(f"MATCH: {abs(dashboard_dist - raw_dist) < 0.0001}")
    print("")

    # 2. Utilization Report Validation (5 random vehicles)
    print("--- UTILIZATION REPORT VALIDATION (5 RANDOM VEHICLES) ---")
    cursor.execute("SELECT vehicle_id, total_distance, odometer FROM fleet_utilization_report ORDER BY vehicle_id LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        vid, dist, odo = row
        cursor.execute(f"SELECT SUM(actual_distance), MAX(km_at_end_actual) FROM fleet_trip WHERE vehicle_id = {vid} AND state = 'completed'")
        raw = cursor.fetchone()
        print(f"Vehicle {vid}: Report Dist={dist:.2f}, Raw Dist={raw[0]:.2f} | Report Odo={odo:.2f}, Raw Odo={raw[1]:.2f} | PASS: {abs(dist-raw[0]) < 0.01 and abs(odo-raw[1]) < 0.01}")

    # 3. Maintenance History Validation
    print("\n--- MAINTENANCE HISTORY VALIDATION (5 RANDOM VEHICLES) ---")
    cursor.execute("SELECT vehicle_id, total_cost, maintenance_count FROM fleet_maintenance_history_report GROUP BY vehicle_id LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        vid, cost, count = row
        cursor.execute(f"SELECT SUM(cost), COUNT(id) FROM hagbes_fleet_maintenance WHERE vehicle_id = {vid} AND state = 'completed'")
        raw = cursor.fetchone()
        print(f"Vehicle {vid}: Report Cost={cost:.2f}, Raw Cost={raw[0]:.2f} | Report Count={count}, Raw Count={raw[1]} | PASS: {abs(cost-raw[0]) < 0.01 and count == raw[1]}")

    conn.close()

if __name__ == '__main__':
    validate_reports()
