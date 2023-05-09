# This file is part of the cooperative_cashflow_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.pool import Pool
from . import sale
from . import purchase
from . import recibo
from . import account
from . import cashflow


def register():
    Pool.register(
        sale.Sale,
        sale.UpdateSaleProjectionStart,
        purchase.Purchase,
        purchase.UpdatePurchaseProjectionStart,
        recibo.Recibo,
        recibo.ReciboLote,
        recibo.UpdateReciboLoteProjectionStart,
        account.Account,
        cashflow.PrintCashFlowReportStart,
        module='cooperative_cashflow_ar', type_='model')
    Pool.register(
        sale.UpdateSaleProjection,
        purchase.UpdatePurchaseProjection,
        recibo.UpdateReciboLoteProjection,
        cashflow.PrintCashFlowReport,
        module='cooperative_cashflow_ar', type_='wizard')
    Pool.register(
        cashflow.CashFlowReport,
        module='cooperative_cashflow_ar', type_='report')
