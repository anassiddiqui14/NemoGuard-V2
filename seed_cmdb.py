import os
import psycopg2

DATABASE_URL = os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db")

def seed_db():
    assets = [
        ("customer_profile", "service", "Customer Profile Ingestion API", 15),
        ("Loyalty Executive Dashboard", "dashboard", "Loyalty Executive Dashboard", 30),
        ("Campaign Audience Export", "export", "Campaign Audience Export", 60),
        ("marketing_sync_job", "job", "Marketing Sync Job", 120),
        ("fraud_detection_api", "service", "Fraud Detection API", 5),
        
        ("JOB_AWS_EXTRACT_RESERVATION", "job", "AWS Extract Reservation", 60),
        ("Reservation Analytics Mart", "mart", "Reservation Analytics Mart", 45),
        ("daily_financial_report", "report", "Daily Financial Report", 1440),
        ("hotel_capacity_planner", "dashboard", "Hotel Capacity Planner", 60),
        
        ("postgres_cdc", "service", "Postgres CDC", 10),
        ("order_history_lake", "lake", "Order History Lake", 120),
        
        ("kafka_ingest", "service", "Kafka Ingest", 5),
        ("realtime_analytics_dashboard", "dashboard", "Realtime Analytics", 10),
        ("session_replay_store", "store", "Session Replay Store", 60),
        
        ("auth_service", "service", "Authentication Service", 5),
        ("user_registry", "service", "User Registry", 10),
        ("core_transaction_db", "database", "Core Transaction DB", 5),
        ("mobile_app_events", "service", "Mobile App Events", 5),
        ("web_telemetry", "service", "Web Telemetry", 5),
        ("identity_provider", "service", "Identity Provider", 5),
        ("aws_rds_main", "database", "AWS RDS Main", 5),
        ("payment_gateway", "service", "Payment Gateway", 5),
        ("inventory_db", "database", "Inventory DB", 5)
    ]
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            for a_id, a_type, name, sla in assets:
                cursor.execute("""
                    INSERT INTO data_asset (asset_id, asset_type, name, freshness_sla_minutes)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (asset_id) DO UPDATE SET freshness_sla_minutes = EXCLUDED.freshness_sla_minutes
                """, (a_id, a_type, name, sla))
        conn.commit()
    print("Database seeded successfully.")

if __name__ == "__main__":
    seed_db()
