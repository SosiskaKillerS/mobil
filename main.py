import json
import secrets
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
import uuid
from pathlib import Path
from starlette.middleware.cors import CORSMiddleware

from authx import AuthX, AuthXConfig, TokenPayload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from schemas import UserLogin, UserRegistration, Verify, RestorePassword, RestorePasswordPatch, PostOut, PostCreate
from init_db import get_session, engine, Base
from models import User, Post

from email.message import EmailMessage
import aiosmtplib

from redis.asyncio import Redis
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = AuthXConfig()
config.JWT_SECRET_KEY = "my_secret_key"
config.JWT_ACCESS_COOKIE_NAME = "my_access_token"
config.JWT_TOKEN_LOCATION = ["cookies"]
security = AuthX(config=config)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "kachelyass123@gmail.com"
SMTP_PASSWORD = "fyffhcgizrxjpvmu"
SMTP_FROM = SMTP_USER
SMTP_STARTTLS = True

CODE_TTL_MINUTE = 10
REG_TTL_SECONDS = CODE_TTL_MINUTE * 60

REDIS_URL = os.getenv("REDIS_URL")

MEDIA_DIR = Path("media")
AVATARS_DIR = MEDIA_DIR / "avatars"
POST_DIR = MEDIA_DIR / "posts"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)
POST_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


async def send_email(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
            timeout=10,  # чтобы быстрее падало
        )
        print("EMAIL SENT", to_email, flush=True)
    except Exception as e:
        # чтобы демо работало: выводим код/письмо в логи Render
        print(f"[EMAIL FAILED] to={to_email} subject={subject} body={body} err={e!r}", flush=True)



def get_redis() -> Redis:
    r = getattr(app.state, "redis", None)
    if r is None:
        raise HTTPException(status_code=500, detail="Redis is not initialized. Call /startup first.")
    return r



async def generate_unique_code(prefix: str) -> str:
    r = get_redis()
    for _ in range(30):
        code = f"{secrets.randbelow(10_000):04d}"
        print(code)
        if not await r.exists(f"{prefix}:code:{code}"):
            return code
    raise HTTPException(status_code=500, detail="Could not generate code, try again")


@app.post("/startup")
async def startup():
    async with engine.begin() as connect:
        await connect.run_sync(Base.metadata.drop_all)
        await connect.run_sync(Base.metadata.create_all)

    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    return {"message": "success"}


@app.post("/shutdown")
async def shutdown():
    r = getattr(app.state, "redis", None)
    if r is not None:
        await r.aclose()
    return {"message": "redis closed"}


@app.post("/registration")
async def reg(creds: UserRegistration, bg: BackgroundTasks, db: AsyncSession = Depends(get_session)):
    r = get_redis()

    result_email = await db.execute(select(User).where(User.email == creds.email))
    if result_email.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Email is already taken")

    result_username = await db.execute(select(User).where(User.username == creds.username))
    if result_username.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Username is already taken")

    email_lower = creds.email.lower()
    username_lower = creds.username.lower()

    email_key = f"reg:email:{email_lower}"
    username_key = f"reg:username:{username_lower}"

    if await r.exists(email_key) or await r.exists(username_key):
        raise HTTPException(status_code=400, detail="Verification already requested. Check your email.")

    code = await generate_unique_code("reg")

    payload = {
        "username": creds.username,
        "email": creds.email,
        "password": creds.password,
        "created_at": datetime.utcnow().isoformat(),
    }

    await r.set(email_key, json.dumps(payload), ex=REG_TTL_SECONDS)
    await r.set(username_key, email_lower, ex=REG_TTL_SECONDS)
    await r.set(f"reg:code:{code}", email_lower, ex=REG_TTL_SECONDS)

    bg.add_task(
        send_email,
        creds.email,
        "Email verification code",
        f"Your code: {code}",
    )

    return {"message": "verification code sent"}


@app.post("/verify-email")
async def verify_email(data: Verify, db: AsyncSession = Depends(get_session)):
    r = get_redis()

    code_key = f"reg:code:{data.code}"
    email_lower = await r.get(code_key)
    if not email_lower:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    email_key = f"reg:email:{email_lower}"
    raw = await r.get(email_key)
    if not raw:
        await r.delete(code_key)
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    payload = json.loads(raw)

    check_email = await db.execute(select(User).where(User.email == payload["email"]))
    if check_email.scalar_one_or_none() is not None:
        await r.delete(code_key, email_key, f"reg:username:{payload['username'].lower()}")
        raise HTTPException(status_code=400, detail="Email is already taken")

    check_username = await db.execute(select(User).where(User.username == payload["username"]))
    if check_username.scalar_one_or_none() is not None:
        await r.delete(code_key, email_key, f"reg:username:{payload['username'].lower()}")
        raise HTTPException(status_code=400, detail="Username is already taken")

    new_user = User(
        username=payload["username"],
        email=payload["email"],
        password=payload["password"],
        is_verified=True,
    )
    db.add(new_user)
    await db.commit()

    await r.delete(code_key, email_key, f"reg:username:{payload['username'].lower()}")

    return {"message": "email verified, user created"}


@app.post("/login")
async def login(creds: UserLogin, bg: BackgroundTasks, db: AsyncSession = Depends(get_session)):
    r = get_redis()

    if creds.email is None:
        result = await db.execute(select(User).where(User.username == creds.username))
    else:
        result = await db.execute(select(User).where(User.email == creds.email))

    user = result.scalar_one_or_none()
    if user is None or creds.password != user.password:
        raise HTTPException(status_code=401, detail="email/username or password is wrong")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email is not verified")

    code = await generate_unique_code("login")

    await r.set(f"login:code:{code}", str(user.id), ex=REG_TTL_SECONDS)

    bg.add_task(
        send_email,
        user.email,
        "Login code",
        f"Your login code: {code}",
    )

    return {"message": "login code sent"}


@app.post("/login-verify")
async def login_verify(data: Verify):
    r = get_redis()

    uid = await r.get(f"login:code:{data.code}")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    await r.delete(f"login:code:{data.code}")

    token = security.create_access_token(uid=str(uid))
    return {"access_token": token}


@app.post('/restore_password')
async def restore_password(creds: RestorePassword, bg: BackgroundTasks, db: AsyncSession = Depends(get_session)):
    r = get_redis()

    if creds.email is None:
        result = await db.execute(select(User).where(User.username == creds.username))
    else:
        result = await db.execute(select(User).where(User.email == creds.email))

    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="email/username is wrong")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email is not verified")

    code = await generate_unique_code("restore_password")

    await r.set(f"restore_password:code:{code}", str(user.id), ex=REG_TTL_SECONDS)

    bg.add_task(
        send_email,
        user.email,
        "Password reset code",
        f"Your password reset code: {code}",
    )

    return {"message": "password reset code sent"}

@app.patch("/restore_password")
async def restore_password_patch(data: RestorePasswordPatch, db: AsyncSession = Depends(get_session)):
    r = get_redis()

    uid = await r.get(f"restore_password:code:{data.code}")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    result = await db.execute(select(User).where(User.id == int(uid)))
    user = result.scalar_one_or_none()
    if user is None:
        await r.delete(f"restore_password:code:{data.code}")
        raise HTTPException(status_code=404, detail="User not found")

    user.password = data.new_password
    await db.commit()

    await r.delete(f"restore_password:code:{data.code}")

    return {"message": "password updated"}

@app.get("/users/{user_id}/")
async def get_user(user_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "avatar_url": user.avatar_url,
    }

@app.post("/users/{user_id}/avatar")
async def upload_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only images allowed")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".png"

    filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
    dest_path = AVATARS_DIR / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    dest_path.write_bytes(content)

    user.avatar_url = f"/media/avatars/{filename}"
    avatar_url = user.avatar_url  # <-- фикс: сохраняем до commit

    await db.commit()

    return {"avatar_url": avatar_url}


@app.post("/posts", response_model=PostOut, status_code=201)
async def create_post(
    body: PostCreate,
    db: AsyncSession = Depends(get_session),
    token: TokenPayload = Depends(security.token_required(locations=["headers", "cookies"])),
):
    try:
        author_id = int(token.sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == author_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    currency = (body.currency or "USD").upper().strip()
    if len(currency) != 3:
        raise HTTPException(status_code=400, detail="Invalid currency")

    price_cents = body.price_cents
    if not body.is_paid:
        price_cents = None
    else:
        if price_cents is None or price_cents < 0:
            raise HTTPException(status_code=400, detail="Invalid price_cents")

    post = Post(
        author_id=author_id,
        title=body.title,
        caption=body.caption,
        media_url=body.media_url,
        media_type=(body.media_type or "image").strip(),
        preview_url=body.preview_url,
        is_paid=body.is_paid,
        price_cents=price_cents,
        currency=currency,
        is_public=body.is_public,
        is_published=body.is_published,
    )

    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post

@app.get("/posts/me", response_model=list[PostOut])
async def get_my_posts(
    db: AsyncSession = Depends(get_session),
    token: TokenPayload = Depends(security.token_required(locations=["headers", "cookies"])),
):
    try:
        author_id = int(token.sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        select(Post).where(Post.author_id == author_id).order_by(Post.created_at.desc())
    )
    return list(result.scalars().all())

CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}

ALLOWED_PREFIXES = ("image/", "video/")
ALLOWED_EXT = set(CONTENT_TYPE_TO_EXT.values())

@app.post("/posts/upload")
async def upload_post_media(file: UploadFile = File(...)):
    ct = (file.content_type or "").lower().strip()
    if not ct or not ct.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail="Only image/video allowed")

    ext = Path(file.filename or "").suffix.lower()

    if ext not in ALLOWED_EXT:
        ext = CONTENT_TYPE_TO_EXT.get(ct, "")

    if not ext:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ct}")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = POST_DIR / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    dest_path.write_bytes(content)

    return {
        "media_url": f"/media/posts/{filename}",
        "media_type": "video" if ct.startswith("video/") else "image",
    }

@app.get("/posts/feed", response_model=list[PostOut])
async def get_feed_posts(
    limit: int = 30,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
    token: TokenPayload = Depends(security.token_required(locations=["headers", "cookies"])),
):
    try:
        me = int(token.sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    result = await db.execute(
        select(Post)
        .where(Post.is_published == True)
        .where(Post.is_public == True)
        .where(Post.author_id != me)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
