from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import os
import asyncio
import markdown
from groq import Groq
from dotenv import load_dotenv
import random

# =========================
# BASIC SETUP
# =========================
app = Flask(__name__, template_folder="Templates")
app.secret_key = "super_secret_key_change_this"

load_dotenv()
# Read key from environment; do not hardcode secrets in source
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

USERS_FILE = "users.xlsx"


# Helpers to load/save users with an in-memory fallback when filesystem
# is read-only (serverless environments). This prevents import-time
# crashes when Vercel or the runtime disallows writing to the project dir.
def load_users():
    try:
        if os.path.exists(USERS_FILE):
            return pd.read_excel(USERS_FILE)
        df = pd.DataFrame(columns=["name", "email", "password"])
        try:
            df.to_excel(USERS_FILE, index=False)
        except Exception:
            app.logger.warning("Cannot write users file; using in-memory store")
            app.config['USERS_DF'] = df
        return df
    except Exception:
        app.logger.exception("Failed reading users file; using in-memory store")
        return app.config.get('USERS_DF', pd.DataFrame(columns=["name", "email", "password"]))


def save_users(df):
    try:
        df.to_excel(USERS_FILE, index=False)
    except Exception:
        app.logger.warning("Cannot persist users file; saving to memory only")
        app.config['USERS_DF'] = df


# Initialize in-memory copy (used if filesystem not writable)
app.config['USERS_DF'] = load_users()

# =========================
# GROQ CLIENT
# =========================
def get_groq_client():
    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        app.logger.exception("Failed to create Groq client")
        return None

# =========================
# GROQ CALL
# =========================
async def ask_groq(prompt, system_role):
    client = get_groq_client()
    if client is None:
        return "GROQ API key not configured. Please set the GROQ_API_KEY environment variable."
    messages = [
        {"role": "system", "content": system_role},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        app.logger.exception("Groq request failed")
        return f"Error contacting Groq: {e}"

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return redirect(url_for("login"))

# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        df = pd.read_excel(USERS_FILE)
        if request.form["email"] in df["email"].values:
            return render_template("register.html", error="Email already exists")
        df.loc[len(df)] = [request.form["name"], request.form["email"], request.form["password"]]
        df.to_excel(USERS_FILE, index=False)
        return redirect(url_for("login"))
    return render_template("register.html")

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        df = pd.read_excel(USERS_FILE)
        user = df[(df["email"]==request.form["email"]) & (df["password"]==request.form["password"])]
        if user.empty:
            return render_template("login.html", error="Invalid credentials")
        session["user"] = request.form["email"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

# =========================
# AI TEACHER
# =========================
@app.route("/teacher", methods=["GET", "POST"])
def teacher():
    if "user" not in session:
        return redirect(url_for("login"))
    response_html = None
    if request.method == "POST":
        topic = request.form.get("topic", "")
        prompt = f"Student Question:\n{topic}\nAnswer clearly and step-by-step in Markdown."
        system_role = "Expert AI teacher for all subjects. Respond in Markdown."
        result = asyncio.run(ask_groq(prompt, system_role))
        response_html = markdown.markdown(result, extensions=["tables","fenced_code","nl2br"])
    return render_template("teacher.html", response=response_html)

# =========================
# AI HEALTH
# =========================
@app.route("/health", methods=["GET","POST"])
def health():
    if "user" not in session:
        return redirect(url_for("login"))
    response_html = None
    emergency = False
    if request.method == "POST":
        age = int(request.form.get("age", 0))
        temp = float(request.form.get("temperature", 0))
        symptoms = request.form.getlist("symptoms")
        score = 0
        if temp>=39: score+=3
        if "Chest Pain" in symptoms or "Breathlessness" in symptoms: score+=4
        if score>=8: emergency=True
        risk = "High" if score>=8 else "Medium" if score>=4 else "Low"
        prompt = f"Patient age {age}, temperature {temp}, symptoms {symptoms}. Give medical guidance in Markdown."
        system_role="Senior medical AI assistant. Only general guidance. Markdown format."
        result = asyncio.run(ask_groq(prompt, system_role))
        response_html = markdown.markdown(result, extensions=["nl2br","fenced_code"])
    return render_template("health.html", response=response_html, emergency=emergency)

# =========================
# AI DIET
# =========================
@app.route("/diet", methods=["GET","POST"])
def diet():
    if "user" not in session:
        return redirect(url_for("login"))
    response_html = None
    if request.method == "POST":
        prompt = f"Age:{request.form['age']},Gender:{request.form['gender']},Height:{request.form['height']},Weight:{request.form['weight']},Region:{request.form['region']},Goal:{request.form['goal']},Diet:{request.form['diet']}"
        system_role="Nutrition expert. Respond in Markdown with Indian diet plan."
        result = asyncio.run(ask_groq(prompt, system_role))
        response_html = markdown.markdown(result, extensions=["tables","nl2br"])
    return render_template("diet.html", response=response_html)

# =========================
# SIMULATED WEATHER FOR CROP
# =========================
def simulate_weather(city, season="Kharif"):
    temp_ranges = {"Kharif": (25,35), "Rabi":(15,28), "Zaid":(28,40)}
    min_temp,max_temp=temp_ranges.get(season,(20,35))
    temperature=round(random.uniform(min_temp,max_temp),1)
    return {
        "city": city.title(),
        "season": season,
        "temperature": temperature,
        "max_temp": round(random.uniform(temperature,max_temp),1),
        "min_temp": round(random.uniform(min_temp,temperature),1),
        "rain": round(random.uniform(0,20),1),
        "windspeed": round(random.uniform(5,25),1),
        "humidity": round(random.uniform(40,90),0)
    }

# =========================
# AI CROP RECOMMENDER
# =========================
@app.route("/crop", methods=["GET","POST"])
def crop():
    if "user" not in session:
        return redirect(url_for("login"))
    response_html=None
    weather=None
    if request.method=="POST":
        location=request.form['location']
        season=request.form['season']
        weather=simulate_weather(location,season)
        prompt=f"Location: {location}, Soil: {request.form['soil']}, Season: {season}, Land: {request.form['land']}, Water: {request.form['water']}, Goal: {request.form['goal']}, Weather: {weather}"
        system_role="Indian agriculture expert. Suggest crops, fertilizers, prices. Markdown."
        result=asyncio.run(ask_groq(prompt, system_role))
        response_html=markdown.markdown(result, extensions=["tables","nl2br"])
    return render_template("crop.html", response=response_html, weather=weather)

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
# RUN
# =========================
if __name__=="__main__":
    app.run(debug=True)