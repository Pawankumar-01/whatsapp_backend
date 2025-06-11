from pydantic import BaseModel

class ContactCreate(BaseModel):
    name: str
    phone: str

class ContactResponse(ContactCreate):
    id: int

    class Config:
        orm_mode = True





class TemplateCreate(BaseModel):
    content: str

class TemplateRead(BaseModel):
    id: int
    content: str
    class Config:
        from_attributes = True 

class ContactRead(BaseModel):
    id: int
    name: str
    phone: str
    class Config:
       from_attributes = True 