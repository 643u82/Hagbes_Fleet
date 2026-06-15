import random
import sys

def calculate_trip_score(fuel_variance, distance_variance, time_variance, high_severity_discrepancies, issue_logs):
    # 1. Fuel Score (40%)
    if fuel_variance <= 0:
        fuel_score = 100
    else:
        fuel_score = max(0, 100 - (fuel_variance * 2))
        
    # 2. Distance Score (25%)
    if distance_variance <= 0:
        distance_score = 100
    else:
        distance_score = max(0, 100 - (distance_variance * 2))
        
    # 3. Time Score (20%)
    if time_variance <= 0:
        time_score = 100
    else:
        time_score = max(0, 100 - (time_variance * 2))
        
    # 4. Compliance Score (15%)
    compliance_score = 100
    compliance_score -= (high_severity_discrepancies * 25)
    compliance_score -= (issue_logs * 10)
    compliance_score = max(0, compliance_score)
    
    total_score = (fuel_score * 0.40) + (distance_score * 0.25) + (time_score * 0.20) + (compliance_score * 0.15)
    
    return {
        'fuel_score': fuel_score,
        'distance_score': distance_score,
        'time_score': time_score,
        'compliance_score': compliance_score,
        'total_score': total_score
    }

def main():
    print("--- DRIVER PERFORMANCE SCORING TEST ---")
    drivers = [
        {"name": "Driver A (Perfect)", "trips": [(0, 0, 0, 0, 0), (0, 0, 0, 0, 0), (0, 0, 0, 0, 0)]},
        {"name": "Driver B (Heavy Foot)", "trips": [(20, 0, 0, 0, 0), (30, 0, 0, 0, 0), (10, 0, 0, 0, 0)]},
        {"name": "Driver C (Gets Lost)", "trips": [(0, 15, 0, 0, 0), (0, 20, 10, 0, 0), (0, 5, 0, 0, 0)]},
        {"name": "Driver D (Reckless/Issues)", "trips": [(0, 0, 0, 1, 1), (0, 0, 0, 0, 2), (0, 0, 0, 1, 0)]},
        {"name": "Driver E (Mixed Bag)", "trips": [(5, 5, 5, 0, 0), (-5, -5, -5, 0, 0), (15, 10, 0, 0, 1)]},
        {"name": "Driver F (Terrible)", "trips": [(50, 40, 30, 2, 2), (60, 50, 40, 1, 3)]}
    ]
    
    for driver in drivers:
        print(f"\nEvaluating {driver['name']}:")
        trip_scores = []
        for i, (f_var, d_var, t_var, hs_disc, issues) in enumerate(driver['trips']):
            score = calculate_trip_score(f_var, d_var, t_var, hs_disc, issues)
            trip_scores.append(score)
            print(f"  Trip {i+1}: Fuel Var: {f_var}%, Dist Var: {d_var}%, Time Var: {t_var}%, HS Disc: {hs_disc}, Issues: {issues}")
            print(f"    Scores -> Fuel: {score['fuel_score']:.1f}, Dist: {score['distance_score']:.1f}, Time: {score['time_score']:.1f}, Comp: {score['compliance_score']:.1f} | TOTAL: {score['total_score']:.2f}")
            
        avg_fuel = sum(t['fuel_score'] for t in trip_scores) / len(trip_scores)
        avg_dist = sum(t['distance_score'] for t in trip_scores) / len(trip_scores)
        avg_time = sum(t['time_score'] for t in trip_scores) / len(trip_scores)
        avg_comp = sum(t['compliance_score'] for t in trip_scores) / len(trip_scores)
        avg_total = (avg_fuel * 0.4) + (avg_dist * 0.25) + (avg_time * 0.2) + (avg_comp * 0.15)
        
        print(f"  --> MONTHLY KPI: Fuel={avg_fuel:.1f}, Dist={avg_dist:.1f}, Time={avg_time:.1f}, Comp={avg_comp:.1f} | OVERALL SCORE: {avg_total:.2f}")

if __name__ == '__main__':
    main()
