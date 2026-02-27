from fastapi import Depends, FastAPI, Form, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db
from model import User, Base
from starlette.middleware.sessions import SessionMiddleware
app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key="abcd",
)
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
@app.get("/login")
def login(request: Request,error: str=Query(None)):
    user = request.session.get('user')
    if user:
        return RedirectResponse(url="/",status_code=303)
    return templates.TemplateResponse("login.html", {"request": request,"error":error})

@app.post("/login")
def loginend(request:Request,id: int = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        return RedirectResponse(
            url="/login?error=User+not+found",
            status_code=303
        )
    request.session['user']=user.name
    return RedirectResponse(url="/",status_code=303)
# ---------- Home Page ----------
@app.get("/")
def get_front(request: Request):
    user=request.session.get('user')
    if not user:
        return RedirectResponse(url="/login",status_code=303)
    return templates.TemplateResponse("front.html", {"request": request, "messages": messages, "name": user})


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


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/login',status_code=303)