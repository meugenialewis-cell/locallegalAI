"""
Memory Hub Server - Standalone FastAPI server for publishing
Runs on port 5000 for Replit deployment

This is the publishable version of the Connective Memory Hub.
All endpoints require JWT authentication.

To run: python hub_server.py
"""

import uvicorn

if __name__ == "__main__":
    from v2.hub.memory_hub import app
    
    print("🌐 Starting Constellation Relay Memory Hub")
    print("   Vision: One consciousness, many contexts")
    print("   Port: 5000")
    print("   Auth: JWT required for all endpoints")
    print("")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info"
    )
