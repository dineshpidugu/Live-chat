from sqlalchemy import Column, Integer, String, BigInteger, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
class Room(Base):
    __tablename__="room"

    id=Column(Integer,primary_key=True,index=True)
    password=Column(Integer)

class Chat(Base):
    __tablename__ = "chat"  # lowercase
    id = Column(BigInteger, primary_key=True)
    content = Column(JSON)