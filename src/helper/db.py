import os
import copy
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

# ─── Connection ───────────────────────────────────────────

_client = None
_db     = None

def get_db():
    global _client, _db
    if _db is not None:
        return _db

    uri  = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    name = os.environ.get("MONGODB_DB",  "hiring_platform")

    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    _db     = _client[name]

    # Test connection
    _client.admin.command("ping")
    print(f"  ✅ Connected to MongoDB: {name}")
    return _db

def close_db():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db     = None
        print("  ✅ MongoDB connection closed")

# ─── Schema Validator ─────────────────────────────────────

STUDENT_PROFILE_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id",
            "created_at",
            "updated_at",
            "candidate",
            "skills",
            "sources_used"
        ],
        "properties": {

            "user_id": {
                "bsonType":    "objectId",
                "description": "Reference to users._id"
            },
            "created_at": {
                "bsonType": "date"
            },
            "updated_at": {
                "bsonType": "date"
            },
            "agent_version": {
                "bsonType": "string"
            },

            "candidate": {
                "bsonType": "object",
                "required": ["name", "email"],
                "properties": {
                    "name":     {"bsonType": "string"},
                    "email":    {"bsonType": "string"},
                    "phone":    {"bsonType": ["string", "null"]},
                    "location": {"bsonType": ["string", "null"]},
                    "summary":  {"bsonType": ["string", "null"]}
                }
            },

            "skills": {
                "bsonType": "object",
                "properties": {
                    "all":            {"bsonType": "array"},
                    "from_resume":    {"bsonType": "array"},
                    "from_github":    {"bsonType": "array"},
                    "from_portfolio": {"bsonType": "array"},
                    "from_code":      {"bsonType": "array"}
                }
            },

            "experience": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "properties": {
                        "company":     {"bsonType": ["string", "null"]},
                        "role":        {"bsonType": ["string", "null"]},
                        "duration":    {"bsonType": ["string", "null"]},
                        "location":    {"bsonType": ["string", "null"]},
                        "description": {"bsonType": ["string", "null"]}
                    }
                }
            },

            "education": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "properties": {
                        "institution": {"bsonType": ["string", "null"]},
                        "degree":      {"bsonType": ["string", "null"]},
                        "field":       {"bsonType": ["string", "null"]},
                        "year":        {"bsonType": ["string", "null"]}
                    }
                }
            },

            "certifications": {
                "bsonType": "array",
                "items":    {"bsonType": "string"}
            },

            "projects": {
                "bsonType": "object",
                "properties": {
                    "from_resume": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "properties": {
                                "name":         {"bsonType": ["string", "null"]},
                                "description":  {"bsonType": ["string", "null"]},
                                "technologies": {"bsonType": "array"}
                            }
                        }
                    },
                    "from_github": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "properties": {
                                "name":          {"bsonType": ["string", "null"]},
                                "description":   {"bsonType": ["string", "null"]},
                                "technologies":  {"bsonType": "array"},
                                "source":        {"bsonType": ["string", "null"]},
                                "stars":         {"bsonType": ["int", "long", "double", "null"]},
                                "forks":         {"bsonType": ["int", "long", "double", "null"]},
                                "commit_count":  {"bsonType": ["int", "long", "double", "null"]},
                                "last_updated":  {"bsonType": ["date", "string", "null"]},
                                "readme":        {"bsonType": ["string", "null"]},
                                "topics":        {"bsonType": "array"},
                                "has_live_demo": {"bsonType": ["bool", "null"]},
                                "homepage":      {"bsonType": ["string", "null"]},
                                "is_fork":       {"bsonType": ["bool", "null"]},
                                "code_samples":  {"bsonType": "object"},
                                "code_insights": {"bsonType": "object"}
                            }
                        }
                    },
                    "from_portfolio": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "properties": {
                                "name":         {"bsonType": ["string", "null"]},
                                "description":  {"bsonType": ["string", "null"]},
                                "technologies": {"bsonType": "array"},
                                "link":         {"bsonType": ["string", "null"]}
                            }
                        }
                    }
                }
            },

            "github_profile": {
                "bsonType": "object",
                "properties": {
                    "username":     {"bsonType": ["string", "null"]},
                    "bio":          {"bsonType": ["string", "null"]},
                    "website":      {"bsonType": ["string", "null"]},
                    "followers":    {"bsonType": ["int", "long", "double", "null"]},
                    "following":    {"bsonType": ["int", "long", "double", "null"]},
                    "public_repos": {"bsonType": ["int", "long", "double", "null"]},
                    "github_url":   {"bsonType": ["string", "null"]},
                    "top_repos": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "properties": {
                                "name":           {"bsonType": ["string", "null"]},
                                "description":    {"bsonType": ["string", "null"]},
                                "languages":      {"bsonType": "array"},
                                "stars":          {"bsonType": ["int", "long", "double", "null"]},
                                "forks":          {"bsonType": ["int", "long", "double", "null"]},
                                "commit_count":   {"bsonType": ["int", "long", "double", "null"]},
                                "last_updated":   {"bsonType": ["date", "string", "null"]},
                                "readme_preview": {"bsonType": ["string", "null"]},
                                "topics":         {"bsonType": "array"},
                                "has_live_demo":  {"bsonType": ["bool", "null"]},
                                "homepage":       {"bsonType": ["string", "null"]},
                                "is_fork":        {"bsonType": ["bool", "null"]},
                                "code_samples":   {"bsonType": "object"},
                                "code_insights":  {"bsonType": "object"}
                            }
                        }
                    }
                }
            },

            "code_analysis": {
                "bsonType": "object",
                "properties": {
                    "repos_analyzed":        {"bsonType": ["int", "long", "double"]},
                    "skills_from_code":      {"bsonType": "array"},
                    "architecture_patterns": {"bsonType": "array"},
                    "best_practices":        {"bsonType": "array"}
                }
            },

            "portfolio": {
                "bsonType": "object",
                "properties": {
                    "url":        {"bsonType": ["string", "null"]},
                    "headings":   {"bsonType": "array"},
                    "structured": {"bsonType": "object"}
                }
            },

            "links": {
                "bsonType": "object",
                "properties": {
                    "github":    {"bsonType": ["string", "null"]},
                    "portfolio": {"bsonType": ["string", "null"]},
                    "linkedin":  {"bsonType": ["string", "null"]}
                }
            },

            "sources_used": {
                "bsonType": "object",
                "required": ["resume", "github", "portfolio", "code_analysis"],
                "properties": {
                    "resume":        {"bsonType": "bool"},
                    "github":        {"bsonType": "bool"},
                    "portfolio":     {"bsonType": "bool"},
                    "code_analysis": {"bsonType": "bool"}
                }
            }
        }
    }
}

# ─── Collection Setup ─────────────────────────────────────

def create_collections(db):
    existing = db.list_collection_names()
    print(f"\n  📦 Setting up MongoDB collections...")

    if "student_profiles" not in existing:
        db.create_collection(
            "student_profiles",
            validator=STUDENT_PROFILE_VALIDATOR,
            validationLevel="moderate",
            validationAction="warn"
        )
        print("  ✅ Created: student_profiles")
    else:
        print("  ℹ️  Exists:  student_profiles")

    if "users" not in existing:
        db.create_collection("users")
        print("  ✅ Created: users")
    else:
        print("  ℹ️  Exists:  users")

    if "resumes" not in existing:
        db.create_collection("resumes")
        print("  ✅ Created: resumes")
    else:
        print("  ℹ️  Exists:  resumes")

    if "agent_logs" not in existing:
        db.create_collection("agent_logs")
        print("  ✅ Created: agent_logs")
    else:
        print("  ℹ️  Exists:  agent_logs")

    _create_indexes(db)
    print("  ✅ MongoDB setup complete\n")


def _create_indexes(db):

    # student_profiles indexes
    db.student_profiles.create_index(
        [("user_id", ASCENDING)],
        unique=True,
        name="idx_user_id_unique"
    )
    db.student_profiles.create_index(
        [("candidate.email", ASCENDING)],
        name="idx_candidate_email"
    )
    db.student_profiles.create_index(
        [("candidate.name", ASCENDING)],
        name="idx_candidate_name"
    )
    db.student_profiles.create_index(
        [("skills.all", ASCENDING)],
        name="idx_skills_all"
    )
    db.student_profiles.create_index(
        [("skills.from_resume", ASCENDING)],
        name="idx_skills_from_resume"
    )
    db.student_profiles.create_index(
        [("candidate.location", ASCENDING)],
        name="idx_location"
    )
    db.student_profiles.create_index(
        [("created_at", DESCENDING)],
        name="idx_created_at"
    )
    db.student_profiles.create_index(
        [("github_profile.username", ASCENDING)],
        name="idx_github_username",
        sparse=True
    )
    db.student_profiles.create_index(
        [("code_analysis.repos_analyzed", DESCENDING)],
        name="idx_repos_analyzed"
    )
    db.student_profiles.create_index(
        [("sources_used.github", ASCENDING)],
        name="idx_sources_github"
    )
    db.student_profiles.create_index(
        [("sources_used.code_analysis", ASCENDING)],
        name="idx_sources_code_analysis"
    )

    # agent_logs indexes
    db.agent_logs.create_index(
        [("user_id", ASCENDING)],
        name="idx_log_user_id"
    )
    db.agent_logs.create_index(
        [("agent", ASCENDING), ("status", ASCENDING)],
        name="idx_log_agent_status"
    )
    db.agent_logs.create_index(
        [("created_at", DESCENDING)],
        name="idx_log_created_at"
    )

    print("  ✅ Indexes created")

# ─── Date Converter ───────────────────────────────────────

def _convert_dates(profile):
    profile = copy.deepcopy(profile)

    def parse_date(val):
        if isinstance(val, str) and "T" in val and val.endswith("Z"):
            try:
                return datetime.fromisoformat(
                    val.replace("Z", "+00:00")
                )
            except:
                return val
        return val

    def convert_obj(obj):
        if isinstance(obj, dict):
            return {k: convert_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_obj(i) for i in obj]
        else:
            return parse_date(obj)

    return convert_obj(profile)

# ─── Save Profile ─────────────────────────────────────────

def save_student_profile(unified_profile, user_id=None):
    db  = get_db()
    now = datetime.now(timezone.utc)

    if user_id is None:
        user_id = ObjectId()
    else:
        user_id = ObjectId(user_id)

    # Convert date strings to ISODate
    profile = _convert_dates(unified_profile)

    # Add meta fields
    profile["user_id"]       = user_id
    profile["updated_at"]    = now
    profile["agent_version"] = "1.0"

    # Upsert — update if exists, insert if not
    existing = db.student_profiles.find_one(
        {"user_id": user_id}
    )

    if existing:
        db.student_profiles.update_one(
            {"user_id": user_id},
            {"$set": profile}
        )
        profile_id = existing["_id"]
        print(f"  ✅ Updated profile in MongoDB: {profile_id}")
    else:
        profile["created_at"] = now
        result     = db.student_profiles.insert_one(profile)
        profile_id = result.inserted_id
        print(f"  ✅ Inserted profile in MongoDB: {profile_id}")

    # Log the run
    _log_agent_run(db, user_id, profile_id, unified_profile, now)

    return profile_id


def _log_agent_run(db, user_id, profile_id, profile, now):
    sources = profile.get("sources_used", {})

    db.agent_logs.insert_one({
        "user_id":      user_id,
        "profile_id":   profile_id,
        "agent":        "agent1",
        "status":       "success",
        "created_at":   now,
        "completed_at": now,
        "input": {
            "candidate_name":  profile.get("candidate", {}).get("name"),
            "candidate_email": profile.get("candidate", {}).get("email")
        },
        "output": {
            "profile_id": profile_id
        },
        "sources_used": sources,
        "stats": {
            "total_skills":     len(profile.get("skills", {}).get("all", [])),
            "resume_skills":    len(profile.get("skills", {}).get("from_resume", [])),
            "github_languages": len(profile.get("skills", {}).get("from_github", [])),
            "code_skills":      len(profile.get("skills", {}).get("from_code", [])),
            "total_repos":      len(profile.get("projects", {}).get("from_github", [])),
            "repos_analyzed":   profile.get("code_analysis", {}).get("repos_analyzed", 0),
            "experience_count": len(profile.get("experience", [])),
            "education_count":  len(profile.get("education", [])),
            "resume_projects":  len(profile.get("projects", {}).get("from_resume", [])),
            "certifications":   len(profile.get("certifications", []))
        }
    })