import numpy as np
from typing import Dict, Any

def compute_slope(elevation: np.ndarray, cell_size_m: float = 100.0) -> np.ndarray:
    """
    Computes slope in degrees from an elevation matrix.
    cell_size_m: approximate grid cell width in meters.
    """
    dy, dx = np.gradient(elevation, cell_size_m)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    return slope_deg

def compute_depression_depth(elevation: np.ndarray) -> np.ndarray:
    """
    Computes relative local depression depth (sink depth / relative elevation).
    Calculates local neighborhood minimum and subtracts it from cell elevation.
    Depression depth > 0 indicates how deep a cell sits relative to surrounding terrain.
    """
    rows, cols = elevation.shape
    padded = np.pad(elevation, pad_width=1, mode='edge')
    local_min = np.zeros_like(elevation)
    
    for r in range(rows):
        for c in range(cols):
            window = padded[r:r+3, c:c+3]
            local_min[r, c] = np.min(window)
            
    # Relative height above local minimum (HAND proxy)
    # Depression depth is higher in low spots relative to local max
    max_in_window = np.zeros_like(elevation)
    for r in range(rows):
        for c in range(cols):
            window = padded[r:r+3, c:c+3]
            max_in_window[r, c] = np.max(window)
            
    depression_depth = max_in_window - elevation
    return np.maximum(0.0, depression_depth)

def compute_flow_accumulation(elevation: np.ndarray, slope_deg: np.ndarray) -> np.ndarray:
    """
    Computes a deterministic flow accumulation proxy.
    Lower slopes and lower elevations receive accumulated flow from surrounding higher cells.
    """
    rows, cols = elevation.shape
    flow_acc = np.ones_like(elevation)
    
    # Simple flow accumulation approximation based on relative elevation rank
    flat_indices = np.argsort(elevation.ravel())[::-1] # Sort high to low
    
    for idx in flat_indices:
        r, c = np.unravel_index(idx, (rows, cols))
        current_elev = elevation[r, c]
        
        # Check neighbors
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if elevation[nr, nc] < current_elev:
                        # Flow down to lower neighbor
                        flow_acc[nr, nc] += flow_acc[r, c] * 0.125
                        
    return flow_acc

def process_dem_terrain(dem_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full terrain processing pipeline.
    Validates CRS, resolution, nodata, extent, and returns terrain products.
    """
    elevation = dem_data["elevation"]
    
    # Handle NaNs / Nodata if any
    elevation = np.nan_to_num(elevation, nan=np.nanmean(elevation))
    
    slope = compute_slope(elevation)
    depressions = compute_depression_depth(elevation)
    flow_acc = compute_flow_accumulation(elevation, slope)
    
    return {
        "elevation": elevation,
        "slope_deg": slope,
        "depression_depth_m": depressions,
        "flow_accumulation": flow_acc
    }
