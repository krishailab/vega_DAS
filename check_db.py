from app.database import stations_collection, users_collection
print("--- STATIONS ---")
for s in stations_collection.find({"station_id": "STN26A0001"}):
    print(s)
print("--- USER ---")
print(users_collection.find_one({"user_id": "EMP26AA0005"}))
