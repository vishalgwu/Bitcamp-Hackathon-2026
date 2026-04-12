# seed_employers.py — run this ONCE: python seed_employers.py
import os
from pymongo import MongoClient
import bcrypt
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(uri)
db = client["hiring_platform"]

employers = [
    {
        "full_name": "Siddharth Saravanan",
        "email": "sid@company1.com",
        "password": bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
        "company_name": "Company1",
        "company_size": "51-200",
        "industry": "Technology",
        "created_at": datetime.utcnow()
    },
    {
        "full_name": "Ashwin Balaji",
        "email": "ashwin@innovate.io",
        "password": bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
        "company_name": "Company2",
        "company_size": "11-50",
        "industry": "Technology",
        "created_at": datetime.utcnow()
    }
]

db["employers"].insert_many(employers)
print("Seeded 2 employers. Login with password: password123")