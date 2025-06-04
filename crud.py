from sqlalchemy.orm import Session
from models import Message, Contact
from sqlalchemy import or_, desc
from datetime import datetime
from schemas import ContactCreate
from sqlalchemy import func


def get_conversations(db: Session):
    # Get distinct user IDs involved in conversations (excluding "you")
    users = db.query(Message.sender).filter(Message.sender != "15556566971").union(
        db.query(Message.receiver).filter(Message.receiver != "15556566971")
    ).distinct().all()
    
    conversations = []
    for (user,) in users:
        # Get latest message for that user
        last_msg = db.query(Message).filter(
            (Message.sender == user) | (Message.receiver == user)
        ).order_by(desc(Message.timestamp)).first()
        
        # Get contact name if exists
        contact = db.query(Contact).filter(Contact.phone == user).first()
        name = contact.name if contact else None

        conversations.append({
            "user_id": user,
            "name": name,
            "last_message": last_msg.message,
            "last_timestamp": last_msg.timestamp
        })

    # Sort by timestamp
    conversations.sort(key=lambda x: x["last_timestamp"], reverse=True)
    return conversations

def create_message(db: Session, sender: str, receiver: str, message: str, is_from_user: bool):
    db_message = Message(
        sender=sender,
        receiver=receiver,
        message=message,
        is_from_user=is_from_user,
        timestamp=datetime.utcnow(),
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def get_full_conversation(db: Session, user_id: str):
    return db.query(Message).filter(
        (Message.sender == user_id) | (Message.receiver == user_id)
    ).order_by(Message.timestamp).all()


def create_contact(db: Session, contact: ContactCreate):
    db_contact = Contact(name=contact.name, phone=contact.phone)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def get_contacts(db: Session):
    return db.query(Contact).all()

def delete_contact(db: Session, contact_id: int):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if contact:
        db.delete(contact)
        db.commit()
        return True
    return False


# message_crud.py
def get_last_messages_with_names(db: Session):
    subquery = (
        db.query(
            Message.phone_number,
            func.max(Message.timestamp).label("last_time")
        )
        .group_by(Message.phone_number)
        .subquery()
    )

    results = (
        db.query(Message, Contact.name)
        .join(subquery, (Message.phone_number == subquery.c.phone_number) & (Message.timestamp == subquery.c.last_time))
        .outerjoin(Contact, Message.phone_number == Contact.phone)
        .all()
    )

    return [
        {
            "phone_number": msg.phone_number,
            "text": msg.text,
            "timestamp": msg.timestamp,
            "name": name
        }
        for msg, name in results
    ]
