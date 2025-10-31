from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.context import CryptContext
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Bank API")

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# PostgreSQL connection
def get_db():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "bank_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "root"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

# Initialize database
def init_db():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "bank_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "root")
    )
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            account_number VARCHAR(20) UNIQUE NOT NULL,
            balance DECIMAL(15, 2) DEFAULT 0.00,
            account_type VARCHAR(20) DEFAULT 'savings',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES accounts(id),
            transaction_type VARCHAR(20) NOT NULL,
            amount DECIMAL(15, 2) NOT NULL,
            description VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

# Pydantic models
class UserRegister(BaseModel):
    username: str
    password: str
    full_name: str

class UserLogin(BaseModel):
    username: str
    password: str

class Transaction(BaseModel):
    account_id: int
    transaction_type: str
    amount: float
    description: Optional[str] = None

class Transfer(BaseModel):
    from_account: str
    to_account: str
    amount: float
    description: Optional[str] = None

# API endpoints
@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
def root():
    return {"message": "Bank API is running!"}

@app.post("/register")
def register(user: UserRegister, conn=Depends(get_db)):
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username = %s", (user.username,))
    if cur.fetchone():
        raise HTTPException(status_code=400, detail="User already exists")

    password_hash = pwd_context.hash(user.password)
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name) VALUES (%s, %s, %s) RETURNING id",
        (user.username, password_hash, user.full_name)
    )
    user_id = cur.fetchone()['id']

    import random
    account_number = f"KZ{random.randint(1000000000000000, 9999999999999999)}"
    cur.execute(
        "INSERT INTO accounts (user_id, account_number, balance) VALUES (%s, %s, %s)",
        (user_id, account_number, 1000.00)
    )

    conn.commit()
    cur.close()

    return {"message": "Registration successful", "account_number": account_number}

@app.post("/login")
def login(user: UserLogin, conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (user.username,))
    db_user = cur.fetchone()

    if not db_user or not pwd_context.verify(user.password, db_user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    cur.close()
    return {"message": "Login successful", "user_id": db_user['id'], "username": db_user['username']}

@app.get("/accounts/{user_id}")
def get_accounts(user_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE user_id = %s", (user_id,))
    accounts = cur.fetchall()
    cur.close()
    return {"accounts": accounts}

@app.get("/transactions/{account_id}")
def get_transactions(account_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM transactions WHERE account_id = %s ORDER BY created_at DESC LIMIT 50",
        (account_id,)
    )
    transactions = cur.fetchall()
    cur.close()
    return {"transactions": transactions}

@app.post("/transaction")
def create_transaction(trans: Transaction, conn=Depends(get_db)):
    cur = conn.cursor()

    cur.execute("SELECT balance FROM accounts WHERE id = %s", (trans.account_id,))
    account = cur.fetchone()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    current_balance = float(account['balance'])

    if trans.transaction_type == 'withdrawal' and current_balance < trans.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    new_balance = current_balance + trans.amount if trans.transaction_type == 'deposit' else current_balance - trans.amount
    cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_balance, trans.account_id))

    cur.execute(
        "INSERT INTO transactions (account_id, transaction_type, amount, description) VALUES (%s, %s, %s, %s)",
        (trans.account_id, trans.transaction_type, trans.amount, trans.description)
    )

    conn.commit()
    cur.close()
    return {"message": "Transaction successful", "new_balance": new_balance}

@app.post("/transfer")
def transfer(trans: Transfer, conn=Depends(get_db)):
    cur = conn.cursor()

    cur.execute("SELECT * FROM accounts WHERE account_number = %s", (trans.from_account,))
    from_acc = cur.fetchone()

    cur.execute("SELECT * FROM accounts WHERE account_number = %s", (trans.to_account,))
    to_acc = cur.fetchone()

    if not from_acc or not to_acc:
        raise HTTPException(status_code=404, detail="Account not found")

    if float(from_acc['balance']) < trans.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    cur.execute(
        "UPDATE accounts SET balance = balance - %s WHERE id = %s",
        (trans.amount, from_acc['id'])
    )
    cur.execute(
        "INSERT INTO transactions (account_id, transaction_type, amount, description) VALUES (%s, %s, %s, %s)",
        (from_acc['id'], 'transfer_out', trans.amount, f"Transfer to {trans.to_account}")
    )

    cur.execute(
        "UPDATE accounts SET balance = balance + %s WHERE id = %s",
        (trans.amount, to_acc['id'])
    )
    cur.execute(
        "INSERT INTO transactions (account_id, transaction_type, amount, description) VALUES (%s, %s, %s, %s)",
        (to_acc['id'], 'transfer_in', trans.amount, f"Transfer from {trans.from_account}")
    )

    conn.commit()
    cur.close()
    return {"message": "Transfer completed successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
