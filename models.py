from sqlalchemy import Column, Integer, String, BigInteger, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Users(Base):
    __tablename__="Users"
    id= Column(Integer,primary_key=True,index=True)
    username=Column(String)
    password=Column