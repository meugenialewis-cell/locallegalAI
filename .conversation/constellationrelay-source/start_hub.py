"""
Start the Connective Memory Hub API on port 8000
Run this alongside the Streamlit app for external API access
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "v2.hub.memory_hub:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
