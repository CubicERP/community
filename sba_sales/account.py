# -*- coding: utf-8 -*-
from openerp.osv import osv


class account_invoice(osv.osv):
    _name = "account.invoice"
    _inherit = "account.invoice"

    def _convert_ref(self, ref):
        return (ref or '').replace('/', '')

account_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
