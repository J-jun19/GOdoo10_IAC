# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo import exceptions
import traceback


class IacRfqCostUpReason(models.Model):
    _name = 'iac.rfq.cost.up.reason'
    _table = "iac_rfq_cost_up_reason"
    _order = 'id asc'
    _rec_name = 'description'
    _description = u'涨价原因对照表'
    # _sql_constraints = [('item_no_description_uniq', 'unique(item_no,description)', '請勿輸入重複數據！'), ]

    item_no = fields.Char(string=u'原因序号')
    description = fields.Char(string=u'描述')
    comment = fields.Char(string=u'备注')
    active = fields.Boolean(string=u'生效标记')

    @api.model
    def create(self, vals):
        if vals.get('item_no'):
            if self.search([('item_no', '=', "".join(vals['item_no'].split()))]):
                raise UserError(u'不能創建重複的原因序號！')
        if vals.get('description'):
            if self.search([('description', '=', vals.get('description'))]):
                raise UserError(u'不能創建重複的原因描述！')
            try:
                result = super(IacRfqCostUpReason, self).create(vals)
                return result
            except:
                self.env.cr.rollback()
                raise exceptions.ValidationError(traceback.format_exc())

    @api.multi
    def write(self, vals):
        if vals.get('item_no'):
            if self.search([('item_no', '=', "".join(vals['item_no'].split()))]):
                raise UserError(u'修改的原因序號已存在！')
        if vals.get('description'):
            if self.search([('description', '=', vals.get('description'))]):
                raise UserError(u'修改的原因描述已存在！')
        try:
            result = super(IacRfqCostUpReason, self).write(vals)
            return result
        except:
            self.env.cr.rollback()
            raise exceptions.ValidationError(traceback.format_exc())

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            if record['item_no']:
                item_no = record['item_no']
            else:
                item_no = ''
            if record['description']:
                item_no = item_no + '. ' + record['description']
            res.append((record['id'], item_no))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain += ['|', ('item_no', operator, name), ('description', operator, name)]
        rfq_reason = self.search(domain + args, limit=limit)
        return rfq_reason.name_get()


class IacRfqNewVsOld(models.Model):
    _name = 'iac.rfq.new.vs.old'
    _table = "iac_rfq_new_vs_old"
    _order = 'id desc'
    _description = u'当前建立的rfq与全部厂区比较有效单价'

    current_rfq_id = fields.Many2one('iac.rfq',string=u'当前RFQ ID',index=True)
    import_rfq_id = fields.Many2one('iac.rfq.import',string=u'中间状态RFQ ID',index=True)
    old_rfq_id = fields.Many2one('iac.rfq',string=u'旧的RFQ ID',index=True)
    price_compare = fields.Selection([("up",u"价格上涨"),
                                      ("down",u"价格下降"),
                                      ("nochange",u"价格不变")],string=u"价格变动")
    new_flag = fields.Selection([("Y","Yes"),
                                 ("N","No")],string=u"对比资料组最新标志")
    ratio = fields.Float(string=u'变动幅度',digits=(19,4))
    old_rfq_vendor_id = fields.Many2one('iac.vendor.rfq',string='Vendor Code',related='old_rfq_id.vendor_id')
    old_rfq_part_id = fields.Many2one('material.master',string='Part Code',related='old_rfq_id.part_id')
    old_rfq_plant_id = fields.Many2one('pur.org.data',string='Plant Code',related='old_rfq_id.plant_id')
    old_rfq_buy_id = fields.Many2one('buyer.code',string='Buyer Code',related='old_rfq_id.buyer_code')
    old_rfq_division_id = fields.Many2one('division.code',string='Division Code',related='old_rfq_id.division_id')
    old_rfq_currency_id = fields.Many2one('res.currency',string='Currency',related='old_rfq_id.currency_id')
    old_rfq_valid_from = fields.Date(string='Valid From',related='old_rfq_id.valid_from')
    old_rfq_valid_to = fields.Date(string='Valid To',related='old_rfq_id.valid_to')
    old_rfq_price_control = fields.Selection([('1','by PO date'),('2','by delivery date')],string='Price Control',related='old_rfq_id.price_control')
    old_rfq_price_unit = fields.Float(string='Price',related='old_rfq_id.input_price')
    old_rfq_tax = fields.Selection([
                               ('J0','0 % input tax, China'),
                               ('J1','17 % input tax, China'),
                               ('J2','13 % input tax, China'),
                               ('J3','6 % input tax, China'),
                               ('J4','4 % input tax, China'),
                               ('J5','7 % input tax, China'),
                               ('J6','3 % input tax, China'),
                               ('J7','11 % input tax, China'),
                               ('J8','5 % input tax, China'),
                               ('J9', '16% input tax, China'),
                               ('JA', '10% input tax, China'),
                               ('11','5% Expense/Material -Deductible'),
                               ('V0','No Tax Transaction Or Foreign Purchase '),
                               ],string='Tax',related='old_rfq_id.tax')






