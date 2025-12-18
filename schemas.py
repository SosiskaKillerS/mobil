from pydantic import BaseModel, EmailStr, model_validator

class UserLogin(BaseModel):
    password: str
    email: EmailStr | None = None
    username: str | None = None

    @model_validator(mode="after")
    def check_login(self):
        if self.email is None and self.username is None:
            raise ValueError
        return self

class UserRegistration(BaseModel):
    username: str
    email: EmailStr
    password: str


