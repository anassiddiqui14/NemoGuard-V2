import pandas as pd
import json

file_path = '/Users/anassiddiqui/Downloads/NemoGuard/Incidents_July.xlsx'

# Read the excel file
try:
    df = pd.read_excel(file_path)
    
    # Let's print the columns to understand the schema
    print("Columns:", list(df.columns))
    
    # Try to find the team column
    team_cols = [c for c in df.columns if 'team' in c.lower() or 'group' in c.lower() or 'assign' in c.lower()]
    print("Potential team columns:", team_cols)
    
    # Try to find the alert type column
    alert_cols = [c for c in df.columns if 'alert' in c.lower() or 'type' in c.lower() or 'category' in c.lower() or 'summary' in c.lower() or 'desc' in c.lower()]
    print("Potential alert columns:", alert_cols)
    
    # Print the first few rows of these potential columns (just a small sample)
    if team_cols and alert_cols:
        print("\nSample Data (first 3 rows):")
        print(df[team_cols + alert_cols].head(3).to_dict('records'))
    
except Exception as e:
    print("Error:", str(e))
