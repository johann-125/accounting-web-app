from datetime import datetime
from models import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    payment_type = db.Column(db.String(20), nullable=False)  # 'invoice' or 'expense'
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    # The cash/bank account used for payment
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payment_account = db.relationship('Account', backref='payments')
    creator = db.relationship('User', backref='payments')

    def __repr__(self):
        return f'<Payment {self.payment_number}>'
