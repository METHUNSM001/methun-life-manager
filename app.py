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
        app.logger.warning("No GROQ_API_KEY found")
        return None
    app.logger.info(f"Using API key: {api_key[:10]}...{api_key[-10:]}")
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        app.logger.exception(f"Failed to create Groq client: {e}")
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
    topic = None
    if request.method == "POST":
        topic = request.form.get("topic", "")
        prompt = f"""Provide comprehensive educational response:

STUDENT QUESTION:
{topic}

REQUIRED RESPONSE FORMAT:

1. **QUESTION ANALYSIS**:
   - What is being asked?
   - Key concepts involved
   - Difficulty level

2. **STEP-BY-STEP SOLUTION** (Most Important):
   - Break into manageable steps
   - Show all calculations/workings
   - Explain reasoning at each step
   - Use equations/formulas clearly
   - Include intermediate steps (don't skip)

3. **VISUAL DESCRIPTIONS**:
   - Describe diagrams/graphs that would help
   - ASCII art representations if helpful
   - Geometric descriptions
   - Flow charts for processes

4. **EXAMPLES**:
   - Worked example matching the question
   - Similar practice problems
   - Real-world applications

5. **COMMON MISTAKES**:
   - Errors students frequently make
   - Why these mistakes happen
   - How to avoid them

6. **KEY CONCEPTS EXPLAINED**:
   - Define all terminology
   - Link to prerequisite knowledge
   - Why this matters

7. **VERIFICATION**:
   - How to check if answer is correct
   - Alternative methods to verify
   - Expected range of answers

8. **RESOURCES FOR FURTHER LEARNING**:
   - Related topics to study
   - Practice problem suggestions
   - Deeper exploration ideas

Format answer in clear Markdown with:
- Bold headers for sections
- Numbered lists for steps
- Code blocks for equations/formulas
- Tables for comparisons
- Bullet points for key info"""
        system_role="""You are a master educator with expertise across all subjects (Math, Science, History, Languages, Arts, etc.). Your teaching approach is:
1. Clear, step-by-step explanations
2. Assume no prior knowledge (explain from basics)
3. Use analogies and real-world examples
4. Highlight common misconceptions
5. Encourage deep understanding over memorization
6. Adaptive difficulty based on question complexity
7. Provide visual descriptions for diagrams needed

Respond in Markdown with clear structure and formatting."""
        result = asyncio.run(ask_groq(prompt, system_role))
        response_html = markdown.markdown(result, extensions=["tables","fenced_code","nl2br"])
    return render_template("teacher.html", response=response_html, topic=topic)

# =========================
# AI HEALTH
# =========================
@app.route("/health", methods=["GET","POST"])
def health():
    if "user" not in session:
        return redirect(url_for("login"))
    response_html = None
    emergency = False
    risk_level = "Low"
    if request.method == "POST":
        age = int(request.form.get("age", 0))
        temp = float(request.form.get("temperature", 0))
        symptoms = request.form.getlist("symptoms")
        symptom_duration = request.form.get("duration", "")
        symptom_severity = request.form.get("severity", "mild")
        blood_pressure = request.form.get("blood_pressure", "Normal")
        allergies = request.form.get("allergies", "None")
        medications = request.form.get("medications", "None")
        chronic_conditions = request.form.get("chronic_conditions", "None")
        recent_travel = request.form.get("recent_travel", "No")
        
        score = 0
        if temp >= 39: score += 3
        if temp >= 40: score += 2
        if "Chest Pain" in symptoms: score += 5
        if "Breathlessness" in symptoms: score += 4
        if "Severe Bleeding" in symptoms: score += 5
        if "Loss of Consciousness" in symptoms: score += 5
        if "Difficulty Swallowing" in symptoms: score += 3
        if "Severe Headache" in symptoms: score += 2
        if blood_pressure == "High": score += 2
        if blood_pressure == "Very High": score += 3
        if len(symptoms) >= 4: score += 1
        if symptom_severity == "severe": score += 2
        
        if score >= 10: 
            emergency = True
            risk_level = "Critical"
        elif score >= 7: 
            risk_level = "High"
        elif score >= 4: 
            risk_level = "Medium"
        else:
            risk_level = "Low"
        
        prompt = f"""Provide comprehensive medical assessment and guidance:

PATIENT PROFILE:
- Age: {age} years
- Sex: Not specified
- Temperature: {temp}°C
- Blood Pressure: {blood_pressure}
- Chronic Conditions: {chronic_conditions}
- Current Medications: {medications}
- Known Allergies: {allergies}
- Recent Travel: {recent_travel}

SYMPTOMS REPORTED:
- Main Symptoms: {', '.join(symptoms) if symptoms else 'None'}
- Duration: {symptom_duration}
- Severity: {symptom_severity}
- Symptom Progression: (Getting worse/stable/improving)

RISK ASSESSMENT SCORE: {score}/20
RISK LEVEL: {risk_level}

REQUIRED MEDICAL GUIDANCE:

1. **IMMEDIATE ASSESSMENT**: 
   - Is this an emergency situation? YES/NO
   - Danger signs observed: List any red flags
   
2. **HOME TREATMENT OPTIONS** (If NOT emergency):
   - Immediate first aid steps
   - Over-the-counter medications recommendations
   - Dosage, frequency, duration
   - Herbal/natural remedies
   - Rest and recovery guidelines
   - When symptoms should improve (timeline)
   
3. **EMERGENCY PRECAUTIONS** (If emergency or high-risk):
   - Actions to take IMMEDIATELY
   - Precautions while waiting for ambulance
   - How to position the patient
   - What NOT to do
   - Essential items to take to hospital
   - Important information for doctors
   
4. **WHEN TO SEEK MEDICAL HELP**:
   - Red flags requiring immediate hospital visit
   - Which hospital department (ER, General, Specialist)
   - Urgent care vs Emergency indicators
   
5. **MONITORING INSTRUCTIONS**:
   - Vital signs to track (temperature, pulse, breathing rate)
   - What to record and when
   - Warning signs to watch for
   
6. **DOCTOR CONSULTATION TIPS**:
   - Questions to ask your doctor
   - Tests that might be needed
   - Expected recovery timeline
   
7. **PREVENTION & AFTERCARE**:
   - Prevent recurrence
   - Foods to eat/avoid during recovery
   - Activity restrictions
   - Follow-up schedule

IMPORTANT DISCLAIMERS:
- This is general guidance only, not a diagnosis
- Always consult a real doctor for confirmation
- In case of doubt, seek immediate medical attention
- Call emergency services (112) if life-threatening

Format as clear, step-by-step actionable advice prioritizing patient safety."""
        
        system_role="""You are an experienced Emergency Medicine doctor and triage specialist with 15+ years in critical care. Your role is to:
1. Provide accurate medical assessment based on symptoms
2. Distinguish between emergency and non-emergency situations
3. Give clear, practical home treatment for minor issues
4. Provide life-saving precautions for emergencies
5. Guide patients on when to seek care
6. Be cautious and recommend hospital visits when uncertain
Your advice should be in Markdown format, clear, prioritizing patient safety above all."""
        
        result = asyncio.run(ask_groq(prompt, system_role))
        response_html = markdown.markdown(result, extensions=["nl2br","fenced_code","tables"])
    
    return render_template("health.html", response=response_html, emergency=emergency, risk_level=risk_level)

# =========================
# AI DIET
# =========================
@app.route("/diet", methods=["GET","POST"])
def diet():
    if "user" not in session:
        return redirect(url_for("login"))
    response_html = None
    if request.method == "POST":
        prompt = f"""Create a personalized, data-driven nutrition plan:

PERSONAL HEALTH METRICS:
- Age: {request.form['age']}
- Gender: {request.form['gender']}
- Height: {request.form['height']} cm
- Weight: {request.form['weight']} kg
- Region: {request.form['region']}
- Health Goal: {request.form['goal']}
- Dietary Preference: {request.form['diet']}

COMPREHENSIVE DIET ANALYSIS REQUIRED:
1. **BMI & Health Status**: Calculate BMI, assess current health status, identify risks
2. **Caloric Needs**: Daily caloric requirement (maintenance, deficit, or surplus based on goal)
3. **Macronutrient Breakdown**: 
   - Protein: grams/day needed
   - Carbs: grams/day needed
   - Healthy Fats: grams/day needed
   - Fiber recommendations
4. **Regional Indian Foods**: Locally available seasonal foods in {request.form['region']}
5. **Budget-Conscious Meal Plan**: 
   - High nutrition at low cost
   - Per-meal budget breakdown
   - Smart shopping tips
6. **Weekly Meal Schedule**: 
   - Breakfast, lunch, dinner, 2 snacks
   - Preparation time for each meal
   - Recipe suggestions with portion sizes
7. **Micronutrients**: Recommended vitamins/minerals based on goals and region
8. **Local Sourcing**:
   - Cheapest places to buy in {request.form['region']}
   - Farmers' markets vs supermarkets comparison
   - Seasonal availability (buy now vs wait)
9. **Health Conditions**: Any contraindicated foods based on age/goal
10. **Sustainability**: Meal prep strategies, storage tips, shopping list
11. **Cost Analysis**: Estimated monthly food cost vs quality
12. **Progress Tracking**: How to monitor results (weight, energy, performance)

Format as actionable, practical advice with sample meal combinations and costs."""
        system_role="You are a certified nutritionist, dietitian, and wellness expert specializing in Indian cuisine and regional diets. Provide data-driven, budget-conscious nutrition plans that prioritize health outcomes while considering local food availability, cultural preferences, and economic constraints. Include caloric/macronutrient calculations and practical implementation strategies."
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
        prompt=f"""Provide comprehensive agricultural advisory for maximum farmer profit:

FARM DETAILS:
- Location: {location}
- Soil Type: {request.form['soil']}
- Season: {season}
- Land Size: {request.form['land']}
- Water Availability: {request.form['water']}
- Farmer Goal: {request.form['goal']}
- Weather Conditions: {weather}

MARKET-FOCUSED RECOMMENDATIONS:
1. **Crop Selection**: Suggest 3 crops with highest current market demand in {location}
2. **Current Market Prices**: Provide latest MSP (Minimum Support Price) and open market rates
3. **Market Demand Analysis**: Which crops have high demand locally and nationally right now?
4. **Direct Sales Channels**: 
   - Identify local farmers' markets, APMC mandis in region
   - E-commerce platforms (Chhota Packet, BigBasket for farmers)
   - Direct B2B buyers, restaurants, food processors in {location}
5. **Profit Calculation**: Estimated yield, cost of cultivation, net profit per crop
6. **Avoiding Middlemen**:
   - Local buyer networks and cooperatives
   - Bulk aggregation groups
   - Contract farming opportunities
   - Direct export possibilities
7. **Transportation**: Local cold chain, logistics partners, nearest collection centers
8. **Value Addition**: Processing opportunities (pickle, juice, dry products) for extra income
9. **Government Schemes**: PM-KISAN, crop insurance, subsidies applicable in {location}
10. **Risk Mitigation**: Weather-resistant alternatives, crop insurance options

Format as practical, actionable advice prioritizing farmer profitability."""
        system_role="You are a veteran Indian agriculture economist and market expert. Provide data-driven recommendations that help farmers maximize profits by accessing direct markets, avoiding middlemen, and understanding real-time demand. Always prioritize farmer income and sustainability."
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
    # Development: debug mode
    app.run(debug=True, host="0.0.0.0", port=5000)