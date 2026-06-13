from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from .. import schemas, auth
from ..database import users_collection

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class AuthOperations:
    @staticmethod
    def login(form_data: OAuth2PasswordRequestForm):
        user = users_collection.find_one({
            "$or": [
                {"email": form_data.username},
                {"mobile_number": form_data.username}
            ]
        })
        if not user or not auth.verify_password(form_data.password, user.get("password", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email/mobile or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        identifier = user.get("email") or user.get("mobile_number")
        token_data = {
            "sub": identifier,
            "role": user.get("role")
        }
        
        if user.get("is_assemble"):
            token_data["is_assemble"] = True
        if user.get("is_dispatch_admin"):
            token_data["is_dispatch_admin"] = True
        
        access_token = auth.create_access_token(
            data=token_data, 
            expires_delta=access_token_expires
        )
        refresh_token = auth.create_refresh_token(data={"sub": identifier})
        
        return {
            "access_token": access_token, 
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    @staticmethod
    def refresh(refresh_token: str):
        payload = auth.validate_refresh_token(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        identifier = payload.get("sub")
        user = users_collection.find_one({
            "$or": [
                {"email": identifier},
                {"mobile_number": identifier}
            ]
        })
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
            
        token_data = {
            "sub": identifier,
            "role": user.get("role")
        }
        
        if user.get("is_assemble"):
            token_data["is_assemble"] = True
        if user.get("is_dispatch_admin"):
            token_data["is_dispatch_admin"] = True
        
        new_access_token = auth.create_access_token(data=token_data)
        return {
            "access_token": new_access_token,
            "refresh_token": refresh_token, # Return same refresh token or rotate it
            "token_type": "bearer"
        }

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    return AuthOperations.login(form_data)

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(refresh_token: str):
    return AuthOperations.refresh(refresh_token)
