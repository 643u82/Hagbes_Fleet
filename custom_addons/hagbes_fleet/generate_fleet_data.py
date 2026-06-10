import random
from datetime import datetime, timedelta

# Configuration
NUM_VEHICLES = 30
NUM_TRIPS = 1000
NUM_ALLOCATIONS = 300
NUM_MAINTENANCE = 150
NUM_REQUISITIONS = 50

# Metadata
BRANDS = ['Toyota', 'Ford', 'Isuzu', 'Mitsubishi', 'Volkswagen']
MODELS = {
    'Toyota': ['Hilux', 'Land Cruiser', 'Corolla'],
    'Ford': ['Ranger', 'Everest', 'Transit'],
    'Isuzu': ['D-Max', 'NPR', 'FSR'],
    'Mitsubishi': ['L200', 'Pajero', 'Canter'],
    'Volkswagen': ['Amarok', 'Crafter', 'Transporter']
}
FUEL_TYPES = ['petrol', 'diesel']
VEHICLE_TYPES = ['work', 'managerial']
DEPARTMENTS = [1, 2, 3, 4, 5]
DRIVERS = list(range(1, 21))
USERS = list(range(1, 11))
COMPANY_ID = 1

def generate_sql():
    sql = []
    
    # 1. Generate Vehicles
    vehicles = []
    for i in range(1, NUM_VEHICLES + 1):
        brand = random.choice(BRANDS)
        model = random.choice(MODELS[brand])
        plate = f"AA-{random.randint(100, 999)}-B{i}"
        engine = f"ENG-{random.randint(100000, 999999)}"
        chassis = f"CHS-{random.randint(100000, 999999)}"
        fuel = random.choice(FUEL_TYPES)
        v_type = random.choice(VEHICLE_TYPES)
        acquisition = (datetime.now() - timedelta(days=random.randint(365, 1825))).strftime('%Y-%m-%d')
        cost = random.randint(30000, 80000)
        
        vehicles.append({
            'id': i,
            'name': f"{brand} {model}",
            'plate_number': plate,
            'brand': brand,
            'model': model,
            'engine_number': engine,
            'chassis_number': chassis,
            'fuel_type': fuel,
            'acquisition_date': acquisition,
            'cost': cost,
            'vehicle_type': v_type,
            'odometer': 0.0,
            'company_id': COMPANY_ID
        })
        
        sql.append(f"INSERT INTO hagbes_fleet_vehicle (id, name, plate_number, brand, model, engine_number, chassis_number, fuel_type, acquisition_date, cost, vehicle_type, company_id, status) VALUES ({i}, '{brand} {model}', '{plate}', '{brand}', '{model}', '{engine}', '{chassis}', '{fuel}', '{acquisition}', {cost}, '{v_type}', {COMPANY_ID}, 'available');")

    # 2. Generate Requisitions
    requisitions = []
    for i in range(1, NUM_REQUISITIONS + 1):
        user = random.choice(USERS)
        dept = random.choice(DEPARTMENTS)
        date_req = (datetime.now() - timedelta(days=random.randint(1, 180))).strftime('%Y-%m-%d')
        date_from = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d %H:%M:%S')
        date_to = (datetime.now() + timedelta(days=random.randint(1, 5))).strftime('%Y-%m-%d %H:%M:%S')
        state = random.choice(['draft', 'submitted', 'dept_approved', 'assigned', 'completed'])
        
        requisitions.append({
            'id': i,
            'state': state
        })
        
        sql.append(f"INSERT INTO fleet_requisition (id, name, date_of_request, request_by, department_id, company_id, date_from, date_to, purpose, traveller_count, destination, state) VALUES ({i}, 'REQ/{i:05}', '{date_req}', {user}, {dept}, {COMPANY_ID}, '{date_from}', '{date_to}', 'Business Trip {i}', '1', 'Destination {i}', '{state}');")

    # 3. Generate Allocations
    allocations = []
    active_allocations = 0
    for i in range(1, NUM_ALLOCATIONS + 1):
        vehicle = random.choice(vehicles)
        req = random.choice(requisitions)
        driver = random.choice(DRIVERS)
        date_alloc = (datetime.now() - timedelta(days=random.randint(1, 180))).strftime('%Y-%m-%d %H:%M:%S')
        state = random.choice(['draft', 'assigned', 'completed', 'dispatched', 'in_progress'])
        if state in ['assigned', 'dispatched', 'in_progress']:
            active_allocations += 1
        
        allocations.append({
            'id': i,
            'vehicle_id': vehicle['id'],
            'driver_id': driver,
            'state': state
        })
        
        sql.append(f"INSERT INTO hagbes_fleet_allocation (id, name, request_id, vehicle_id, driver_id, company_id, allocation_date, state) VALUES ({i}, 'ALC/{i:05}', {req['id']}, {vehicle['id']}, {driver}, {COMPANY_ID}, '{date_alloc}', '{state}');")

    # 4. Generate Trips
    vehicle_odometers = {v['id']: 0.0 for v in vehicles}
    total_dist = 0
    for i in range(1, NUM_TRIPS + 1):
        vehicle_id = random.choice(range(1, NUM_VEHICLES + 1))
        alloc = random.choice(allocations)
        
        dist = random.uniform(20, 300)
        km_start = vehicle_odometers[vehicle_id]
        km_end = km_start + dist
        vehicle_odometers[vehicle_id] = km_end
        total_dist += dist
        
        ret_date = (datetime.now() - timedelta(days=random.randint(0, 180))).strftime('%Y-%m-%d')
        state = 'completed'
        
        sql.append(f"INSERT INTO fleet_trip (id, name, vehicle_id, allocation_id, company_id, km_at_start_actual, km_at_end_actual, actual_distance, return_date, state) VALUES ({i}, 'TRIP/{i:05}', {vehicle_id}, {alloc['id']}, {COMPANY_ID}, {km_start}, {km_end}, {dist}, '{ret_date}', '{state}');")

    # 5. Generate Maintenance
    total_maint_cost = 0
    for i in range(1, NUM_MAINTENANCE + 1):
        vehicle_id = random.choice(range(1, NUM_VEHICLES + 1))
        service_type = random.choice(['preventive', 'corrective'])
        date_serv = (datetime.now() - timedelta(days=random.randint(1, 180))).strftime('%Y-%m-%d')
        cost = random.randint(500, 5000)
        total_maint_cost += cost
        state = 'completed'
        
        sql.append(f"INSERT INTO hagbes_fleet_maintenance (id, vehicle_id, company_id, service_type, service_date, cost, state) VALUES ({i}, {vehicle_id}, {COMPANY_ID}, '{service_type}', '{date_serv}', {cost}, '{state}');")

    with open('fleet_uat_data.sql', 'w') as f:
        f.write('\n'.join(sql))

    # Output KPIs for documentation
    print("--- EXPECTED KPI VALUES ---")
    print(f"Total Vehicles: {NUM_VEHICLES}")
    print(f"Total Fleet Distance: {total_dist:.2f} KM")
    print(f"Average Distance per Trip: {total_dist/NUM_TRIPS:.2f} KM")
    print(f"Total Trips: {NUM_TRIPS}")
    print(f"Total Maintenance Events: {NUM_MAINTENANCE}")
    print(f"Total Maintenance Cost: {total_maint_cost:.2f}")
    print(f"Total Allocations: {NUM_ALLOCATIONS}")
    print(f"Active Allocations: {active_allocations}")
    print(f"Total Requisitions: {NUM_REQUISITIONS}")

if __name__ == '__main__':
    generate_sql()
