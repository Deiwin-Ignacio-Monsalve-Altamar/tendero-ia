import os

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///tendero.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
