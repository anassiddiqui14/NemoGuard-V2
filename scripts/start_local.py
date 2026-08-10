#!/usr/bin/env python3
"""Start all local services for the demo."""

import os
import subprocess

def main():
    generated_dir = 'data/generated'
    db_path = os.path.join(generated_dir, 'pipeline.db')
    
    print("1. Checking database...")
    if not os.path.exists(db_path):
        print("Database not found. Running generate_demo_data.py...")
        script_path = os.path.join(os.path.dirname(__file__), 'generate_demo_data.py')
        try:
            subprocess.run(['python3', script_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error generating data: {e}")
            return
    else:
        print("Database found.")

    print("\n2. Instructions for running services:")
    print("--------------------------------------")
    print("To run the API server:")
    print("  cd src && uvicorn api.main:app --reload")
    print("\nTo run the UI:")
    print("  cd ui && npm start (or streamlit run app.py)")
    print("--------------------------------------")

if __name__ == '__main__':
    main()
