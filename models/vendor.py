from datetime import datetime
from models import db


class Vendor(db.Model):
    __tablename__ = 'vendors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)
    company = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    expenses = db.relationship('Expense', backref='vendor', lazy=True)

    @property
    def balance(self):
        """Outstanding accounts payable balance."""
        return sum(float(exp.amount) for exp in self.expenses if exp.status == 'unpaid')

    @property
    def total_expenses(self):
        return sum(float(exp.amount) for exp in self.expenses)

    def __repr__(self):
        return f'<Vendor {self.name}>'
