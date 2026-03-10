from core.ml_predictor import predict_crowd_risk
# 1) Typical output test
score = predict_crowd_risk({
    'total_agents': 50, 
    'floor_area_sqm': 100.0, 
    'avg_velocity_ms': 1.2, 
    'peak_congestion_pct': 50.0
})
print("Result:", score)

# 2) Graceful fallback with missing joblib
try:
    import joblib
except ImportError:
    pass

