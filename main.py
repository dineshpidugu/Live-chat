from typing import List
from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import Depends, FastAPI, Form, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db, SessionLocal
from model import User, Base,Chat
from starlette.middleware.sessions import SessionMiddleware
import redis.asyncio as redis
import asyncio
import json
from google import genai

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
Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="template")

# ---------- Redis Setup ----------
PUBSUB_CHANNEL = "chat_channel"
redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

# ---------- WebSocket Manager ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.typing_users: set[str] = set()

    async def connect(self, websocket: WebSocket, name: str):
        await websocket.accept()
        self.active_connections[name] = websocket
        await self.broadcast({"type": "Joined", "name": name})
        await websocket.send_json({
            "type": "online_members",
            "members": self.get_members()
        })
        await self.broadcast_members()

    def disconnect(self, name: str):
        self.active_connections.pop(name, None)
        self.typing_users.discard(name)

    def get_members(self) -> list[str]:
        return list(self.active_connections.keys())

    async def broadcast(self, message: dict):
        for ws in list(self.active_connections.values()):
            try:
                await ws.send_json(message)
            except:
                pass

    async def broadcast_members(self):
        await self.broadcast({
            "type": "online_members",
            "members": self.get_members()
        })

    async def set_typing(self, name: str, is_typing: bool):
        if is_typing:
            self.typing_users.add(name)
        else:
            self.typing_users.discard(name)
        await self.broadcast({
            "type": "typing",
            "typing_users": list(self.typing_users)
        })

    # Redis subscriber task
    async def redis_subscriber(self):
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(PUBSUB_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self.broadcast(data)
                # messages.append(data)
                

    def save_to_db(self, data: dict):
        db: Session = next(get_db())
        try:
            new_user = Chat(content=data)
            db.add(new_user)
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
        manager.disconnect(name)
        await manager.broadcast({"type": "Left", "name": name})
        await manager.broadcast_members()

# ---------- Login Pages ----------
@app.get("/login")
def login(request: Request, error: str = Query(None)):
    user = request.session.get("user")
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
def loginend(request: Request, id: int = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        return RedirectResponse(url="/login?error=User+not+found", status_code=303)
    request.session["user"] = user.name
    return RedirectResponse(url="/", status_code=303)

# ---------- Home Page ----------
@app.get("/")
def get_front(request: Request,db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    # messages: List[Chat] = db.query(Chat).order_by(Chat.id.asc()).limit(50).all()
    contents: List[dict] = db.query(Chat.content).order_by(Chat.id.asc()).limit(50).all()
    contents = [c[0] for c in contents]
    return templates.TemplateResponse(
        "front.html",
        {
            "request": request,
            "messages": contents,
            "name": user
        })
# ---------- Add User ----------
@app.post("/adduser/{id}/{name}")
async def adduser(name: str, id: int, db: Session = Depends(get_db)):
    if not name or not id:
        return JSONResponse(content={"error": "Name and ID required"}, status_code=400)
    existing = db.query(User).filter(User.id == id).first()
    if existing:
        return JSONResponse(content={"error": "User already exists"}, status_code=400)
    new_user = User(name=name, id=id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return JSONResponse(content={"id": new_user.id, "name": new_user.name, "message": "User added successfully"})

# ---------- AI Chat (dummy) ----------
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
    db=SessionLocal()
    num_deleted = db.query(Chat).delete()
    db.commit()
    return {"message": f"Deleted {num_deleted} messages"}

# ---------- DevTools Dummy ----------
@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def devtools_dummy():
    return JSONResponse(content={})


# @app.get("/create_room/{name}")
# async def create_room(name:str):

from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}