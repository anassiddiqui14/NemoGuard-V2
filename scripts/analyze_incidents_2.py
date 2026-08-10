import pandas as pd
import json
import re

file_path = '/Users/anassiddiqui/Downloads/NemoGuard/Incidents_July.xlsx'

def clean_summary(summary):
    if pd.isna(summary):
        return ""
    # Remove specific IDs, IPs, or sensitive looking tokens
    # Generalize paths and hostnames
    s = str(summary)
    s = re.sub(r'\[P\d\]', '', s) # Remove priority tags like [P3]
    s = re.sub(r'\[PSS [A-Z]+\]', '', s) # Remove team tags like [PSS BWS]
    s = re.sub(r'Re-Triggered:|Triggered:', '', s) # Remove prefix
    
    # Try to extract the core issue by removing specific instances
    # like /whgservices/...
    s = re.sub(r'\/[\w\/]+', '{ENDPOINT}', s)
    s = re.sub(r'\b[a-z0-9\-]+\-[a-z0-9\-]+\-[a-z0-9\-]+\b', '{HOST/RESOURCE}', s) # match things like whr-use1-apig-digitalpromosmiscservices-prd
    
    return s.strip()

try:
    df = pd.read_excel(file_path)
    
    # Filter for the teams
    teams = ['Pss Aws', 'Pss Edw', 'Pss Bws']
    # 'Assigned SVD Name' seems to hold the team
    team_col = 'Assigned SVD Name'
    
    # Normalize team names
    df['Team_Lower'] = df[team_col].astype(str).str.lower()
    
    target_teams = ['pss aws', 'pss edw', 'pss bws']
    filtered_df = df[df['Team_Lower'].isin(target_teams)]
    
    print(f"Found {len(filtered_df)} incidents for the target teams.")
    
    # Group by team and find common alert summaries
    results = {}
    for team in target_teams:
        team_df = filtered_df[filtered_df['Team_Lower'] == team]
        
        # Clean summaries to find patterns
        cleaned_summaries = team_df['Summary'].apply(clean_summary)
        
        # Count frequencies
        top_patterns = cleaned_summaries.value_counts().head(10).to_dict()
        results[team.upper()] = top_patterns
        
    print(json.dumps(results, indent=2))
    
except Exception as e:
    print("Error:", str(e))
