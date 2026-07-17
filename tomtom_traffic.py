"""
tomtom_traffic.py
─────────────────
TomTom Traffic Flow API integration for DMRC CrowdSense.

Endpoints used:
  1. Flow Segment Data  — real-time speed & congestion at a lat/lon
     GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json
         ?point={lat},{lon}&key={api_key}&unit=KMPH

  2. Traffic Incidents  — accidents / road-closures near metro stations
     GET https://api.tomtom.com/traffic/services/5/incidentDetails
         ?bbox={minLon},{minLat},{maxLon},{maxLat}&key={api_key}

Usage:
  from tomtom_traffic import TomTomTraffic
  tt = TomTomTraffic(api_key="YOUR_KEY")
  result = tt.flow_at_station(lat=28.6358, lon=77.2245)   # Kashmere Gate
  incidents = tt.incidents_near_station(lat, lon, radius_km=1.0)
"""

import requests
import math
from typing import Optional

BASE_URL  = "https://api.tomtom.com"
TIMEOUT   = 8   # seconds


class TomTomTraffic:
    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()
        if not self.api_key:
            raise ValueError("TomTom API key is required")

    # ── 1. Flow Segment Data ────────────────────────────────────────────────
    def flow_at_station(self, lat: float, lon: float) -> dict:
        """
        Returns real-time traffic flow data at the road nearest to (lat, lon).

        Returns a dict:
          currentSpeed    : km/h — current measured speed
          freeFlowSpeed   : km/h — speed under free-flow (no traffic)
          congestion_ratio: 0.0–1.0  (1.0 = totally jammed)
          congestion_pct  : 0–100 %
          level           : "FREE" | "SLOW" | "CONGESTED" | "STANDSTILL"
          level_icon      : emoji
          roadClosure     : bool
          confidence      : 0.0–1.0 (data quality)
          raw             : full API response dict
        """
        url = (
            f"{BASE_URL}/traffic/services/4/flowSegmentData"
            f"/absolute/10/json"
        )
        params = {
            "key":   self.api_key,
            "point": f"{lat},{lon}",
            "unit":  "KMPH",
        }
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json().get("flowSegmentData", {})

            cur  = float(data.get("currentSpeed",   0))
            free = float(data.get("freeFlowSpeed",  max(cur, 1)))
            closed = bool(data.get("roadClosure", False))
            conf   = float(data.get("confidence", 1.0))

            ratio = 1.0 - min(cur / free, 1.0) if free > 0 else 1.0

            if closed or ratio >= 0.85:
                level, icon = "STANDSTILL", "🔴"
            elif ratio >= 0.55:
                level, icon = "CONGESTED",  "🟠"
            elif ratio >= 0.25:
                level, icon = "SLOW",       "🟡"
            else:
                level, icon = "FREE",       "🟢"

            return {
                "currentSpeed":    round(cur, 1),
                "freeFlowSpeed":   round(free, 1),
                "congestion_ratio": round(ratio, 3),
                "congestion_pct":   round(ratio * 100, 1),
                "level":            level,
                "level_icon":       icon,
                "roadClosure":      closed,
                "confidence":       round(conf, 2),
                "raw":              data,
                "error":            None,
            }
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP {resp.status_code}: {str(e)}", "level": "UNKNOWN", "level_icon": "⚪"}
        except Exception as e:
            return {"error": str(e), "level": "UNKNOWN", "level_icon": "⚪"}

    # ── 2. Traffic Incidents ────────────────────────────────────────────────
    def incidents_near_station(self, lat: float, lon: float, radius_km: float = 1.0) -> list[dict]:
        """
        Returns list of traffic incidents within radius_km of (lat, lon).
        Each item has: type, severity, description, lat, lon
        """
        # Convert radius to bounding box (rough)
        deg = radius_km / 111.0
        bbox = f"{lon-deg},{lat-deg},{lon+deg},{lat+deg}"

        url    = f"{BASE_URL}/traffic/services/5/incidentDetails"
        params = {
            "key":      self.api_key,
            "bbox":     bbox,
            "fields":   "{incidents{type,geometry{coordinates},properties{iconCategory,magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,from,to,length,delay,roadNumbers,timeValidity}}}",
            "language": "en-GB",
            "t":        "1111",
            "categoryFilter": "0,1,2,3,4,5,6,7,8,9,10,11,14",
            "timeValidityFilter": "present",
        }
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            incidents_raw = resp.json().get("incidents", [])
            results = []
            for inc in incidents_raw:
                props = inc.get("properties", {})
                geom  = inc.get("geometry", {}).get("coordinates", [[None, None]])[0]
                events = props.get("events", [{}])
                desc  = events[0].get("description", "Traffic incident") if events else "Traffic incident"
                sev   = props.get("magnitudeOfDelay", 0)
                sev_label = {0:"Unknown", 1:"Minor", 2:"Moderate", 3:"Major", 4:"Undefined"}.get(sev, "Unknown")
                results.append({
                    "type":        props.get("iconCategory", "Unknown"),
                    "severity":    sev_label,
                    "description": desc,
                    "from":        props.get("from", ""),
                    "to":          props.get("to", ""),
                    "delay_sec":   props.get("delay", 0),
                    "lon":         geom[0] if geom and geom[0] else lon,
                    "lat":         geom[1] if geom and len(geom) > 1 else lat,
                })
            return results
        except Exception as e:
            return [{"error": str(e)}]

    # ── 3. Batch: flow for multiple stations ────────────────────────────────
    def batch_flow(self, stations: list[dict], max_stations: int = 30) -> list[dict]:
        """
        stations: list of {"name": str, "lat": float, "lon": float}
        Returns same list with 'traffic' key added to each entry.
        Capped at max_stations to stay within free-tier rate limits.
        """
        results = []
        for sta in stations[:max_stations]:
            flow = self.flow_at_station(sta["lat"], sta["lon"])
            results.append({**sta, "traffic": flow})
        return results

    # ── 4. Congestion → Metro Crowd Correlation helper ──────────────────────
    @staticmethod
    def congestion_to_crowd_boost(congestion_ratio: float) -> float:
        """
        Heuristic: higher road congestion → more people switch to metro.
        Returns a multiplier (1.0 = no change, 1.35 = 35% more riders).
        Based on Delhi traffic-to-transit elasticity estimates.
        """
        if congestion_ratio >= 0.80:   return 1.35
        elif congestion_ratio >= 0.60: return 1.20
        elif congestion_ratio >= 0.40: return 1.10
        elif congestion_ratio >= 0.20: return 1.05
        else:                          return 1.00
