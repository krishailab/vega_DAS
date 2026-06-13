from app.database import stations_collection

def migrate_stations():
    print("Starting migration: setting is_dispatch to False for existing stations...")
    
    # Update stations where is_dispatch is missing
    result = stations_collection.update_many(
        {"is_dispatch": {"$exists": False}},
        {"$set": {"is_dispatch": False}}
    )
    
    print(f"Migration complete. {result.modified_count} stations updated.")

if __name__ == "__main__":
    migrate_stations()
