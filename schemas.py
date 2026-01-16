from pydantic import BaseModel, EmailStr, model_validator, Field
from datetime import datetime

class UserLogin(BaseModel):
    password: str = Field(min_length=6, max_length=12)
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=25)

    @model_validator(mode="after")
    def check_login(self):
        if self.email is None and self.username is None:
            raise ValueError("Provide email or username")
        return self


class UserRegistration(BaseModel):
    username: str = Field(min_length=3, max_length=25)
    email: EmailStr
    password: str = Field(min_length=6, max_length=12)


class Verify(BaseModel):
    code: str = Field(min_length=4, max_length=4)

class RestorePassword(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=25)

    @model_validator(mode="after")
    def check_login(self):
        if self.email is None and self.username is None:
            raise ValueError("Provide email or username")
        return self

class RestorePasswordPatch(Verify):
    new_password: str = Field(min_length=6, max_length=12)

class PostCreate(BaseModel):
    title: str | None = None
    caption: str | None = None
    media_url: str
    media_type: str = "image"
    preview_url: str | None = None
    is_paid: bool = False
    price_cents: int | None = None
    currency: str = "USD"
    is_public: bool = True
    is_published: bool = True

class PostOut(BaseModel):
    id: int
    author_id: int
    title: str | None
    caption: str | None
    media_url: str
    media_type: str
    preview_url: str | None
    is_paid: bool
    price_cents: int | None
    currency: str
    is_public: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True