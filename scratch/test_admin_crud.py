import asyncio
import sys
from starlette.requests import Request
class MockRequest:
    pass

async def test_crud():
    print("Testing PyMongoModelView CRUD operations...")
    try:
        from app.admin import admin
        from app.database import users_collection
        user_view = None
        for view in admin._views:
            if view.identity == "users":
                user_view = view
                break
                
        if not user_view:
            print("FAILED: Could not find User view in admin.views")
            sys.exit(1)
            
        print("1. Testing 'count'...")
        total_users = await user_view.count(MockRequest())
        print(f"   Success! Total users in DB: {total_users}")
        
        print("2. Testing 'find_all' with limit=2...")
        users = await user_view.find_all(MockRequest(), skip=0, limit=2)
        print(f"   Success! Retrieved {len(users)} users.")
        for u in users:
            print(f"   - {u.first_name} {u.last_name} ({u.role}) ID: {u.user_id}")
            
        if users:
            print("3. Testing 'find_by_pk'...")
            pk = users[0].user_id
            user = await user_view.find_by_pk(MockRequest(), pk)
            if user and user.user_id == pk:
                print(f"   Success! Found user by PK: {user.first_name} {user.last_name}")
            else:
                print("   FAILED: User not found or mismatch.")
                sys.exit(1)
                
            print("4. Testing 'find_by_pks'...")
            pks = [u.user_id for u in users]
            found_users = await user_view.find_by_pks(MockRequest(), pks)
            if len(found_users) == len(pks):
                print(f"   Success! Found all {len(found_users)} users by PKs list.")
            else:
                print("   FAILED: Multi-PK search count mismatch.")
                sys.exit(1)
                
        print("\nAll CRUD provider test cases passed successfully!")
        sys.exit(0)
    except Exception as e:
        print("FAILED: CRUD integration test failed with an error:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_crud())
