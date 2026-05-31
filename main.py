from typing import List
from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import Depends, FastAPI, Form, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db, SessionLocal
from model import User, Base, Chat ,Room,UserRoom
from starlette.middleware.sessions import SessionMiddleware
import redis.asyncio as redis
import asyncio
import json
from google import genai
from passlib.context import CryptContext

client = genai.Client()
chat = client.chats.create(model="gemini-2.5-flash")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Redis subscriber...")
    asyncio.create_task(manager.redis_subscriber())
    yield
    print("Application shutting down")

# ---------- FastAPI App ----------
app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="abcd")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="template")

# ---------- Redis Setup ----------
PUBSUB_CHANNEL = "chat_channel"
redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

# ---------- WebSocket Manager ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, name: str):
        await websocket.accept()
        self.active_connections[name] = websocket

        await redis_client.publish(PUBSUB_CHANNEL, json.dumps({
            "type": "Joined",
            "name": name
        }))

        await redis_client.sadd("online_users", name)
        members = list(await redis_client.smembers("online_users"))
        await websocket.send_json({
            "type": "online_members",
            "members": members
        })

        await redis_client.publish(PUBSUB_CHANNEL, json.dumps({
            "type": "online_members",
            "members": members
        }))

    async def disconnect(self, name: str):
        self.active_connections.pop(name, None)

        await redis_client.srem("online_users", name)
        members = list(await redis_client.smembers("online_users"))

        await redis_client.publish(PUBSUB_CHANNEL, json.dumps({
            "type": "Left",
            "name": name
        }))
        await redis_client.publish(PUBSUB_CHANNEL, json.dumps({
            "type": "online_members",
            "members": members
        }))

    async def set_typing(self, name: str, is_typing: bool):

        if is_typing:
            await redis_client.sadd("typing_users", name)
        else:
            await redis_client.srem("typing_users", name)

        typing_users = list(await redis_client.smembers("typing_users"))
        await redis_client.publish(PUBSUB_CHANNEL, json.dumps({
            "type": "typing",
            "typing_users": typing_users
        }))

    async def broadcast_local(self, message: dict):

        for ws in list(self.active_connections.values()):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def redis_subscriber(self):
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(PUBSUB_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self.broadcast_local(data)   

    def save_to_db(self, data: dict):
        db: Session = next(get_db())
        try:
            new_chat = Chat(content=data)
            db.add(new_chat)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to save message: {e}")
        finally:
            db.close()

manager = ConnectionManager()

# ---------- WebSocket Endpoint ----------
@app.websocket("/w/{name}")
async def websocket_endpoint(websocket: WebSocket, name: str):
    await manager.connect(websocket, name)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "typing":
                await manager.set_typing(name, data.get("is_typing", False))

            elif data.get("type") == "message":
                await manager.set_typing(name, False)
                await redis_client.publish(PUBSUB_CHANNEL, json.dumps(data))
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, manager.save_to_db, data)

    except WebSocketDisconnect:
        await manager.disconnect(name)   


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(password, hashed_password):
    return pwd_context.verify(password, hashed_password)

def hash_password(password: str):
    return pwd_context.hash(password)

# ---------- Login Pages ----------
@app.get("/login")
def login(request: Request, error: str = Query(None)):
    user = request.session.get("name")
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
def loginend(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        return RedirectResponse(url="/login?error=User+not+found", status_code=303)
    request.session["name"] = user.name
    request.session["username"]=username
    return RedirectResponse(url="/", status_code=303)

# ---------- Home Page ----------
@app.get("/")
def get_front(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("name")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    contents: List[dict] = db.query(Chat.content).order_by(Chat.id.asc()).limit(50).all()
    contents = [c[0] for c in contents]
    return templates.TemplateResponse("front.html", {
        "request": request,
        "messages": contents,
        "name": user
    })

@app.post("/create_room")
def create_room(request: Request,room_name: str =Form(...), Password: str = Form(...), db: Session = Depends(get_db)):
    new_room=Room(roomname=room_name,password=hash_password(Password))
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    db.add(UserRoom(username=request.session.get("username"),room_id=new_room.id,room_name=new_room.roomname))
    db.commit()
    return JSONResponse(content={"status":"success","message":"new Chat Room has been created"})

@app.post("/join_room")
def join_room(request: Request,room_name: str =Form(...), Password: str = Form(...), db: Session = Depends(get_db)):
    existing_room=db.query(Room).filter(Room.roomname==room_name).first()
    if not existing_room or verify_password(Password,existing_room.password):
        return JSONResponse(content={"status":"Failed","message": "room may not exist or incorrect password"})
    db.add(UserRoom(username=request.session.get("username"),room_id=existing_room.id,room_name=existing_room.roomname))
    db.commit()
    return JSONResponse(content={"status":"success","message":"Joined Successfully"})


# ---------- Add User ----------
@app.post("/adduser")
async def adduser(name: str, username: str, password: str, db: Session = Depends(get_db)):
    if not name or not username:
        return JSONResponse(content={"error": "Name and username required"}, status_code=400)
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return JSONResponse(content={"error": "User already exists"}, status_code=400)
    new_user = User(name=name, username=username, password=hash_password(password=password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return JSONResponse(content={"id": new_user.id, "name": new_user.name, "message": "User added successfully"})

# ---------- AI Chat ----------
@app.post("/chatwithai")
async def chatwithai(request: Request):
    body = await request.json()
    user_prompt = body.get("content", "")
    response_text = chat.send_message(user_prompt).text
    return JSONResponse(content={"content": response_text})

# ---------- Logout ----------
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/clear_chat", response_model=None)
def clear_chat():
    db = SessionLocal()
    num_deleted = db.query(Chat).delete()
    db.commit()
    return {"message": f"Deleted {num_deleted} messages"}

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def devtools_dummy():
    return JSONResponse(content={})

@app.get("/health")
def health_check():
    return {"status": "ok"}