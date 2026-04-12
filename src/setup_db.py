import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from helper.db import get_db, create_collections

if __name__ == "__main__":
    print("🚀 Setting up MongoDB for Hiring Platform...")
    try:
        db = get_db()
        create_collections(db)
        print("✅ Done! MongoDB is ready.")
        print("\nCollections created:")
        for name in db.list_collection_names():
            count = db[name].count_documents({})
            print(f"  • {name} ({count} documents)")
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("💡 Make sure MongoDB is running: brew services start mongodb-community")