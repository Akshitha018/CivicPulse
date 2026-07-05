"""
Generates realistic synthetic demo data so CivicPulse has something to show
without needing real city data. Centered on Vijayawada, Andhra Pradesh by
default — change CITY_CENTER to re-center on any city.
"""
import random
from datetime import datetime, timedelta

CITY_CENTER = (16.5062, 80.6480)  # Vijayawada
CITY_NAME = "Vijayawada"

random.seed(42)

COMPLAINT_TEMPLATES = [
    ("Roads & Potholes", "Medium", [
        "There's a large pothole near {area} that's damaging vehicles.",
        "The road on {area} main road has multiple potholes after the rains.",
        "Footpath near {area} is broken and unsafe for pedestrians.",
        "Speed breaker near {area} school is worn out and needs repair.",
    ]),
    ("Roads & Potholes", "Critical", [
        "Huge pothole near {area} caused a two-wheeler accident yesterday, someone was injured.",
        "Road collapse near {area} bridge, very dangerous for traffic at night.",
    ]),
    ("Sanitation & Waste", "Medium", [
        "Garbage has not been collected in {area} for the past 4 days.",
        "Overflowing dustbin near {area} market is attracting stray animals.",
        "Sewage water is stagnant on the road near {area}.",
    ]),
    ("Sanitation & Waste", "High", [
        "Open drain near {area} is overflowing and causing a foul smell across the street, third time this month.",
    ]),
    ("Water Supply", "Medium", [
        "No water supply in {area} for the last two days.",
        "Water pipeline leak near {area} is wasting a lot of water.",
    ]),
    ("Water Supply", "Critical", [
        "Major water pipeline burst near {area}, flooding the street and entering nearby homes.",
    ]),
    ("Electricity & Streetlights", "Medium", [
        "Streetlights on {area} road have not been working for a week, it's very dark at night.",
        "Frequent power cuts in {area} area, happening almost every evening.",
    ]),
    ("Electricity & Streetlights", "Critical", [
        "A live electric wire is hanging low near {area}, extremely dangerous, please send someone urgently.",
    ]),
    ("Public Safety", "High", [
        "Street near {area} has no proper lighting and there have been reports of chain snatching.",
        "Stray dogs near {area} have become aggressive, a child was chased yesterday.",
    ]),
    ("Parks & Public Spaces", "Low", [
        "The park in {area} has broken benches and unused for months.",
        "Playground equipment near {area} is rusted and unsafe for kids.",
    ]),
    ("Noise & Nuisance", "Low", [
        "Loud construction noise near {area} continues late into the night.",
        "Illegal loudspeaker use near {area} temple/function hall past midnight.",
    ]),
]

AREAS = [
    "Governorpet", "Labbipet", "Patamata", "Bhavanipuram", "Auto Nagar",
    "Gunadala", "Ajit Singh Nagar", "Payakapuram", "Suryaraopet", "Vidyadharapuram",
    "Krishna Lanka", "Currency Nagar", "Benz Circle", "Poranki", "Gollapudi",
]


def _jitter(lat, lng, meters=1200):
    # crude meter->degree jitter, fine for demo purposes
    deg = meters / 111000
    return lat + random.uniform(-deg, deg), lng + random.uniform(-deg, deg)


def generate_complaints(n=180):
    rows = []
    now = datetime.utcnow()
    # deliberately cluster some pothole reports around one area to demo hotspot detection
    hotspot_area = "Governorpet"
    hotspot_lat, hotspot_lng = None, None

    for i in range(n):
        category, priority, templates = random.choice(COMPLAINT_TEMPLATES)
        template = random.choice(templates)
        area = random.choice(AREAS)
        text = template.format(area=area)

        # force a hotspot cluster: ~8 pothole complaints tightly packed in one area
        if category == "Roads & Potholes" and random.random() < 0.35:
            area = hotspot_area
            text = random.choice(COMPLAINT_TEMPLATES[0][2]).format(area=area)
            if hotspot_lat is None:
                hotspot_lat, hotspot_lng = _jitter(*CITY_CENTER, meters=3000)
            lat, lng = _jitter(hotspot_lat, hotspot_lng, meters=150)
        else:
            lat, lng = _jitter(*CITY_CENTER, meters=6000)

        days_ago = random.randint(0, 13)
        created_at = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat()
        status = random.choices(["Open", "In Progress", "Resolved"], weights=[0.5, 0.3, 0.2])[0]
        sentiment = random.choice(["Neutral", "Frustrated", "Concerned", "Angry"])

        rows.append({
            "text": text,
            "category": category,
            "priority": priority,
            "sentiment": sentiment,
            "lat": lat,
            "lng": lng,
            "address_hint": f"{area}, {CITY_NAME}",
            "ai_summary": text,
            "created_at": created_at,
            "status": status,
        })

    return rows


FAQ_ENTRIES = [
    {"category": "Waste", "question": "When is garbage collected in my area?",
     "answer": "Municipal garbage collection runs door-to-door every day between 6 AM and 10 AM in most residential zones. If your street has been missed for more than 2 days, please file a complaint through CivicPulse and it will be routed to the Sanitation Department."},
    {"category": "Water", "question": "How do I report a water pipeline leak?",
     "answer": "You can report a water leak directly through the CivicPulse complaint form — just describe the location and issue. It will be automatically routed to the Water Board with a priority based on severity."},
    {"category": "Documents", "question": "How do I get a birth certificate?",
     "answer": "Birth certificates can be obtained from the Municipal Corporation's Civil Registration office. You'll need the hospital discharge summary or a self-declaration form, proof of address, and parents' ID proof. Processing typically takes 5-7 working days."},
    {"category": "Documents", "question": "How do I apply for a trade license?",
     "answer": "Trade licenses are issued by the Municipal Corporation's Licensing Department. You need to submit an application with proof of business address, ID proof, and applicable fees. New applications typically take 10-15 working days."},
    {"category": "Property", "question": "How do I pay my property tax?",
     "answer": "Property tax can be paid online through the Municipal Corporation's official payment portal using your Property Tax Identification Number (PTIN), or in person at any ward office."},
    {"category": "Roads", "question": "How do I report a pothole?",
     "answer": "Use the CivicPulse complaint form to describe the pothole and its location. The AI system will classify it by severity and route it to the Roads Department. If it's part of a larger cluster of nearby reports, it may be prioritized as a root-cause repair."},
    {"category": "Electricity", "question": "Who do I contact for a power outage?",
     "answer": "Report power outages through CivicPulse or directly to the Electricity Board helpline. Outages affecting a whole street or having safety risks (like exposed wires) are automatically flagged as high priority."},
    {"category": "Safety", "question": "How do I report an unsafe or poorly lit street?",
     "answer": "File a Public Safety complaint through CivicPulse describing the location and concern. These are routed to Municipal Enforcement and, where relevant, the local police station."},
    {"category": "General", "question": "How can I track the status of my complaint?",
     "answer": "Every complaint filed through CivicPulse receives a ticket ID (e.g. RD-1042). You can check its status — Open, In Progress, or Resolved — on the dashboard or by asking the assistant with your ticket ID."},
    {"category": "General", "question": "What is CivicPulse?",
     "answer": "CivicPulse is an AI-powered platform that lets citizens report issues in plain language, automatically classifies and routes them to the right city department, and gives city officials a real-time dashboard of community issues, including detection of recurring problem hotspots."},
    {"category": "Parks", "question": "How do I report damaged park equipment?",
     "answer": "File a complaint under Parks & Public Spaces through CivicPulse with the park name and description of the damage. It will be routed to the Parks Department."},
    {"category": "Noise", "question": "How do I report a noise complaint?",
     "answer": "You can file a Noise & Nuisance complaint through CivicPulse. Complaints about construction noise or loudspeakers after permitted hours are routed to Municipal Enforcement."},
]
