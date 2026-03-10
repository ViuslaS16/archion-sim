import os
import joblib
import numpy as np

def predict_crowd_risk(summary_stats: dict) -> float | None:
    """
    Predict a Crowd Crush Risk Score (0-10) using the trained Random Forest model.
    """
    model_path = os.path.join(os.path.dirname(__file__), "archion_insight_model.pkl")
    
    if not os.path.exists(model_path):
        print(f"[ML Predictor] Warning: Model file not found at {model_path}")
        return None
        
    try:
        model = joblib.load(model_path)
        
        # Extract features exactly as requested
        agents = summary_stats.get("total_agents", 0)
        area = summary_stats.get("floor_area_sqm", 0.0)
        vel = summary_stats.get("avg_velocity_ms", 0.0)
        cong = summary_stats.get("peak_congestion_pct", 0.0)
        
        # Format as 2D array: [[agents, area, vel, cong]]
        features = np.array([[agents, area, vel, cong]])
        
        # Predict score
        prediction = model.predict(features)[0]
        
        # Return float rounded to 1 decimal place
        return round(float(prediction), 1)
        
    except Exception as e:
        print(f"[ML Predictor] Error running inference: {e}")
        return None

