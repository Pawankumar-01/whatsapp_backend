from pydantic import BaseModel

class ContactCreate(BaseModel):
    name: str
    phone: str

class ContactResponse(ContactCreate):
    id: int

    class Config:
        orm_mode = True