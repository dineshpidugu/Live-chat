from fastapi import Depends, FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db
from model import User, Base
app = FastAPI()
Base.metadata.create_all(bind=engine)

# ---------- WebSocket Manager ----------
messages = []

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


manager = ConnectionManager()
templates = Jinja2Templates(directory="template")


# ---------- WebSocket ----------
@app.websocket("/w/{name}")
async def websocket_endpoint(websocket: WebSocket, name: str):
    await manager.connect(websocket, name)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "typing":
                # Handle typing indicator
                await manager.set_typing(name, data.get("is_typing", False))

            elif data.get("type") == "message":
                # Clear typing when message is sent
                await manager.set_typing(name, False)
                messages.append(data)
                await manager.broadcast(data)

    except WebSocketDisconnect:
        manager.disconnect(name)
        await manager.broadcast({"type": "Left", "name": name})
        await manager.broadcast_members()


# ---------- Login Page ----------
@app.get("/")
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# ---------- Home Page ----------
@app.post("/home")
def get_front(request: Request, id: str = Form(...), db: Session = Depends(get_db)):
    id = int(id)
    user = db.query(User).filter(User.id == id).first()
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "User not found"})
    return templates.TemplateResponse("front.html", {"request": request, "messages": messages, "name": user.name})


# ---------- DevTools Dummy ----------
@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def devtools_dummy():
    return JSONResponse(content={})


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


# ---------- AI Chat ----------
@app.post('/chatwithai')
async def chatwithai(request: Request):
    
    return "Not Yet Updated(Will Be Soooon)"