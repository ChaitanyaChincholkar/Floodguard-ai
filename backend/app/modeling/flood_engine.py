import numpy as np
from typing import Dict, Any, List, Tuple
from shapely.geometry import Polygon, mapping

class BaselineFloodModel:
    """
    Deterministic & Interpretable Baseline Urban Flood Model.
    Combines rainfall forcing, terrain slope, relative depression depth, and flow accumulation.
    PROVENANCE: DEVELOPMENT MODEL — BASELINE FLOOD MODEL (NOT FOR OPERATIONAL DECISION MAKING)
    """
    def __init__(self, urban_runoff_coeff: float = 0.70, min_inundation_depth_m: float = 0.05):
        self.urban_runoff_coeff = urban_runoff_coeff
        self.min_inundation_depth_m = min_inundation_depth_m
        
        self.risk_thresholds = {
            "low": (0.05, 0.15),
            "moderate": (0.15, 0.35),
            "high": (0.35, 0.60),
            "severe": (0.60, float('inf'))
        }

    def classify_risk(self, depth_m: float) -> str:
        if depth_m < 0.05:
            return "none"
        elif depth_m < 0.15:
            return "low"
        elif depth_m < 0.35:
            return "moderate"
        elif depth_m < 0.60:
            return "high"
        else:
            return "severe"

    def run_simulation(self, dem_data: Dict[str, Any], terrain_data: Dict[str, Any], rainfall_mm: float) -> Dict[str, Any]:
        elevation = terrain_data["elevation"]
        slope_deg = terrain_data["slope_deg"]
        depressions = terrain_data["depression_depth_m"]
        flow_acc = terrain_data["flow_accumulation"]
        
        rows, cols = elevation.shape
        lons = dem_data["lons"]
        lats = dem_data["lats"]
        cell_size_lon = dem_data["cell_size_lon"]
        cell_size_lat = dem_data["cell_size_lat"]
        
        effective_rain = rainfall_mm * self.urban_runoff_coeff # mm
        
        slope_factor = 1.0 / np.maximum(0.5, slope_deg)
        depression_factor = 1.0 + 0.25 * depressions
        flow_factor = 1.0 + 0.15 * np.log1p(flow_acc)
        
        depth_m = (effective_rain * 0.004) * slope_factor * depression_factor * flow_factor
        depth_m[depth_m < self.min_inundation_depth_m] = 0.0
        
        features = []
        risk_counts = {"low": 0, "moderate": 0, "high": 0, "severe": 0}
        depths_list = []
        
        cell_area_sqkm = (cell_size_lon * 111.0) * (cell_size_lat * 111.0)
        
        for r in range(rows - 1):
            for c in range(cols - 1):
                d = float(depth_m[r, c])
                if d < self.min_inundation_depth_m:
                    continue
                    
                risk = self.classify_risk(d)
                if risk in risk_counts:
                    risk_counts[risk] += 1
                depths_list.append(d)
                
                x1, y1 = lons[c], lats[r]
                x2, y2 = lons[c + 1], lats[r + 1]
                poly = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)])
                
                features.append({
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {
                        "predicted_depth_m": round(d, 2),
                        "risk_level": risk,
                        "rainfall_mm": round(rainfall_mm, 1),
                        "elevation_m": round(float(elevation[r, c]), 1),
                        "slope_deg": round(float(slope_deg[r, c]), 1),
                        "data_status": "simulated",
                        "model_name": "Baseline Urban Flood Model",
                        "model_version": "0.1.0"
                    }
                })

        affected_cells = len(depths_list)
        total_affected_area_sqkm = affected_cells * cell_area_sqkm
        max_depth = float(np.max(depths_list)) if depths_list else 0.0
        mean_depth = float(np.mean(depths_list)) if depths_list else 0.0

        return {
            "features": features,
            "metrics": {
                "rainfall_mm": rainfall_mm,
                "affected_cells": affected_cells,
                "affected_area_sqkm": round(total_affected_area_sqkm, 2),
                "max_depth_m": round(max_depth, 2),
                "mean_depth_m": round(mean_depth, 2),
                "risk_counts": risk_counts
            },
            "depth_matrix": depth_m
        }
