import csv
import json
import requests
import time
from itertools import product

cities = {}
csv_filename = "examples/locationLocationLocation/it.csv"

print(f"Loading cities from {csv_filename}...")
with open(csv_filename, mode='r', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    for row in reader:
        name = row['city']
        lat = float(row['lat'])
        lng = float(row['lng'])
        cities[name] = (lng, lat) # OSRM takes (Longitude, Latitude)

city_names = list(cities.keys())
total_routes = len(city_names) ** 2
print(f"Loaded {len(city_names)} cities. Preparing to calculate {total_routes} routes.")

nxn_matrix = {}
completed = 0
start_time = time.time()

for origin, dest in product(city_names, repeat=2):
    if origin not in nxn_matrix:
        nxn_matrix[origin] = {}
        
    if origin == dest:
        nxn_matrix[origin][dest] = {
            "distance_km": 0, "driving_hours": 0.0, "has_ferry": False
        }
        completed += 1
        continue

    lon1, lat1 = cities[origin]
    lon2, lat2 = cities[dest]
    
    # load HPC OSRM Server
    url = f"http://localhost:6578/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?steps=true&overview=false"
    
    try:
        response = requests.get(url).json()
        
        # Check if OSRM successfully found a road
        if response.get('code') != 'Ok':
            print(f"Warning: No route found between {origin} and {dest}")
            continue
            
        route = response['routes'][0]
        dist_km = round(route['distance'] / 1000, 1)
        hours = route['duration'] / 3600
        
        has_ferry = any(step.get('mode') == 'ferry' 
                        for leg in route['legs'] 
                        for step in leg['steps'])
                            
        nxn_matrix[origin][dest] = {
            "distance_km": dist_km,
            "driving_hours": round(hours, 1),
            "has_ferry": has_ferry,
        }
        
    except Exception as e:
        print(f"API Error between {origin} and {dest}: {e}")
        
    # Progress tracker
    completed += 1
    if completed % 1000 == 0:
        print(f"Progress: {completed} / {total_routes} routes calculated...")

output_file = "examples/locationLocationLocation/italy_100x100_matrix.json"
with open(output_file, "w") as outfile:
    json.dump(nxn_matrix, outfile, indent=4)
    
elapsed = round(time.time() - start_time, 1)
print(f"Success! 100x100 Matrix generated in {elapsed} seconds and saved to {output_file}.")