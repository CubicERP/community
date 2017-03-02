# -*- coding: utf-8 -*-
from openerp import api, models, fields, _
from openerp.exceptions import except_orm
import re

vat_re = re.compile(r'ar(\d\+)')


class res_partner(models.Model):
    _inherit = 'res.partner'

    responsability_id = fields.Many2one('afip.responsability', 'Responsability')
    document_type_id = fields.Many2one('afip.document_type', 'Document type')
    document_number = fields.Char('Document number')
    iibb = fields.Char('Gross Income')
    start_date = fields.Date('Initial date activity')

    @api.onchange('vat')
    def onchange_vat(self):
        vat_match = vat_re.match(self.vat)
        if vat_match:
            mod_obj = self.env['ir.model.data']
            cuit_id = mod_obj.get_object_reference('l10n_ar_invoice', 'dt_CUIT')
            self.document_type_id = cuit_id
            self.document_number = mod_obj.group(1)

    @api.onchange('document_type_id', 'document_number')
    def onchange_ar_document(self):
        mod_obj = self.env['ir.model.data']
        cuit_id = mod_obj.get_object_reference('l10n_ar_invoice', 'dt_CUIT')[1]
        if cuit_id == self.document_type_id.id and \
                self.check_vat_ar(self.document_number):
            self.vat = "AR%s" % self.document_number
        elif cuit_id == self.document_type_id.id:
            return {
                'warning': {'title': _('Invalid CUIT'),
                            'message': _('Please, set a valid CUIT number')}
            }

    @api.multi
    def afip_validation(self):
        """
        Hay que validar si el partner no es de tipo 'consumidor final'
        tenga un CUIT asociado.
            - Si el cuit es extrangero, hay que asignar a document_number y
            document_type los correspondientes a la interpretación argentina
            del CUIT.
            - Si es responsable monotributo hay que asegurarse que tenga vat
            asignado. El documento y número de documento deberían ser DNI.
            - Si es responsable inscripto y persona juridica indicar el cuit
            copia del VAT. El objetivo es que en la generación de factura
            utilice la información de document_type y document_number.

            Otra opción es asignar a la argentina los prefijos:
                'cuit' 'dni' 'ci', etc...

        Del prefijo se toma el número de documento. Que opinanará la comunidad?
        """

        for part in self:
            pass

        return True

    @api.returns('account.journal')
    @api.one
    def prefered_journals(self, company_id, type):
        """
        Devuelve la lista de journals disponibles para este partner.
        """
        # Set list of valid journals by partner responsability
        company_obj = self.env['res.company']
        journal_obj = self.env['account.journal']

        partner = self
        company = company_obj.browse(company_id)
        responsability = partner.responsability_id

        if responsability.issuer_relation_ids is None:
            return []

        type_map = {
            'out_invoice': ['sale'],
            'out_refund': ['sale_refund'],
            'in_invoice': ['purchase'],
            'in_refund': ['purchase_refund'],
        }

        if not company.partner_id:
            raise except_orm(
                _('Error!'),
                _('Your company has not setted any partner'))

        if not company.partner_id.responsability_id:
            raise except_orm(
                _('Error!'),
                _('Your company has not setted any responsability'))

        cr = self.env.cr
        cr.execute(
            """
            SELECT DISTINCT J.id, J.name, IRSEQ.number_next
            FROM account_journal J
            LEFT join ir_sequence IRSEQ on (J.sequence_id = IRSEQ.id)
            LEFT join afip_journal_class JC on (J.journal_class_id = JC.id)
            LEFT join afip_document_class DC on
            (JC.document_class_id = DC.id)
            LEFT join afip_responsability_relation RR on
            (DC.id = RR.document_class_id)
            WHERE
            (RR.id is Null OR
                (RR.id is not Null AND
                RR.issuer_id = %s AND
                RR.receptor_id = %s)) AND
            J.type in %s AND
            J.id is not NULL AND
            J.sequence_id is not NULL
            AND IRSEQ.number_next is not NULL
            ORDER BY IRSEQ.number_next DESC;
            """, (
                company.partner_id.responsability_id.id,
                partner.responsability_id.id,
                tuple(type_map[type])))

        journal_ids = [x[0] for x in cr.fetchall()]
        journal_ids = journal_obj.search([('id', 'in', journal_ids)])

        return journal_ids

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
