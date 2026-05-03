from datetime import datetime
from models import db


ACCOUNT_TYPES = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense']

# Normal balance side per account type
DEBIT_NORMAL = ['Asset', 'Expense']
CREDIT_NORMAL = ['Liability', 'Equity', 'Revenue']


class Account(db.Model):
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(20), nullable=False)  # Asset, Liability, Equity, Revenue, Expense
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Self-referential relationship
    children = db.relationship('Account', backref=db.backref('parent', remote_side=[id]), lazy=True)
    journal_lines = db.relationship('JournalLine', backref='account', lazy=True)

    @property
    def debit_total(self):
        from sqlalchemy import func
        from models.journal import JournalLine
        result = db.session.query(func.sum(JournalLine.debit)).filter_by(account_id=self.id).scalar()
        return float(result or 0)

    @property
    def credit_total(self):
        from sqlalchemy import func
        from models.journal import JournalLine
        result = db.session.query(func.sum(JournalLine.credit)).filter_by(account_id=self.id).scalar()
        return float(result or 0)

    @property
    def balance(self):
        """Net balance based on normal side of account."""
        if self.account_type in DEBIT_NORMAL:
            return self.debit_total - self.credit_total
        else:
            return self.credit_total - self.debit_total

    def balance_for_period(self, start_date=None, end_date=None):
        """Calculate balance filtered by date range."""
        from sqlalchemy import func
        from models.journal import JournalLine, JournalEntry

        query_dr = db.session.query(func.sum(JournalLine.debit)).join(JournalEntry).filter(
            JournalLine.account_id == self.id
        )
        query_cr = db.session.query(func.sum(JournalLine.credit)).join(JournalEntry).filter(
            JournalLine.account_id == self.id
        )
        if start_date:
            query_dr = query_dr.filter(JournalEntry.date >= start_date)
            query_cr = query_cr.filter(JournalEntry.date >= start_date)
        if end_date:
            query_dr = query_dr.filter(JournalEntry.date <= end_date)
            query_cr = query_cr.filter(JournalEntry.date <= end_date)

        dr = float(query_dr.scalar() or 0)
        cr = float(query_cr.scalar() or 0)

        if self.account_type in DEBIT_NORMAL:
            return dr - cr
        else:
            return cr - dr

    def __repr__(self):
        return f'<Account {self.code}: {self.name}>'
