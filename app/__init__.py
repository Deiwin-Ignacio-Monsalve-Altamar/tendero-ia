from flask import Flask
from sqlalchemy import inspect, text
from app.extensions import db
from app.config import Config
from app.api.health.routes import health_bp
from app.api.demo.routes import demo_bp
from app.api.products.routes import products_bp
from app.utils.error_handlers import register_error_handlers

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        # create_all creates missing tables but does not add columns to existing tables.
        if "products" in inspect(db.engine).get_table_names():
            columns = {column["name"] for column in inspect(db.engine).get_columns("products")}
            if "aliases" not in columns:
                db.session.execute(text("ALTER TABLE products ADD COLUMN aliases VARCHAR(500)"))
                db.session.commit()

    app.register_blueprint(health_bp, url_prefix='/api/v1')
    app.register_blueprint(demo_bp, url_prefix='/api/v1/demo')
    app.register_blueprint(products_bp, url_prefix='/api/v1/products')
    
    register_error_handlers(app)

    return app
