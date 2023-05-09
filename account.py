# This file is part of the cooperative_cashflow_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Account(metaclass=PoolMeta):
    __name__ = 'account.account'

    cashflow_report = fields.Boolean('Use in cashflow report', select=True)

    @staticmethod
    def default_cashflow_report():
        return False
