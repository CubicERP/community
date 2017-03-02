# -*- coding: utf-8 -*-
from openerp import models


class account_invoice(models.Model):
    _inherit = "account.invoice"

    def afip_validation(self):
        """
        Si la factura ya usa la impresora fiscal,
        entonces no chequeo.
        """
        r = True
        for inv in self:
            if not inv.journal_id.use_fiscal_printer:
                r = r and super(account_invoice, inv).afip_validation()

        return r

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
