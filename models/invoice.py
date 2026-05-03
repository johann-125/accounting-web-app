from datetime import datetime
from models import db


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='unpaid', nullable=False)
    # Status: unpaid, partial, paid, cancelled
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lines = db.relationship(
        'InvoiceLine',
        backref='invoice',
        lazy=True,
        cascade='all, delete-orphan'
    )
    payments = db.relationship(
        'Payment',
        foreign_keys='Payment.invoice_id',
        backref='invoice',
        lazy=True
    )
    creator = db.relationship('User', backref='invoices')

    @property
    def total(self):
        return sum(line.total for line in self.lines)

    @property
    def amount_paid(self):
        return sum(float(p.amount) for p in self.payments)

    @property
    def balance_due(self):
        return self.total - self.amount_paid

    @property
    def status_badge(self):
        badges = {
            'unpaid': 'danger',
            'partial': 'warning',
            'paid': 'success',
            'cancelled': 'secondary'
        }
        return badges.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class InvoiceLine(db.Model):
    __tablename__ = 'invoice_lines'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), default=1, nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)

    revenue_account = db.relationship('Account', backref='invoice_lines')

    @property
    def total(self):
        return float(self.quantity) * float(self.unit_price)

    def __repr__(self):
        return f'<InvoiceLine {self.description}>'
