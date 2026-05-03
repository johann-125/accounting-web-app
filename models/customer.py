from datetime import datetime
from models import db


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)
    company = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship('Invoice', backref='customer', lazy=True)

    @property
    def balance(self):
        """Outstanding accounts receivable balance."""
        return sum(
            inv.balance_due for inv in self.invoices
            if inv.status not in ('cancelled', 'paid')
        )

    @property
    def total_invoiced(self):
        return sum(inv.total for inv in self.invoices if inv.status != 'cancelled')

    @property
    def total_paid(self):
        return self.total_invoiced - self.balance

    def __repr__(self):
        return f'<Customer {self.name}>'
