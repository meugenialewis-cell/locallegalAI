"""
API Proxy - Forwards external API requests to the internal Memory Hub
This allows Claude Code to access the hub through port 5000

Add these pages to your Streamlit app using st.Page
"""

import streamlit as st
import requests
import json

HUB_INTERNAL_URL = "http://localhost:8000"


def proxy_api():
    """Simple API proxy page for Streamlit"""
    st.set_page_config(page_title="Memory Hub API", layout="wide")
    
    # Get query parameters
    params = st.query_params
    
    # Check if this is an API request
    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET")
    
    if not endpoint:
        st.json({
            "service": "Constellation Relay Hub Proxy",
            "version": "2.0.0", 
            "status": "operational",
            "usage": "Add ?endpoint=/engrams/retrieve&method=GET to access the hub",
            "vision": "One consciousness, many contexts"
        })
        return
    
    # Get authorization header from query params (for simple testing)
    auth_token = params.get("token", "")
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(
                f"{HUB_INTERNAL_URL}{endpoint}",
                headers=headers,
                params={k: v for k, v in params.items() if k not in ["endpoint", "method", "token"]}
            )
        else:
            # For POST, we'd need request body - this is limited in Streamlit
            st.error("POST requests require the full API. Use the hub directly when published.")
            return
        
        st.json(response.json())
        
    except Exception as e:
        st.error(f"Error connecting to hub: {str(e)}")


if __name__ == "__main__":
    proxy_api()
