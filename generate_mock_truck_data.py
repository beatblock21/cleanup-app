import json
import random

def generate_mock_trucks(num_trucks=20):
    trucks = []
    for i in range(1, num_trucks + 1):
        truck = {
            'id': f'{i}',
            'status': 'default_status',  # Add a default status
            'is_dispatched': random.choice([False, True])  # Randomly assign dispatched status
        }
        trucks.append(truck)
    return trucks

def save_to_json(data, filename='mock_trucks.json'):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    mock_trucks = generate_mock_trucks()
    save_to_json(mock_trucks)
    print(f"Generated {len(mock_trucks)} mock trucks and saved to 'mock_trucks.json'.")
