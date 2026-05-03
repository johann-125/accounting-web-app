from datetime import datetime
from models import db


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reference = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='unpaid', nullable=False)
    # Status: unpaid, paid
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    expense_account = db.relationship('Account', backref='expenses')
    creator = db.relationship('User', backref='expenses')
    payments = db.relationship(
        'Payment',
        foreign_keys='Payment.expense_id',
        backref='expense',
        lazy=True
    )

    @property
    def amount_paid(self):
        return sum(float(p.amount) for p in self.payments)

    @property
    def balance_due(self):
        return float(self.amount) - self.amount_paid

    @property
    def status_badge(self):
        badges = {
            'unpaid': 'danger',
            'paid': 'success'
        }
        return badges.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Expense {self.expense_number}>'
