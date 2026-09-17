from app import app, _SECRET_KEY_DEFAULT

if not app.secret_key or not str(app.secret_key).strip():
    app.secret_key = _SECRET_KEY_DEFAULT
    app.config["SECRET_KEY"] = _SECRET_KEY_DEFAULT

if __name__ == "__main__":
    app.run()
