from openerp.osv import osv,fields
from datetime import date
import string

class partner_region(osv.osv):
	_name = "res.partner.region"
	_description = "Region a la que pertenece el cliente"

	_columns = {
		'name': fields.char('Name',size=32),
		'printed_name': fields.char('Nombre impreso',size=64),
		'printed_address': fields.char('Direccion impresa',size=64),
		'printed_email': fields.char('E-mail impreso'),
		'printed_phone': fields.char('Tel.impreso'),
		}

partner_region()

class partner_canal(osv.osv):
	_name = "res.partner.canal"
	_description = "Canal al que pertenece el cliente"

	_columns = {
		'name': fields.char('Name',size=32),
		}
partner_canal()


class res_user(osv.osv):
	_name = "res.users"
	_inherit = "res.users"

	_columns = {
		'cod_vendedor_epicor': fields.char('Cod.Vendedor EPICOR',size=16),
		}
res_user()

class res_partner_category(osv.osv):
	_name = "res.partner.category"
	_inherit = "res.partner.category"

	_columns = {
		'pricelist_id': fields.many2one('product.pricelist',string="Pricelist"),
		}
res_partner_category()

class res_partner(osv.osv):
	_name = "res.partner"
	_inherit = "res.partner"

        def _check_phones(self, cr, uid, ids, context=None):
            obj = self.browse(cr, uid, ids[0], context=context)
	    if (obj.customer or obj.supplier) and obj.is_company:
            	if (not obj.phone) and (not obj.mobile):
                	return False
            return True

        def _check_null_values(self, cr, uid, ids, context=None):
            for obj in self.browse(cr, uid, ids, context=context):
                if obj.supplier and obj.is_company:
                    if (not obj.name) or (not obj.city) or (not obj.street) or (not obj.zip) or (not obj.email) \
                        or (not obj.document_number) or (not obj.document_type_id):
                        return False
                if obj.customer and obj.is_company:
                    if (not obj.name) or (not obj.city) or (not obj.street) or (not obj.user_id) or (not obj.zip) or (not obj.email) \
                        or (not obj.document_number) or (not obj.document_type_id) or (not obj.property_payment_term) \
                        or (not obj.region) or (not obj.canal):
                        return False
            return True

        def _update_warning_msgs(self,cr,uid,ids=None,context=None):
	    partner_ids = self.search(cr,uid,[('credit','>',0)])
	    for partner in self.browse(cr,uid,partner_ids):
	        val_warn_msg = {
			'sale_warn_msg': 'El cliente cuenta con una deuda de '+str(partner.credit)+' $',
			'sale_warn': 'warning',
			'invoice_warn_msg': 'El cliente cuenta con una deuda de '+str(partner.credit)+' $',
			'invoice_warn': 'warning',
			}
		return_id = self.write(cr,uid,partner.id,val_warn_msg)
	    return True


        _constraints = [
		#(_check_null_values, 'Nombre, calle, ciudad, codigo postal, email, CUIT, resp. fiscal, term.pago, canal, region y promotor\nson campos que no pueden ser nulos',['name','city','street','user_id','zip','email','region','canal']),
		#(_check_phones, 'Se debe ingresar el telefono o celular',['phone','mobile']),
		]

	_columns = {
		'cod_epicor': fields.char('Codigo EPICOR',size=10),
		# 'region': fields.selection((('1','BUE'),('2','ROS'),('3','CBA'),('4','MDQ'),('5','BBA'),('N/A','N/A')),'Region'),
		# 'region': fields.selection((('BUE','BUE'),('ROS','ROS'),('CBA','CBA'),('MDQ','MDQ'),('BBA','BBA'),('N/A','N/A')),'Region'),
		'region': fields.many2one('res.partner.region','Region'),
		# 'canal': fields.selection((('1','Distribuidor'),('3','Libreria'),('4','Instituciones/Escuelas'),('5','Colptores'),('6','Iglesias'),('9','Iglesias'),('N/A','N/A'),('7','Desconocido'),('8','Desconocido')),'Canal'),
		'canal': fields.selection((('Distribuidor','Distribuidor'),('Libreria','Libreria'),('Instituciones/Escuelas','Instituciones/Escuelas'),('Colptores','Colptores'),('Iglesias','Iglesias'),('Iglesias (9)','Iglesias'),('N/A','N/A'),('Desconocido','Desconocido'),('Desconocido','Desconocido')),'Canal'),
		'correlativo': fields.char('Nro. Correlativo Categoria',size=4),
	        'user_id': fields.many2one('res.users', 'Promotor', help='The internal user that is in charge of communicating with this contact if any.'),
		'warehouse_id': fields.many2one('stock.warehouse','Warehouse'),
		}

        def write(self, cr, uid, ids, vals, context=None):
            if 'name' in vals:
		if vals['name']:
		        vals['name'] = vals['name'].upper()
            if 'street' in vals:
		if vals['street']:
		        vals['street'] = vals['street'].upper()
            if 'city' in vals:
		if vals['city']:
		        vals['city'] = vals['city'].upper()
	    if 'category_id' in vals:
		if vals['category_id']:
			for value in vals['category_id'][0][2]:
				pricelist_id = self.pool.get('res.partner.category').browse(cr,uid,value).pricelist_id.id
				if pricelist_id:
					vals['property_product_pricelist'] = pricelist_id
            return super(res_partner, self).write(cr, uid, ids, vals, context=context)

        def create(self, cr, uid, vals, context=None):
            if 'name' in vals:
		if vals['name']:
		        vals['name'] = vals['name'].upper()
            if 'street' in vals:
		if vals['street']:
		        vals['street'] = vals['street'].upper()
            if 'city' in vals:
		if vals['city']:
		        vals['city'] = vals['city'].upper()
	    if not 'date' in vals:
		vals['date'] = date.today()
	    if 'category_id' in vals:
		if vals['category_id']:
			for value in vals['category_id'][0][2]:
				pricelist_id = self.pool.get('res.partner.category').browse(cr,uid,value).pricelist_id.id
				if pricelist_id:
					vals['property_product_pricelist'] = pricelist_id
            return super(res_partner, self).create(cr, uid, vals, context=context)

res_partner()
