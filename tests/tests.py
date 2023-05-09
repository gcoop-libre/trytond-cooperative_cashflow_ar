# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class CooperativeCashflowArTestCase(ModuleTestCase):
    'Test Account Inflation Adjustment module'
    module = 'cooperative_cashflow_ar'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CooperativeCashflowArTestCase))
    return suite
