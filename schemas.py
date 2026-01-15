from pydantic import BaseModel, EmailStr, model_validator, Field

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

