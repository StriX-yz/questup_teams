from flask import Flask, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import random

# ------------------------------
# CONFIG
# ------------------------------
MONGO_URI = "mongodb+srv://yazidmoundher_db_user:L9chQ2YsVoEITXIl@cluster0.siqi7ho.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["questup"]
event_emails = db["event_emails"]
teams_collection = db["teams"]

DEPARTMENT_DISTRIBUTION = {
    "Dev": 2,
    "Design": 2,
    "Visual": 1,
    "Marketing": 1,
    "Event": 2
}

NUM_TEAMS = 9
TEAM_SIZE = 8
MIN_OLD_PER_TEAM = 2

# ------------------------------
# FLASK SETUP
# ------------------------------
app = Flask(__name__)
CORS(app)  # Allow CORS for all routes


# ------------------------------
# UTILITIES
# ------------------------------
def safe_get_name(doc):
    name = doc.get("name")
    if not name or str(name).strip().lower() in ["none", "null", ""]:
        email = doc.get("email", "")
        if "@" in email:
            return email.split("@")[0].capitalize()
        return "Unknown"
    return name.strip()


# ------------------------------
# TEAM GENERATION LOGIC
# ------------------------------
def generate_teams():
    members = list(event_emails.find({}, {"_id": 0}))

    # Deduplicate members
    unique_members = {}
    for m in members:
        email = str(m.get("email", "")).lower().strip()
        if not email:
            continue
        if email not in unique_members:
            unique_members[email] = m
        elif str(m.get("old_member", "")).lower() == "yes":
            unique_members[email] = m
    members = list(unique_members.values())

    # Classify into old/new pools
    old_pool = {d: [] for d in DEPARTMENT_DISTRIBUTION}
    new_pool = {d: [] for d in DEPARTMENT_DISTRIBUTION}

    for m in members:
        dept = m.get("department")
        if dept not in DEPARTMENT_DISTRIBUTION:
            continue

        member = {
            "name": safe_get_name(m),
            "email": m.get("email"),
            "department": dept,
            "old_member": m.get("old_member", "no")
        }

        if str(member["old_member"]).lower() == "yes":
            old_pool[dept].append(member)
        else:
            new_pool[dept].append(member)

    # Create a team
    def make_team(team_num):
        team_members = []
        dept_counts = {d: 0 for d in DEPARTMENT_DISTRIBUTION}

        # Step 1: assign minimum old members
        old_candidates = [m for pool in old_pool.values() for m in pool]
        random.shuffle(old_candidates)

        chosen_old = []
        for member in old_candidates:
            d = member["department"]
            if dept_counts[d] < DEPARTMENT_DISTRIBUTION[d]:
                chosen_old.append(member)
                dept_counts[d] += 1
                old_pool[d].remove(member)
                if len(chosen_old) >= MIN_OLD_PER_TEAM:
                    break

        # Step 2: fill with more old if room
        for member in list(old_candidates):
            if len(chosen_old) >= TEAM_SIZE:
                break
            d = member["department"]
            if member not in chosen_old and dept_counts[d] < DEPARTMENT_DISTRIBUTION[d]:
                chosen_old.append(member)
                dept_counts[d] += 1
                old_pool[d].remove(member)

        team_members.extend(chosen_old)

        # Step 3: fill remaining with new members
        for dept, max_per_team in DEPARTMENT_DISTRIBUTION.items():
            remaining = max_per_team - dept_counts[dept]
            for _ in range(remaining):
                if new_pool[dept]:
                    member = new_pool[dept].pop()
                    team_members.append(member)
                    dept_counts[dept] += 1

        random.shuffle(team_members)
        return {"team": f"Team {team_num}", "members": team_members}

    teams = [make_team(i + 1) for i in range(NUM_TEAMS)]
    return teams


# ------------------------------
# ROUTE
# ------------------------------
@app.route("/generate-teams", methods=["POST"])
def generate_teams_route():
    teams = generate_teams()

    # Replace existing collection
    teams_collection.delete_many({})
    teams_collection.insert_many(teams)

    for t in teams:
        t.pop("_id", None)

    # Return the JSON directly
    return jsonify(teams), 200


# ------------------------------
# MAIN
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
