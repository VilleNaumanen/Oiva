import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    print("Oiva running at http://localhost:5000")
    app.run(debug=True, port=5000)
