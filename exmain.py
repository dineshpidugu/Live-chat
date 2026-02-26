from fastapi import Depends, FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db
from model import User, Base

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

# ---------- WebSocket Manager ----------
messages = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket,name:str):
        await websocket.accept()
        await self.broadcast({"type":"Joined","name":name})
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()
templates = Jinja2Templates(directory="template")

# ---------- WebSocket ----------
@app.websocket("/w/{name}")
async def websocket_endpoint(websocket: WebSocket,name:str):
    await manager.connect(websocket,name)
    try:
        while True:
            data = await websocket.receive_json()
            messages.append(data)
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({"type":"Left","name":name})

# ---------- Login Page ----------
@app.get("/")
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ---------- Home Page ----------
@app.post("/home")
def get_front(request: Request, id: str = Form(...), db: Session = Depends(get_db)):
    id =int(id)
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
async def adduser(name:str,id:int ,db: Session = Depends(get_db)):   
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
@app.post('/chatwithai')
async def chatwithai(request:Request):
    from google import genai
    client = genai.Client()
    data = await request.json()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=data.get('content'),
    )
    return {"content": response.text}