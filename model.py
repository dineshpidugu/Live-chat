from sqlalchemy import Column, Integer, String, BigInteger, JSON, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)


class Room(Base):
    __tablename__ = "room"

    id = Column(Integer, primary_key=True, index=True)
    roomname = Column(String, unique=True, nullable=False)
    password = Column(String)


class Chat(Base):
    __tablename__ = "chat"

    id = Column(BigInteger, primary_key=True)
    content = Column(JSON)


class UserRoom(Base):
    __tablename__ = "userroom"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    room_id = Column(Integer, ForeignKey("room.id"))