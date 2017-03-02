# -*- coding: utf-8 -*-
from openerp import models, fields, _
from openerp import api
from datetime import date, timedelta


class crm_lead(models.Model):
    _name = "crm.lead"
    _inherit = "crm.lead"

    date_deadline = fields.Date(
        'Expected Closing',
        help="Estimate of the date on which the opportunity will be won.",
        required=True)
    categ_ids = fields.Many2many(
        'crm.case.categ',
        'crm_lead_category_rel',
        'lead_id',
        'category_id',
        'Tags',
        domain="['|', ('section_id', '=', section_id), "
        "('section_id', '=', False), "
        "('object_id.model', '=', 'crm.lead')]",
        help="Classify and analyze your lead/opportunity categories like: "
        "Training, Service",
        required=True)
    event_ids = fields.One2many('calendar.event', 'opportunity_id', 'Events')

    @api.v8
    @api.onchange('date_deadline')
    def onchange_date_deadline(self):
        self.set_event()
        import pdb; pdb.set_trace()

    @api.v8
    @api.multi
    def set_event(self, context=None):
        env = self.env
        alarm_id = env['calendar.alarm'].search([('name', '=', '1 day mail')])

        for lead in self:
            if lead.event_ids:
                for event in lead.event_ids:
                    vals = {
                        'start_date': lead.date_deadline,
                        'stop_date': lead.date_deadline,
                        'alarm_ids': [(6, 0, alarm_id.ids)]
                    }
                    event.write(vals)
            else:
                vals = {
                    'allday': True,
                    'start_date': lead.date_deadline,
                    'stop_date': lead.date_deadline,
                    'state': 'open',
                    'description':
                    _('Oportunity due %s\n Estimated amount %f') %
                    (lead.name, lead.planned_revenue or 0),
                    'name': lead.name,
                    'opportunity_id': lead.id,
                    'alarm_ids': [(6, 0, alarm_id.ids)],
                }
                env['calendar.event'].create(vals)

        return

    def _check_date(self, cr, uid, ids, context=None):
        obj = self.browse(cr, uid, ids[0], context=context)
        if not obj.date_deadline:
            return False
        if obj.date_deadline < obj.date_action:
            return False
        return True

    _constraints = [
        (
            _check_date,
            'Deadline should be higher than next action date.',
            ['date_deadline']
        ),
    ]

    _defaults = {
        'date_deadline': lambda *a: str(date.today()+timedelta(days=15)),
    }

crm_lead()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
