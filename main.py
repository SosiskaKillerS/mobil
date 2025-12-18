from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.params import Depends
from starlette.middleware.cors import CORSMiddleware
from authx import AuthX, AuthXConfig
from schemas import UserLogin, UserRegistration, Verify
from init_db import get_session, engine, Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User
from email.message import EmailMessage
import aiosmtplib
import secrets
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

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "kachelyass123@gmail.com"
SMTP_PASSWORD = "fyffhcgizrxjpvmu"
SMTP_FROM = "kachelyass123@gmail.com"
SMTP_STARTTLS = True
CODE_TTL_MINUTE = 10

async def send_email(to_email: str, subject: str, body: str)->None:
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )

@app.post('/startup')
async def startup():
    async with engine.begin() as connect:
        await connect.run_sync(Base.metadata.drop_all)
        await connect.run_sync(Base.metadata.create_all)
    return {"message": "success"}

@app.post('/registration', summary
="Registration for user")
async def reg(creds: UserRegistration, bg: BackgroundTasks, db: AsyncSession = Depends(get_session)):
    result_email = await db.execute(select(User).where(creds.email == User.email))
    is_email_engaged = result_email.scalar_one_or_none()
    if is_email_engaged is not None:
        raise HTTPException(status_code=400, detail='Email is already taken')

    result_username = await db.execute(select(User).where(creds.username == User.username))
    is_username_engaged = result_username.scalar_one_or_none()
    if is_username_engaged is not None:
        raise HTTPException(status_code=400, detail="Username is already taken")

    code = f"{secrets.randbelow(10_000):04d}"

    new_user = User(
        username=creds.username,
        email=getattr(creds, "email"),
        password=creds.password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    bg.add_task(
        send_email,
        new_user.email,
        "Email verification code",
        f"Your code: {code}",
    )
    return {"message": "verification code sent"}

@app.post('/verify-email')
async def verify_email(data: Verify, db: AsyncSession = Depends(get_session)):
    ...

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



