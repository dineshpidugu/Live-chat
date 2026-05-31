from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends , Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

fake_users_db = {
    "dinesh": {
        "username": "dinesh",
        "hashed_password": pwd_context.hash("1229")
    }
}


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_token(data: dict, expire_time: timedelta = None):
    to_encode = data.copy()

    expire = datetime.utcnow() + (expire_time or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode.update({"exp": expire})

    jwt_token = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return jwt_token


def user_authenticate(username, password):
    user = fake_users_db.get(username)

    if not user:
        return False

    if not verify_password(password, user["hashed_password"]):   # FIXED
        return False

    return user


app = FastAPI()

origins = [
    "http://localhost:5173",  # Vite React
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from fastapi import WebSocket, WebSocketDisconnect
class ConnectionManager:
    def __init__(self):
        self.active_members: dict[str,WebSocket]={}
        self.active_chatroom

    async def connect(self,websocket: WebSocket,user_name:str):
        await websocket.accept()
        self.active_members[user_name]=WebSocket
        await websocket.send_json({"type":"data",})

    async def disconnect(self,username):
        self.active_members.pop(username, None)

    async def broadcast(self,room_name,message,websocket:WebSocket):
        for i in self.active_members[room_name]-set(websocket):
            i.send_json(message)
    
    
    


@app.post('/login')
def login(request: Request ,form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_authenticate(
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    access_token = create_token(
        data={"sub": user["username"]},   # FIXED
        expire_time=timedelta(minutes=30)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }