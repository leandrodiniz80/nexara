from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Nexara está no ar 🚀"}

@app.get("/billing/overview")
def overview():
    return {
        "business_score": 82,
        "business_status": "Crescimento acelerado",
        "executive_insight": "Seu negócio está crescendo forte, mas atenção ao churn.",
        "weekly_focus": "Focar em conversão de leads quentes",
        "top_opportunities": [],
        "at_risk_customers": [],
        "top_customers": []
    }
