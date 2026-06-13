import jwt

# The token you received from the /api/auth/login endpoint
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtYXN0ZXIyLmFkbWluQHZlZ2EuY29tIiwicm9sZSI6Ik1hc3RlciBBZG1pbiIsImV4cCI6MTc3NzU4NDQ0MH0.vSVDu8TEBdZP9VaKxPnw8LPgUFWJGzCjDGhke-6JOvQ"

# The Secret Key used by thebackend (found in your app/auth.py or .env)
# Default for this project: super_secret_vega_track_key_123
SECRET_KEY = "super_secret_vega_track_key_123" 
ALGORITHM = "HS256"

def decode_token(token):
    try:
        # Decode the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Extract the role
        role = payload.get("role")
        user_id = payload.get("sub")
        
        print(f"--- Token Decoded Successfully ---")
        print(f"User Identifier: {user_id}")
        print(f"Role: {role}")
        
        return payload
    except jwt.ExpiredSignatureError:
        print("Error: Token has expired.")
    except jwt.InvalidTokenError:
        print("Error: Invalid token.")

if __name__ == "__main__":
    decode_token(token)
