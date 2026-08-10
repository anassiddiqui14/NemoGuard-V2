#!/usr/bin/env python3
"""Reset the demo to a clean starting state."""

import os
import shutil
import subprocess
import sqlite3

def main():
    generated_dir = 'data/generated'
    
    print(f"1. Deleting {generated_dir} contents...")
    if os.path.exists(generated_dir):
        for item in os.listdir(generated_dir):
            item_path = os.path.join(generated_dir, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
    else:
        os.makedirs(generated_dir, exist_ok=True)
    
    print("2. Re-running generate_demo_data.py programmatically...")
    script_path = os.path.join(os.path.dirname(__file__), 'generate_demo_data.py')
    try:
        subprocess.run(['python3', script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running generate_demo_data.py: {e}")
        return

    print("3. Verifying expected counts...")
    db_path = os.path.join(generated_dir, 'pipeline.db')
    if not os.path.exists(db_path):
        print("Error: Database was not created.")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Found {len(tables)} tables in DB.")
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")
        
    print("Demo reset complete!")

if __name__ == '__main__':
    main()
