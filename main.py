from fastapi import FastAPI, Request, Depends, HTTPException, WebSocket,WebSocketDisconnect, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import SessionLocal, engine, Base
from typing import List
from sqlalchemy.orm import aliased
import crud, models
from database import SessionLocal, engine
from crud import get_last_messages_with_names
from models import Message, Contact
from sqlalchemy import desc



app = FastAPI()
VERIFY_TOKEN = "saiganga"
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup():
    models.Base.metadata.create_all(bind=engine)



active_connections = []

@app.get("/webhook")
async def verify(request: Request):
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    return PlainTextResponse(content="Invalid token", status_code=403)

@app.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        print("✅ Incoming Webhook:", body)

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                
                if "messages" in value:
                    for msg in value["messages"]:
                        crud.create_message(
                            db,
                            sender=msg["from"],
                            receiver=metadata.get("display_phone_number"),
                            message=msg["text"]["body"],
                            is_from_user=False,
                        )
                if "statuses" in value:
                    for status in value["statuses"]:
                        crud.create_message(
                            db,
                            sender=metadata.get("display_phone_number"),
                            receiver=status["recipient_id"],
                            message="(sent message)",
                            is_from_user=True,
                        )

        return JSONResponse(content={"status": "received"}, status_code=200)
    except Exception as e:
        print("❌ Webhook error:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)
    





# Dependency to get DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic schemas with Pydantic v2 style config
class ContactBase(BaseModel):
    name: str
    phone: str

class ContactOut(ContactBase):
    id: int

    class Config:
        from_attributes = True  # Pydantic v2 ORM support

class ContactBatch(BaseModel):
    contacts: List[ContactBase]

# Routes with response_model and proper DB session injection

@app.get("/api/contacts", response_model=List[ContactOut])
def get_contacts(db: Session = Depends(get_db)):
    contacts = db.query(models.Contact).all()
    return contacts

@app.post("/api/contacts", response_model=ContactOut)
def add_contact(contact: ContactBase, db: Session = Depends(get_db)):
    phone = contact.phone.strip()
    if not phone.startswith("91"):
        phone = "91" + phone
    db_contact = models.Contact(name=contact.name, phone=phone)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@app.post("/api/contacts/batch")
def batch_add_contacts(payload: ContactBatch, db: Session = Depends(get_db)):
    formatted = []
    for c in payload.contacts:
        phone = c.phone.strip()
        if not phone.startswith("91"):
            phone = "91" + phone
        formatted.append(models.Contact(name=c.name, phone=phone))
    db.add_all(formatted)
    db.commit()
    return {"added": len(formatted)}

@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"detail": "Deleted"}

@app.get("/api/conversations")
def get_conversations(db: Session = Depends(get_db)):
    users = db.query(Message.sender).filter(Message.sender != "15556566971").union(
        db.query(Message.receiver).filter(Message.receiver != "15556566971")
    ).distinct().all()

    conversations = []
    for (user,) in users:
        last_msg = db.query(Message).filter(
            (Message.sender == user) | (Message.receiver == user)
        ).order_by(desc(Message.timestamp)).first()

        # 👇 Match contact by phone
        contact = db.query(Contact).filter(Contact.phone == user).first()
        name = contact.name if contact else None

        conversations.append({
            "user_id": user,
            "name": name,
            "last_message": last_msg.message,
            "last_timestamp": last_msg.timestamp
        })

    conversations.sort(key=lambda x: x["last_timestamp"], reverse=True)
    return conversations

@app.get("/api/conversations/{user_id}")
def read_full_conversation(user_id: str, db: Session = Depends(get_db)):
    messages = crud.get_full_conversation(db, user_id)
    return[
        {
            "sender": m.sender,
            "receiver": m.receiver,
            "message": m.message,
            "timestamp": m.timestamp.isoformat(),
            "from_user": m.is_from_user,
        }
        for m in messages
    ]


@app.get("/api/messages/last")
def get_last_messages(db: Session = Depends(get_db)):
    return get_last_messages_with_names(db)