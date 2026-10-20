from app.extensions import db
from datetime import datetime

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="CONFIRMED") # PENDING_CONFIRMATION, CONFIRMED, CANCELLED
    raw_input = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('TransactionItem', backref='transaction', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "business_id": self.business_id,
            "phone_number": self.phone_number,
            "total_amount": self.total_amount,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "items": [item.to_dict() for item in self.items]
        }

class TransactionItem(db.Model):
    __tablename__ = 'transaction_items'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    raw_name = db.Column(db.String(100), nullable=False)
    canonical_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "raw_name": self.raw_name,
            "canonical_name": self.canonical_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "subtotal": self.subtotal
        }
