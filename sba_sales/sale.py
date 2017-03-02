from openerp.osv import osv,fields
from openerp.tools.translate import _
from datetime import date
from datetime import datetime
import string
import urlparse

class crm_case_section(osv.Model):
    _inherit = 'crm.case.section'

    _columns = {
        'discount': fields.float('Approval Discount'),
        'credit_tolerance': fields.float('Approbal Credit Tolerance'),
        'region_id': fields.many2one('res.partner.region', 'Region'),
    }

crm_case_section()

class sale_stockout(osv.osv):
	_name = "sale.stockout"
	_description = "Modelo con los productos que tuvieron stockout durante la confirmacion del pedido"

	_columns = {
		'date': fields.date('Fecha'),
		'product_id': fields.many2one('product.product','Producto'),
		'sale_id': fields.many2one('sale.order','Pedido'),
		'qty': fields.integer('Cantidad'),
		}


        def _update_stock_outs(self,cr,uid,ids=None,context=None):

		sale_obj = self.pool.get('sale.order')
		sale_ids = sale_obj.search(cr,uid,[('state','=','manual')])

		for sale in sale_obj.browse(cr,uid,sale_ids,context=context):
	       		for line in sale.order_line:
                        	if line.product_id.qty_available < line.product_uom_qty :
                                	stock_out_id = self.search(cr,uid,[('sale_id','=',sale.id),('product_id','=',line.product_id.id)])
		                        if not stock_out_id:
                		                vals_stock_out = {
                                	     	        'date': str(date.today()),
                                                	'product_id': line.product_id.id,
		                                        'sale_id': sale.id,
                		                        'qty': line.product_uom_qty,
                                	               }
                                        	return_id = self.create(cr,uid,vals_stock_out)

		return True

sale_stockout()

#class survey_input(osv.osv):
#	_name = "survey.user_input"
#	_inherit = "survey.user_input"

#	_columns = {
#		'order_id': fields.many2one('sale.order','Sale Order'),
#		}

#survey_input()


class survey_survey(osv.osv):
	_name = "survey.survey"
	_inherit = "survey.survey"

	_columns = {
		'order_ids': fields.one2many('sale.order','survey_id','Sale Order'),
		}

survey_survey()

class sale_order(osv.osv):
	_name = "sale.order"
	_inherit = "sale.order"

	_columns = {
	        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, readonly=True,\
				 help="Pricelist for current sales order."),
		'discount_ok': fields.boolean('Discount OK',readonly=True),
		# 'survey_input_id': fields.one2many('survey.user_input','opportunity_id','Survey Input'),
		'survey_id': fields.many2one('survey.survey','Survey'),
		}


	_defaults = {
		'discount_ok': False,
		# 'warehouse_id': lambda self,cr,uid, context: self.pool.get('res.users').browse(cr, uid, uid, context).partner_id.warehouse_id,
		}

	def action_quotation_send(self, cr, uid, ids, context=None):
        	'''
	        This function opens a window to compose an email, with the edi sale template message loaded by default
        	'''
	        assert len(ids) == 1, 'This option should only be used for a single id at a time'
		obj = self.browse(cr,uid,ids)
                if obj and not obj.discount_ok:
                        raise osv.except_osv(('Alerta!'), ("El descuento necesita ser aprobado"))
                        return None
		return super(sale_order, self).action_quotation_send(cr,uid,ids,context=context)


	def print_quotation(self, cr, uid, ids, context=None):
        	'''
	        This function prints the sales order and mark it as sent, so that we can see more easily the next step of the workflow
        	'''
	        assert len(ids) == 1, 'This option should only be used for a single id at a time'
		obj = self.browse(cr,uid,ids)
                if obj and not obj.discount_ok:
                        raise osv.except_osv(('Alerta!'), ("El descuento necesita ser aprobado"))
                        return None
        	# self.signal_workflow(cr, uid, ids, 'quotation_sent')
	        return self.pool['report'].get_action(cr, uid, ids, 'sba_sales.report_saleorder_sba', context=context)
			

	def send_survey(self, cr, uid, survey_id, partner_id, context=None):
		
		ir_model_data = self.pool.get('ir.model.data')
        	templates = ir_model_data.get_object_reference(cr, uid,
                                'survey', 'email_template_survey')
	        template_id = templates[1] if len(templates) > 0 else False

		survey = self.pool.get('survey.survey').browse(cr,uid,survey_id)
		
        	survey_response_obj = self.pool.get('survey.user_input')
	        partner_obj = self.pool.get('res.partner')
		partner = partner_obj.browse(cr,uid,partner_id)
        	mail_mail_obj = self.pool.get('mail.mail')
	        try:
        	    model, anonymous_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'portal', 'group_anonymous')
	        except ValueError:
        	    anonymous_id = None

		def create_response_and_send_mail(token, partner_id, email):
	            """ Create one mail by recipients and replace __URL__ by link with identification token """
        	    #set url
	            url = survey.public_url
        	    # url = urlparse.urlparse(url).path[1:]  # dirty hack to avoid incorrect urls
		    template_id = self.pool.get('email.template').search(cr,uid,[('model','=','survey.survey')])
		    template = self.pool.get('email.template').browse(cr,uid,template_id)
		    body = template.body_html
	            if token:
        	        url = url + '/' + token

	            # post the message
        	    values = {
                	'model': None,
	                'res_id': None,
        	        'subject': template.subject,
                	'body': body.replace("__URL__", url),
	                'body_html': body.replace("__URL__", url),
        	        'parent_id': None,
                	'partner_ids': partner_id and [(4, partner_id)] or None,
	                'notified_partner_ids': partner_id and [(4, partner_id)] or None,
	                'email_from': 'info@sba.org' or None,
        	        'email_to': partner.email,
		            }
	            mail_id = mail_mail_obj.create(cr, uid, values, context=context)
        	    mail_mail_obj.send(cr, uid, [mail_id], context=context)

	        def create_token(partner_id, email):
        	    if context.get("survey_resent_token"):
                	response_ids = survey_response_obj.search(cr, uid, [('survey_id', '=', survey_id), ('state', 'in', ['new', 'skip']), '|', ('partner_id', '=', partner_id), ('email', '=', email)], context=context)
	                if response_ids:
        	            return survey_response_obj.read(cr, uid, response_ids, ['token'], context=context)[0]['token']
        	        token = uuid.uuid4().__str__()
                	# create response with token
	                survey_response_obj.create(cr, uid, {
        	            'survey_id': survey_id,
                	    'deadline': datetime.now(),
	                    'date_create': datetime.now(),
        	            'type': 'link',
                	    'state': 'new',
	                    'token': token,
        	            'partner_id': partner_id,
                	    'email': email})
	                return token

               	token = create_token(partner_id, partner.email)
	        create_response_and_send_mail(token, partner_id, partner.email)

		return True
		
	def action_button_confirm(self, cr, uid, ids, context=None):
            r = super(sale_order,self).action_button_confirm(cr,uid,ids,context)
            obj = self.browse(cr,uid,ids)
            if obj.survey_id:
                    return_survey = self.send_survey(cr,uid,obj.survey_id.id,obj.partner_id.id,context)		
            return r
		
        def create(self, cr, uid, vals, context=None):
            vals['discount_ok'] = not float(vals.get('add_disc', 0.0)) > 0
            return super(sale_order, self).create(cr, uid, vals, context=context)

        def write(self, cr, uid, ids, vals, context=None):
            if ids:
                    if 'discount_ok' not in vals.keys():
                            obj = self.browse(cr, uid, ids[0], context=context)
                            if vals.get('state', obj.state) in ['draft']:
                                    vals['discount_ok'] = not float(vals.get('add_disc', obj.add_disc)) > 0

            return super(sale_order, self).write(cr, uid, ids, vals, context=context)

	def _check_validation_sba(self, cr, uid, ids, context = None):
            obj = self.browse(cr, uid, ids[0], context=context)
            if obj.state == 'manual' or obj.state == 'sent':
                    if obj.discount_ok:
                            return True
                    if obj.add_disc < 0.01:
                            return True
                    if not obj.discount_ok:
                            return False
            return True

	_constraints = [(_check_validation_sba, '\n\nUd acaba de otorgar un descuento superior al descuento que se le permite otorgar.\nPor favor, pida a su superior que autorice el pedido', ['add_disc','state']),
			]

	def approve_discount(self, cr, uid, ids, context=None):
            user_obj = self.pool.get('res.users')
            user = user_obj.browse(cr, uid, uid)
            r = {}
            for so in self.browse(cr, uid, ids, context=context):
                team = so.section_id

                while team and team.user_id.id != uid:
                    team = team.parent_id

                if not team:
                    """ No es responsable de ningun equipo """
                    discount = 0
                    credit_tolerance = 0
                else:
                    """ Es responsable de un equipo """
                    discount = team.discount
                    credit_tolerance = team.credit_tolerance

                discount_ok = so.add_disc <= discount

                if not discount_ok:
                    boss = so.section_id.user_id

                    if boss == user:
                        boss = so.section_id.parent_id.user_id if so.section_id.parent_id else False

                    if not boss:
                        message_id = self.message_post(cr, uid, [so.id],
                                                       subject=_('Request action'),
                                                       body=_('The sale order has not a valid sale team. Assign one.'))
                        self.pool.get('mail.message').set_message_read(cr, user.id, [message_id], False)
                    else:
                        self.message_subscribe_users(cr, uid, [so.id], user_ids=[boss.id])
                        message_id = self.message_post(cr, uid, [so.id],
                                                       subject=_('Request action'),
                                                       body=_('The user <b>%s</b> tried to approve this sale order, but the user does not have the authorization to approve such discount.\nAn approval request for this sale order has been created for user <b>%s</b>.') % (user.name, boss.name), to_read=True)
                        self.pool.get('mail.message').set_message_read(cr, boss.id, [message_id], False)
                else:
                    self.message_post(cr, uid, [so.id], body=_('The user <b>%s</b> approve this sale order with %4.2f%% discount.') % (user.name, so.add_disc))

                self.write(cr,uid,so.id, { 'discount_ok': discount_ok })

            return { }

sale_order()


class sale_order_line(osv.osv):
	_name = "sale.order.line"
	_inherit = "sale.order.line"

	def onchange_discount(self, cr, uid, ids, discount, context=None):
		obj = self.browse(cr,uid,ids)
		if obj.discount > discount:
			res['discount'] = discount
		else:
	        	warning = {
		            'title': _('Alerta Lista de Precios!'),
        		    'message' : _('Si cambia la lista de precios, no se modificaran los precios a los productos ya cargados.')
		        	}
        		return {'warning': warning, 'value': value}
        	return {'value': res}

        def _fnct_listprice_unit(self, cr, uid, ids, field_name, args, context=None):

                if context is None:
                    context = {}
                res = {}
		for id in ids:
        		obj = self.browse(cr, uid, id, context=context)
			if obj.product_uom_qty > 0:
		                res[obj.id] = obj.price_subtotal / obj.product_uom_qty
			else:
				res[obj.id] = 0
                return res

        #def write(self, cr, uid, ids, vals, context=None):
	#	obj = self.browse(cr,uid,ids)
	#	diff_discount = obj.discount - obj.original_discount
	#	if diff_discount > 0:
	#		order_id = obj.order_id
	#		vals = {}
	#		vals['discount_ok'] = False
	#		return_id = self.pool.get('sale.order').write(cr,uid,order_id.id,vals,context=context)
			
        #	return super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

        #def create(self, cr, uid, vals, context=None):
	#	if 'discount' in vals.keys():
	#		vals['original_discount'] = vals['discount']
        #	return super(sale_order_line, self).create(cr, uid, vals, context=context)

	_columns = {
		'original_price': fields.related('product_id','list_price',string='Original Price',readonly=True),
		'original_discount': fields.float('Original Discount',readonly=True),
                'list_price_perunit': fields.function(_fnct_listprice_unit, string='Precio Publico'),
		}


sale_order_line()
