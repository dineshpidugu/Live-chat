from sqlalchemy import Column, Integer, String, BigInteger, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    username=Column(String)
    password=Column(String)
class Room(Base):
    __tablename__="room"

    id=Column(Integer,primary_key=True,index=True)
    roomname=Column(String)
    # chatid=Column(Integer)
    password=Column(Integer)

class Chat(Base):
    __tablename__ = "chat"  
    id = Column(BigInteger, primary_key=True)
    content = Column(JSON)

class UserRoom(Base):
    __tablename__ ="userroom"

    user_name = Column(Integer)
    room_id = Column(Integer)
    room_name = Column(String)