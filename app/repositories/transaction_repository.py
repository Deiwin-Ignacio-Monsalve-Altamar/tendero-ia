from app.extensions import db
from app.models.business import Business
from app.models.transaction import Transaction, TransactionItem
from datetime import datetime, date
from sqlalchemy import func

class TransactionRepository:
    @staticmethod
    def create_confirmed_sale(phone_number, business_id, items, total_amount, raw_input):
        if Business.query.filter_by(id=business_id, phone_number=phone_number).first() is None:
            raise ValueError("phone_number does not belong to business_id")
        new_transaction = Transaction(
            business_id=business_id,
            phone_number=phone_number,
            total_amount=total_amount,
            status='CONFIRMED',
            raw_input=raw_input
        )
        db.session.add(new_transaction)
        db.session.flush() # Get ID

        for item in items:
            t_item = TransactionItem(
                transaction_id=new_transaction.id,
                raw_name=item.raw_name,
                canonical_name=item.canonical_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal
            )
            db.session.add(t_item)
        
        db.session.commit()
        return new_transaction

    @staticmethod
    def get_daily_total(business_id):
        today = date.today()
        total = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.business_id == business_id,
            Transaction.status == 'CONFIRMED',
            func.date(Transaction.created_at) == today
        ).scalar()
        return total or 0.0

    @staticmethod
    def get_confirmed_sales(business_id):
        return Transaction.query.filter_by(business_id=business_id, status='CONFIRMED').order_by(Transaction.created_at.desc()).all()

    @staticmethod
    def get_confirmed_total(business_id):
        total = db.session.query(func.sum(Transaction.total_amount)).filter_by(
            business_id=business_id, status='CONFIRMED'
        ).scalar()
        return total or 0.0
