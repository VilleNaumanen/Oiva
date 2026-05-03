import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port  = int(os.environ.get("PORT", "5000"))
    print(f"Oiva running at http://localhost:{port}")
    app.run(debug=debug, port=port)
