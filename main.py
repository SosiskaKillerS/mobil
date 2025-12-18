from fastapi import FastAPI, HTTPException
from fastapi.params import Depends
from starlette.middleware.cors import CORSMiddleware
from authx import AuthX, AuthXConfig
from schemas import UserLogin, UserRegistration
from init_db import get_session, engine, Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS "],
    allow_headers=["*"],
)

config = AuthXConfig()
config.JWT_SECRET_KEY = "SECRET_KEY"
config.JWT_ACCESS_COOKIE_NAME = 'my_access_token'
config.JWT_TOKEN_LOCATION = ["cookies"]

security = AuthX(config=config)

@app.post('/startup')
async def startup():
    async with engine.begin() as connect:
        await connect.run_sync(Base.metadata.drop_all)
        await connect.run_sync(Base.metadata.create_all)
    return {"message": "success"}

@app.post('/registration', summary
="Registration for user")
async def reg(creds: UserRegistration, db: AsyncSession = Depends(get_session)):
    new_user = User(
        username=creds.username,
        email=getattr(creds, "email"),
        password=creds.password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return 'success'


@app.post('/login', summary="User login endpoint")
async def login(creds: UserLogin, db: AsyncSession = Depends(get_session)):
    if creds.email is None:
        result = await db.execute(select(User).where(User.username == creds.username))
        is_username_exist = result.scalar_one_or_none()
        if is_username_exist is None:
            raise HTTPException(status_code=401, detail = 'username or password is wrong')
        if creds.password != is_username_exist.password:
            raise HTTPException(status_code=401, detail = 'username or password is wrong')
        token = security.create_access_token(uid=str(is_username_exist.id))
        return {"access_token": token}
    else:
        result = await db.execute(select(User).where(User.email == creds.email))
        is_email_exist = result.scalar_one_or_none()
        if is_email_exist is None:
            return HTTPException(status_code=401, detail= 'email or password is wrong')
        if creds.password != is_email_exist.password:
            return HTTPException(status_code=401, detail='email or password is wrong')
        token = security.create_access_token(uid=str(is_email_exist.id))
        return {"access_token": token}

