#!/usr/bin/env python3
"""Generate the complete synthetic dataset for the pipeline copilot demo."""

import argparse
import yaml
import os
import random
import sys

# Assume appropriate PYTHONPATH setup or running from root
from src.generator.topology import Topology
from src.generator.healthy_runs import HealthyRunGenerator
from src.generator.scenario_injection import ScenarioInjector
from src.generator.validators import run_all_validations
from src.store.postgres_database import PostgresDatabase

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic dataset")
    parser.add_argument('--config', default='config/demo.yaml', help='Path to config file')
    parser.add_argument('--output-dir', default='data/generated', help='Directory for output')
    parser.add_argument('--db', default='data/generated/pipeline.db', help='Database file path')
    parser.add_argument('--seed', type=int, default=None, help='Random seed override')
    args = parser.parse_args()

    config_path = args.config
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        print(f"Warning: config file {config_path} not found. Using defaults.")
        config = {}

    seed = args.seed if args.seed is not None else config.get('random_seed', 42)
    random.seed(seed)
    
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    
    if os.path.exists(args.db):
        os.remove(args.db)

    print("Step 4: Initialize Topology")
    topology = Topology('data/seed/')
    
    print("Step 5: Validate topology")
    if not topology.validate():
        print("Error: Topology validation failed. Aborting.")
        sys.exit(1)

    print("Step 6: Generate healthy runs")
    healthy_gen = HealthyRunGenerator(topology, config, random)
    executions, logs = healthy_gen.generate()

    print("Step 7: Inject demo incidents")
    injector = ScenarioInjector(topology, config, random)
    executions, logs, demo_alerts, demo_ground_truth = injector.inject_demo_incidents(executions, logs)
    
    print("Step 8: Inject random incidents")
    executions, logs, random_alerts, random_ground_truth = injector.inject_random_incidents(executions, logs, 5)

    all_alerts = demo_alerts + random_alerts
    all_ground_truth = demo_ground_truth + random_ground_truth

    print("Step 9: Run all validations")
    results = run_all_validations(topology.jobs, topology.edges, executions, logs, all_alerts, all_ground_truth, topology.assets, topology.asset_deps)
    failed = False
    for k, v in results.items():
        if v:
            print(f"Validation failed for {k}: {v}")
            failed = True
    if failed:
        print("Warning: Some validation checks failed.")

    print("Step 10: Initialize Database and load everything")
    db = Database(args.db)
    db.init_schema()
    db.load_seed_data('data/seed/')
    
    db.insert_executions(executions)
    db.insert_logs(logs)
    db.insert_alerts(all_alerts)
    
    print("Step 11: Write ground_truth.json to output dir")
    gt_path = os.path.join(args.output_dir, 'ground_truth.json')
    db.insert_ground_truth(all_ground_truth, gt_path)

    print("Step 12: Print summary stats")
    stats = db.get_stats()
    for table, count in stats.items():
        print(f"  {table}: {count}")
    
    db.close()
    
    print(f"Dataset generation complete! Generated {len(executions)} executions, {len(logs)} logs, {len(all_alerts)} alerts, {len(all_ground_truth)} incidents.")

if __name__ == '__main__':
    main()
