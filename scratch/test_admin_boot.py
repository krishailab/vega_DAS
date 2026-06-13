import sys

try:
    print("Testing application imports and FastAPI boot with Starlette-Admin...")
    from app.main import app
    print("SUCCESS: FastAPI and Starlette-Admin successfully loaded and mounted!")
    
    # Check if admin is registeredadmin-ui
    routes = [r.path for r in app.routes]
    print("Registered Routes:")
    for route in sorted(routes):
        if "/admin" in route:
            print(f"  - {route}")
            
    print("\nBoot verification succeeded! No syntax or import errors.")
    sys.exit(0)
except Exception as e:
    print("FAILED: Boot verification failed with an error:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
