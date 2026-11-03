import argparse
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.main import SessionLocal, Base, engine
from app.models import User, Skill, Task, SkillPrerequisite
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def seed(db, reset=False):
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    skills_data = [
        {"name": "Variables", "domain": "python", "difficulty_base": 20, "description": "Storing data in variables", "mastery_threshold": 70},
        {"name": "Printing", "domain": "python", "difficulty_base": 15, "description": "Outputting text with print()", "mastery_threshold": 70},
        {"name": "Loops", "domain": "python", "difficulty_base": 40, "description": "Repeating code with for/while", "mastery_threshold": 80},
        {"name": "Functions", "domain": "python", "difficulty_base": 50, "description": "Reusable code blocks with def", "mastery_threshold": 80},
        {"name": "Lists", "domain": "python", "difficulty_base": 35, "description": "Collections of values", "mastery_threshold": 75},
        {"name": "Dictionaries", "domain": "python", "difficulty_base": 55, "description": "Key-value pairs", "mastery_threshold": 80},
    ]

    skill_by_name = {}
    for s in skills_data:
        skill = db.query(Skill).filter(Skill.name == s["name"]).first()
        if not skill:
            skill = Skill(**s)
            db.add(skill)
            db.flush()
        skill_by_name[s["name"]] = skill
    db.commit()

    var_skill = skill_by_name["Variables"]
    print_skill = skill_by_name["Printing"]
    loop_skill = skill_by_name["Loops"]
    fn_skill = skill_by_name["Functions"]
    list_skill = skill_by_name["Lists"]

    prereq_specs = [
        (print_skill, var_skill),
        (loop_skill, print_skill),
        (fn_skill, loop_skill),
        (list_skill, fn_skill),
    ]
    for child, parent in prereq_specs:
        existing = db.query(SkillPrerequisite).filter(
            SkillPrerequisite.skill_id == child.id,
            SkillPrerequisite.prerequisite_id == parent.id
        ).first()
        if not existing:
            db.add(SkillPrerequisite(skill_id=child.id, prerequisite_id=parent.id))
    db.commit()

    tasks_data = [
        {
            "skill_id": var_skill.id,
            "title": "Print Hello World",
            "description": "Use the print() function to output the message 'Hello, World!' to the console.",
            "difficulty": 10,
            "starter_code": "# Your code here\n",
            "expected_solution": "Print a greeting message using the print() function.",
            "solution_intent": "Use print() with a string argument.",
            "test_cases": [{"input": "", "expected": "Hello, World!"}]
        },
        {
            "skill_id": loop_skill.id,
            "title": "Sum a List",
            "description": "Write a loop that sums all numbers in the list [1, 2, 3, 4, 5].",
            "difficulty": 40,
            "starter_code": "numbers = [1, 2, 3, 4, 5]\n# Your code here\n",
            "expected_solution": "Use a for loop to accumulate sum.",
            "solution_intent": "Initialize total=0, iterate with for, accumulate total += x.",
            "test_cases": [{"expected": "15"}]
        },
    ]

    for t in tasks_data:
        existing_task = db.query(Task).filter(Task.title == t["title"], Task.skill_id == t["skill_id"]).first()
        if not existing_task:
            db.add(Task(**t))
    db.commit()

    users = [
        {"email": "student@test.com", "username": "student", "password": "password123", "full_name": "Test Student"},
        {"email": "admin@test.com", "username": "admin", "password": "admin123", "full_name": "Admin User"},
    ]

    for u in users:
        if not db.query(User).filter(User.username == u["username"]).first():
            db.add(User(
                email=u["email"],
                username=u["username"],
                hashed_password=pwd_context.hash(u["password"]),
                full_name=u["full_name"]
            ))
    db.commit()
    print("Database seeded successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        seed(db, reset=args.reset)
    finally:
        db.close()