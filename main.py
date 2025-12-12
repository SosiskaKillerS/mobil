from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.middleware.cors import CORSMiddleware
from init_db import engine, Base, get_session
from models import User
from schemas import UserCreate, UserLogin
from authx import AuthX, AuthXConfig
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

config = AuthXConfig(
    JWT_SECRET_KEY="SUPER_SECRET_KEY",
    JWT_TOKEN_LOCATION=["headers"],
    JWT_HEADER_NAME="Authorization",
    JWT_HEADER_TYPE="Bearer",
)

auth = AuthX(config=config)
auth.handle_errors(app)
@app.post("/startup")
async def on_startup():

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    return {'response': 'success'}

@app.post('/users/login')
async def user_login(user: UserLogin, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(User).where(User.username == user.username))
    user_res = result.scalar_one_or_none()

    if user_res is None or user.password != User.password:
        raise HTTPException(status_code=401, detail='Wrong password or login')
    access_token = auth.create_access_token(uid=user_res.id)
    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'user_id': user_res.id,
        'username': user_res.username,
        'avatar_url': user_res.avatar_url
    }
@app.get('/me', dependencies=[Depends(auth.access_token_required)])
async def me():
    return {'message': 'Hello from protected route'}
