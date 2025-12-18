from pydantic import BaseModel, EmailStr, model_validator, Field

class UserLogin(BaseModel):
    password: str = Field(min_length=6, max_length=12)
    email: EmailStr | None = Field(min_length=5)
    username: str = Field(min_length=3, max_length=25)

    @model_validator(mode="after")
    def check_login(self):
        if self.email is None and self.username is None:
            raise ValueError
        return self

class UserRegistration(BaseModel):
    username: str = Field(min_length=3, max_length=25)
    email: EmailStr = Field(min_length=5)
    password: str = Field(min_length=6, max_length=12)


class Verify(BaseModel):
    code: str = Field(min_length=4, max_length=4)
