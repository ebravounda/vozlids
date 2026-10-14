import os
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, Request, Response
from db import db

ALG = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    return jwt.encode({"sub": user_id, "email": email, "exp": exp, "type": "access"}, _secret(), algorithm=ALG)


def create_refresh_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    return jwt.encode({"sub": user_id, "exp": exp, "type": "refresh"}, _secret(), algorithm=ALG)


def set_access_cookie(response: Response, token: str):
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=900, path="/")


def set_auth_cookies(response: Response, user_id: str, email: str) -> str:
    access = create_access_token(user_id, email)
    set_access_cookie(response, access)
    response.set_cookie("refresh_token", create_refresh_token(user_id), httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")
    return access


def clear_auth_cookies(response: Response):
    for k in ("access_token", "refresh_token"):
        response.delete_cookie(k, path="/", secure=True, samesite="none")


def decode(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sesión caducada")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token no válido")
    if payload.get("type") != expected_type:
        raise HTTPException(401, "Token no válido")
    return payload


async def get_user_by_id(uid: str) -> dict:
    try:
        user = await db.users.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
    except InvalidId:
        user = None
    if not user:
        raise HTTPException(401, "Usuario no encontrado")
    user["id"] = str(user.pop("_id"))
    return user


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            token = h[7:]
    if not token:
        raise HTTPException(401, "No autenticado")
    payload = decode(token, "access")
    return await get_user_by_id(payload["sub"])
