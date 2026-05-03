from datetime import datetime
from models import db


class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id = db.Column(db.Integer, primary_key=True)
    entry_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    reference = db.Column(db.String(50), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lines = db.relationship(
        'JournalLine',
        backref='journal_entry',
        lazy=True,
        cascade='all, delete-orphan'
    )
    creator = db.relationship('User', backref='journal_entries')

    @property
    def total_debit(self):
        return sum(float(line.debit) for line in self.lines)

    @property
    def total_credit(self):
        return sum(float(line.credit) for line in self.lines)

    @property
    def is_balanced(self):
        return abs(self.total_debit - self.total_credit) < 0.01

    def __repr__(self):
        return f'<JournalEntry {self.entry_number}>'


class JournalLine(db.Model):
    __tablename__ = 'journal_lines'

    id = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    debit = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    credit = db.Column(db.Numeric(15, 2), default=0, nullable=False)

    def __repr__(self):
        return f'<JournalLine acct={self.account_id} Dr={self.debit} Cr={self.credit}>'
