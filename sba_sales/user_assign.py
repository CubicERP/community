##############################################################################
# 
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
from datetime import date
from datetime import datetime
from openerp import netsvc


class crm_lead_user_assign(osv.osv_memory):
	_name = 'crm.lead.user.assign'
	_description = 'CRM Lead User Wizard'

	_columns = {
		'user_id': fields.many2one('res.users',string='Promotor a delegar',required=True)
		}	

	def user_assign(self, cr, uid, ids, context=None):

		lead_ids = context['active_ids']
		obj = self.browse(cr,uid,ids)
		vals_crm_lead = {
			'user_id': obj.user_id.id
			}
		name = ''
		for lead in self.pool.get('crm.lead').browse(cr,uid,lead_ids):
			name = name + ', ' + lead.name

		return_id = self.pool.get('crm.lead').write(cr,uid,lead_ids,vals_crm_lead)

		message_data = {
		    'type': 'notification',
		    'subject': "Se le acaba de asignar una oportunidad",
		    'body': "Se le asigno a oportunidad "+name,
		    'partner_ids': [(4,obj.user_id.partner_id.id)],
		    }

		msg_obj = self.pool.get('mail.message')
		msg_obj.create(cr, uid, message_data)

	        return {}

crm_lead_user_assign()


