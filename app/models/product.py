from app.extensions import db

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    canonical_name = db.Column(db.String(100), nullable=False)
    aliases = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "business_id": self.business_id,
            "name": self.name,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "price": self.price,
            "is_active": self.is_active
        }
