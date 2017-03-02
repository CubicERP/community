import re
from openerp import netsvc, models, api, fields
from openerp.osv import osv
from openerp.tools.translate import _
_vat = lambda x: x.tax_code_id.parent_id.name == 'IVA'
document_type_map = {
    "DNI":      "D",
    "CUIL":     "L",
    "CUIT":     "T",
    "CPF":      "C",
    "CIB":      "C",
    "CIK":      "C",
    "CIX":      "C",
    "CIW":      "C",
    "CIE":      "C",
    "CIY":      "C",
    "CIM":      "C",
    "CIF":      "C",
    "CIA":      "C",
    "CIJ":      "C",
    "CID":      "C",
    "CIS":      "C",
    "CIG":      "C",
    "CIT":      "C",
    "CIH":      "C",
    "CIU":      "C",
    "CIP":      "C",
    "CIN":      "C",
    "CIQ":      "C",
    "CIL":      "C",
    "CIR":      "C",
    "CIZ":      "C",
    "CIV":      "C",
    "PASS":     "P",
    "LC":       "V",
    "LE":       "E",
};
responsability_map = {
    "IVARI":  "I", # Inscripto,
    "IVARNI": "N", # No responsable,
    "RM":     "M", # Monotributista,
    "IVAE":   "E", # Exento,
    "NC":     "U", # No categorizado,
    "CF":     "F", # Consumidor final,
    "RMS":    "T", # Monotributista social,
    "RMTIP":  "P", # Monotributista trabajador independiente promovido.
}

class account_invoice(models.Model):
    _name = "account.invoice"
    _inherit = "account.invoice"
    
    afip_printed = fields.Boolean('AFIP Printed', help="This invoice was printed through AFIP fiscal printer")
    
    @api.multi
    def action_move_create(self):
        self.action_fiscal_printer()
        return super(account_invoice,self).action_move_create()    
    
    @api.cr_uid_ids_context
    def action_fiscal_printer(self, cr, uid, ids, context=None):
        picking_obj = self.pool.get('stock.picking')
        user_obj = self.pool.get('res.users')
        sequence_obj = self.pool.get('ir.sequence')
        r = {}
#         if len(ids) > 1:
#             raise osv.except_osv(_(u'Cancelling Validation'),
#                                  _(u'Please, validate one ticket at time.'))
#             return False
        for inv in self.browse(cr, uid, ids, context):
            if inv.journal_id.use_fiscal_printer and not inv.afip_printed:
                # Check if amount is valid
                if (inv.amount_total > 25000):
                    raise osv.except_osv(_('Error!'),
                                         _("Total must less than 25000 $"))
                journal = inv.journal_id
                ticket={
                    "ticket_id": "account.invoice,%s"%inv.id,
                    "turist_ticket": False,
                    "debit_note": False,
                    "partner": {
                        "name": inv.partner_id.name,
                        "name_2": "",
                        "address": inv.partner_id.street,
                        "address_2": inv.partner_id.city,
                        "address_3": inv.partner_id.country_id.name,
                        "document_type": document_type_map.get(inv.partner_id.document_type_id.code, "D"),
                        "document_number": inv.partner_id.document_number,
                        "responsability": responsability_map.get(inv.partner_id.responsability_id.code, "F"),
                    },
                    "related_document": (picking_obj.search_read(cr, uid, [('origin','=',inv.origin)], ["name"]) +
                                         [{'name': _("No picking")}])[0]['name'],
                    "related_document_2": inv.origin or "",
                    "turist_check": "",
                    "lines": [ ],
                    "cut_paper": True,
                    "electronic_answer": False,
                    "print_return_attribute": False,
                    "current_account_automatic_pay": False,
                    "print_quantities": True,
                    "tail_no": 1 if inv.user_id.name else 0,
                    "tail_text": _("Saleman: %s") % inv.user_id.name if inv.user_id.name else "",
                    "tail_no_2": 0,
                    "tail_text_2": "",
                    "tail_no_3": 0,
                    "tail_text_3": "",
                }
                for line in inv.invoice_line:
                    ticket["lines"].append({
                        "item_action": "sale_item",
                        "as_gross": False,
                        "send_subtotal": True,
                        "check_item": False,
                        "collect_type": "q",
                        "large_label": "",
                        "first_line_label": "",
                        "description": "",
                        "description_2": "",
                        "description_3": "",
                        "description_4": "",
                        "item_description": line.name,
                        "quantity": line.quantity,
                        "unit_price": line.price_unit,
                        "vat_rate": ([ tax.amount*100 for tax in line.invoice_line_tax_id.filtered(_vat)]+[0.0])[0],
                        "fixed_taxes": 0,
                        "taxes_rate": 0
                    })
                    if line.discount > 0: ticket["lines"].append({
                        "item_action": "discount_item",
                        "as_gross": False,
                        "send_subtotal": True,
                        "check_item": False,
                        "collect_type": "q",
                        "large_label": "",
                        "first_line_label": "",
                        "description": "",
                        "description_2": "",
                        "description_3": "",
                        "description_4": "",
                        "item_description": "%5.2f%%" % line.discount,
                        "quantity": line.quantity,
                        "unit_price": line.price_unit * (line.discount/100.),
                        "vat_rate": ([ tax.amount*100 for tax in line.invoice_line_tax_id.filtered(_vat)]+[0.0])[0],
                        "fixed_taxes": 0,
                        "taxes_rate": 0
                    })
                if inv.type == 'out_invoice':
                    r = journal.make_ticket_factura(ticket)[inv.journal_id.id]
                elif inv.type == 'out_refund':
                    r = journal.make_ticket_notacredito(ticket)[inv.journal_id.id]
                
                # Verifing if the ticket was cancelled
                ticket_canceled = r and r.get('error', 'x') == 'ticket canceled'
                if r and 'error' in r and not ticket_canceled:
                    # Raise if an error and not cancelation happen
                    raise osv.except_osv(
                        _('Printer Error!'),
                        _('Printer return: %s') % r['error'])
                if 'document_type' not in r or 'document_number' not in r:
                    raise osv.except_osv(
                        _('Printer Error!'),
                        _('No number was assigned!'))
                    
                # Generate ticket number
                document_type = r['document_type']
                document_number = int(r['document_number'])
                
                if document_type <> inv.journal_id.journal_class_id.document_class_id.name:
                    raise osv.except_osv(
                        _('Journal Document Class Error'),
                        _('The document class associated to the invoice journal must be %s, check please !')%document_type)
                
                # If ticket was canceled
                if r.get('command', '') == 'cancel_ticket_factura':
                    raise osv.except_osv(
                        _('User Error'),
                        _('The printer work has been cancelled, you must cancel this invoice manually !'))
                
                if inv.journal_id.sequence_id.number_next_actual != document_number:
                    sequence_obj.write({'number_next_actual': document_number})
                #self.number = self.internal_number = sequence_obj.next_by_id(cr, uid, inv.journal_id.sequence_id.id,context=context)
                self.afip_printed = True
                
                
#         if not r:
#             return True
#         elif r and 'error' not in r:
#             return True
#         elif r and 'error' in r:
#             raise osv.except_osv(_(u'Cancelling Validation'),
#                                  _('Error: %s') % r['error'])
#         else:
#             raise osv.except_osv(_(u'Cancelling Validation'),
#                                  _(u'Unknown error.'))
