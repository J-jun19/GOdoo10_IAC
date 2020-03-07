# -*- coding: utf-8 -*-

import json
import threading
import xlwt
import time, base64
import datetime
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from xlrd import open_workbook
from odoo import models, fields, api
import psycopg2
import logging
from dateutil.relativedelta import relativedelta
from StringIO import StringIO
import pdb
import traceback
import math
import traceback, logging, types, json
from odoo.odoo_env import odoo_env

_logger = logging.getLogger(__name__)


def is_float_valid(str_val):
    """
    返回2个值
    对出现科学计数法的字符串转换为标准字符串
    1   处理是否成功
    2   转换成的数值
    :param str_val:
    :return:
    """
    try:
        float_val = float(str_val)
        # 获取允许范围之外的小数部分
        input_price = float_val

        # 扩大10 的6次方倍
        try_price = input_price * math.pow(10, 6)

        # 减去整数部分获得小数部分
        digits_part = abs(round(try_price - round(try_price), 2))
        price_unit = 0
        # 如果小数部分大于0.0001 那么表示超过6位，反之小于6位
        if (digits_part > 0.0001):
            # 1000的不满足,尝试10000
            return False, "%f" % (float_val,)
        else:
            return True, "%f" % (float_val,)
    except:
        traceback.print_exc()
        pass
    return False, 0


# def calcu_rfq_price(vals):
#     if "input_price" not in vals:
#         return
#     digits_count=vals.get("digits_count",0)
#
#
#     #获取允许范围之外的小数部分
#     input_price=vals["input_price"]
#     return_vals={
#         "input_price":input_price
#     }
#     rfq_price_test=input_price*1000*math.pow(10,digits_count)
#
#     digits_part_test=float("%.2f"%(rfq_price_test))-int("%.0d"%(rfq_price_test))
#
#     price_unit=0
#     #浮点位数问题导致，做特殊处理,小数部分等于1,表明1000的price_unit够用
#     if  (digits_part_test==1.0):
#         price_unit=1000
#         return_vals["price_unit"]=price_unit
#         return_vals["rfq_price"]=round(price_unit*input_price,digits_count)
#         return return_vals
#
#
#     if (digits_part_test>=0.01):
#         #1000的不满足,尝试10000
#         rfq_price_test=input_price*10000*math.pow(10,digits_count)
#         full_price=float("%.2f"%(rfq_price_test))
#         int_part_price=float("%.0d"%(rfq_price_test))
#         digits_part=float("%.2f"%(rfq_price_test))-int("%.0d"%(rfq_price_test))
#
#         price_unit=10000
#         return_vals["price_unit"]=price_unit
#         #存在小数的情况下,精度不允许的情况下进行截断处理
#         if digits_part>=0.01 and digits_count==0:
#             return_vals["rfq_price"]=int("%.0d"%(input_price*10000))
#         else:
#             return_vals["rfq_price"]=round(input_price*10000,digits_count)
#     else:
#         price_unit=1000
#         return_vals["price_unit"]=price_unit
#         return_vals["rfq_price"]=round(price_unit*input_price,digits_count)
#
#
#     return return_vals


def calcu_rfq_price(vals):
    def get_price_info(input_price, digits_count, price_unit):
        """
        输入参数是原始价格和需要的小数位
        返回值是价格和最后一位小数位
        :param price_str:
        :return:
        """
        # 获取按照格式获得的价格,截取不进行四舍五入
        rfq_test_price = input_price * price_unit
        format_str = "{:." + str(digits_count + 1) + "f}"
        price_str = format_str.format(rfq_test_price)

        point_pos = price_str.index(".")
        price_str_3 = price_str[0:point_pos + digits_count + 1]
        price_return = float(price_str_3)
        last_digit = int(price_str[point_pos + digits_count + 1:point_pos + digits_count + 2])
        return price_return, last_digit

    if "input_price" not in vals:
        return
    digits_count = vals.get("digits_count", 0)

    # 获取允许范围之外的小数部分
    input_price = vals["input_price"]
    return_vals = {
        "input_price": input_price
    }

    price_unit = 1000

    # 从科学计数法字串中获取价格和小数位超出有效部分,例如允许2位小数，那么这个值就是小数位第3位
    rfq_price, last_digit = get_price_info(input_price, digits_count, price_unit)
    if last_digit == 0:
        return_vals["rfq_price"] = rfq_price
        return_vals["price_unit"] = 1000
    else:
        # 尝试price_unit=10000
        price_unit = 10000
        return_vals["price_unit"] = 10000
        # 转换为科学计数法字串
        rfq_price, last_digit = get_price_info(input_price, digits_count, price_unit)
        return_vals["rfq_price"] = rfq_price
    return return_vals


class IacVendorRfq(models.Model):
    _inherit = "iac.vendor"
    _name = 'iac.vendor.rfq'
    _table = 'iac_vendor'
    _description = u"Vendor Info"


class IacCWRW(models.Model):
    _name = 'iac.cw.rw'
    _order = 'sequence'

    sequence = fields.Integer('Sequence')
    code_master_id = fields.Char('code_master_id')
    description = fields.Char('Description')


class IacRfq(models.Model):
    """docstring for IacRfqRfq"""
    _name = 'iac.rfq'
    _description = 'RFQ'
    _order = "id desc"

    note = fields.Text('Memo')
    # vendor input
    input_price = fields.Float(string="Price", digits=(18, 6))
    orig_input_price = fields.Float(related='last_rfq_id.input_price', string="Original Price", readonly=True)
    rfq_price = fields.Float(string="Price", digits=(18, 2))
    valid_from = fields.Date('Valid From', index=True)
    valid_to = fields.Date('Valid To', index=True)
    moq = fields.Integer(string="MOQ")
    mpq = fields.Integer(string="MPQ")
    lt = fields.Integer(string="LTIME")
    cw = fields.Selection(string="CW", selection='_selection_cw')
    rw = fields.Selection(string="RW", selection='_selection_rw')
    document_base = fields.Selection([('po', 'PO base'), ('delivery', 'Delivery Base')], string='Document base')
    # six factor: moq/mpq/lt/cw/rw/tax
    # J9	16% input tax, China 购买货物,接受加工、修理修配劳务
    # JA	10% input tax, China 购买暖气，邮政服务等
    tax = fields.Selection([
        ('J0', 'J0 0% input tax, China'),
        ('J1', 'J1 17% input tax, China'),
        ('J2', 'J2 13% input tax, China'),
        ('J3', 'J3 6% input tax, China'),
        ('J4', 'J4 4% input tax, China'),
        ('J5', 'J5 7% input tax, China'),
        ('J6', 'J6 3% input tax, China'),
        ('J7', 'J7 11% input tax, China'),
        ('J8', 'J8 5% input tax, China'),
        ('J9', 'J9 16% input tax, China'),
        ('JA', 'JA 10% input tax, China'),
        ('11', '11 5% Expense/Material -Deductible'),
        ('V0', 'V0 No Tax Transaction Or Foreign Purchase '),
    ], string="Tax")

    price_unit = fields.Float('Price unit')
    vendor_id = fields.Many2one('iac.vendor.rfq', string='Vendor', index=True)
    name = fields.Char(string="RFQ#", index=True, default="New")

    part_id = fields.Many2one('material.master', string='Part No#', index=True)
    part_code = fields.Char('Part NO.')
    plant_id = fields.Many2one('pur.org.data', string='Plant Code')
    division_id = fields.Many2one('division.code', string='Divsion', readonly=True)
    buyer_code = fields.Many2one('buyer.code', string='BuyerCode')
    purchase_org_id = fields.Many2one('vendor.plant', 'Purchase Orgnization')
    text = fields.Text('Webflow Message')
    currency_id = fields.Many2one('res.currency', string='Currency')
    state = fields.Selection([
        ('draft', 'Draft'),  # quote
        ('sent', 'Sent'),
        ('replay', 'Replied'),
        ('as_upload', 'AS Upload'),
        ('rfq', 'RFQ'),  # rfq
        # ('pending', 'Pending'),
        ('wf_ok', 'Webflow Sent'),
        ('wf_fail', 'Webflow Fail'),
        ('wf_approved', 'Webflow Approved'),
        ('wf_unapproved', 'Webflow Unapproved'),
        ('sap_ok', 'Complete'),
        ('sap_fail', 'SAP Fail'),
        # ('history', 'Info record history'),
        ('cancel', 'Cancel'),
        ('done', 'Done'),
        ('open', 'Open'),  # mass
        ('processing', 'Processing'),
        ('reason', 'Reason')
    ], string='Status', default='draft', index=True)
    sap_price = fields.Monetary('Current SAP Price')
    cost_up = fields.Boolean(string="Cost Up")
    low_by_all_site = fields.Boolean(string="Low Price By All Site")
    disapproval_comm = fields.Text(string="Disapproval Comments")
    reason_code = fields.Text(string="Reason")
    manufacturer_part_no = fields.Char('Manufacturer Part No')
    release_flag = fields.Char('Release Flag')
    uom = fields.Integer('Uom')
    line_text = fields.Char(string="Line text")
    vendor_part_no = fields.Char('Vendor Part No')
    order_reason = fields.Char(string="order_reason")

    last_rfq_id = fields.Many2one('iac.rfq', 'Last RFQ')
    orig_price = fields.Float(related='last_rfq_id.input_price', string="Original Price", readonly=True)

    orig_valid_from = fields.Date(related='last_rfq_id.valid_from', string='Original valid from', readonly=True)
    orig_valid_to = fields.Date(related='last_rfq_id.valid_to', string='Original valid to', readonly=True)
    orig_lt = fields.Integer(related='last_rfq_id.lt', string="Original LTIME", readonly=True)
    orig_moq = fields.Integer(related='last_rfq_id.moq', string="Original MOQ", readonly=True)
    orig_mpq = fields.Integer(related='last_rfq_id.mpq', string="Original MPQ", readonly=True)
    orig_cw = fields.Selection(related='last_rfq_id.cw', string="Original CW", readonly=True, selection='_selection_cw')
    orig_rw = fields.Selection(related='last_rfq_id.rw', string="Original RW", readonly=True, selection='_selection_rw')
    orig_tax = fields.Selection(related='last_rfq_id.tax', string='Original Tax', readonly=True)

    payment_term = fields.Char(string="Payment_term")
    incoterm = fields.Char(string="Incoterm")
    incoterm2 = fields.Char(string="Incoterm2")
    price_control = fields.Selection([('1', 'by PO date'), ('2', 'by delivery date')], string="Price control")
    active = fields.Boolean(string="Active", default=True)
    type = fields.Selection([('quote', 'Quote'),
                             ('rfq', 'RFQ'),
                             ('mass', 'Mass RFQ'),
                             ('history', 'Info record')], index=True, default='quote')
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                              default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)

    supplier_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    sap_approve_date = fields.Date('SAP approve date')

    flag = fields.Selection([('c', 'C'), ('n', 'N'), ('y', 'Y')], string='Flag')
    new_type = fields.Selection([
        ('old_ep', 'Old Ep'),
        ('as_upload', 'As Upload'),
        ('quote_create', 'Quote Create'),
        ('buyer_create', 'Buyer Create'),
        ('job_create', 'Idle Job Create'),
        ('change_term', 'Change Term Create')], string='RFQ Create Type', default="old_ep")
    country_code = fields.Char('Country Code')

    role_list = fields.Char('Workflow roles', compute='_take_role_list')

    group_id = fields.Many2one('iac.rfq.group', 'IAC Group')
    webflow_result = fields.Char(string='Webflow Result')
    sap_result = fields.Char(string='Sap Result')

    active = fields.Boolean('Active', default=True)
    no_down_reason_id = fields.Many2one('iac.rfq.reason', string="Reason Code")
    # drop fields.
    contract_pirce = fields.Monetary('Contract Price')

    modified_valid_date = fields.Boolean(string='Modified Valid Date', compute='_take_modified_valid_date')
    cost_down = fields.Boolean('Cost Down', compute='_take_cost_down')
    to_be_cost_down = fields.Boolean('Cost Down', compute='_take_cost_down')
    new_material = fields.Boolean(string='New material', compute='_take_new_material')
    usd_price = fields.Monetary('USD Price', compute='_take_usd_price')  # 转换到美金的价格
    orig_usd_price = fields.Float(string="Original USD Price", compute='_take_orig_usd_price',
                                  readonly=True)  # 历史的USD价格
    webflow_number = fields.Char(string="Webflow Number")
    # 废弃字段
    # THREE_MONTH_AMOUNT = fields.Float(string='Current Price',compute='_compute_history_fields')
    # part_id = fields.Many2one('material.master',string='Part No#',compute='_compute_fields',store=True)
    # THREE_MONTH_QTY = fields.Float(string='Current Price',compute='_compute_history_fields')
    # to_be_cost_down = fields.Boolean(string='To be cost down',compute='_compute_history_fields')
    # unit_price = fields.Float(string='Price per unit', compute='_compute_history_fields',store=True)

    # 数据迁移所使用的字段
    buyer_code_sap = fields.Char(string="Buyer Code", index=True)
    currency_name = fields.Char(string="Currency Name", index=True)
    division_code = fields.Char(string="Division Code", index=True)
    last_rfq_no = fields.Char(string="Last RFQ NO", index=True)
    plant_code = fields.Char(string="Plant Code", index=True)
    vendor_code = fields.Char(string="Vendor Code", index=True)
    purchase_org = fields.Char(string="Purchase Org")
    reason_code_text = fields.Char(string="Reason Code")
    supplier_company_no = fields.Char(string="Supplier Company No")

    # 为数据权限配置增加的字段
    source_code = fields.Char(string="Source Code", index=True)

    # 为数据迁移所准备的字段
    sap_key = fields.Char(string="SAP KEY", index=True)
    sap_log_id = fields.Char(string="SAP LOG ID")

    # 为供应商评鉴提供的数据
    last_price = fields.Float(string="Last Price")  # 最近一次的价格,state=sap_ok
    change_factor_price = fields.Selection([('up', 'Price Up'), ('down', 'Price Down'), ('equal', 'Price Equal')],
                                           string="Last Price is Cost Down", default="equal",
                                           index=True)  # 相比最近一次价格(state=sap_ok)是否降价
    ex_msg = fields.Text(string="Error Message")

    # 管理价格变动添加的字段_by_jiangjun
    cost_up_reason_id = fields.Many2one('iac.rfq.cost.up.reason', string=u'价格不同原因', index=True)
    cost_up_reason_web = fields.Char(string=u'涨价原因-web')
    customer_duty_web = fields.Char(string=u'客户是否吸收涨价')
    request_by_web = fields.Char(string=u'要求方')
    comment_web = fields.Char(string=u'涨价说明')
    approve_date_web = fields.Date(string=u'签核时间')
    effect_quantity_web = fields.Float(string=u'涨价后影响的数量', digits=(19, 5))
    new_vs_old_ids = fields.One2many('iac.rfq.new.vs.old', 'current_rfq_id', domain=[('new_flag', '=', 'Y')],
                                     string='New Vs Old RFQ')

    @api.one
    @api.depends('input_price')
    def _take_orig_usd_price(self):
        self.orig_usd_price = self.orig_price

    @api.one
    @api.depends('input_price')
    def _take_usd_price(self):
        if self.currency_id.exists() and self.currency_id.name == "USD":
            self.usd_price = self.input_price
        else:
            if not self.currency_id.exists():
                self.usd_price = 0
            else:
                currency_exchange = self.env["iac.currency.exchange"].get_usd_exchange_record(self.currency_id.id)
                if currency_exchange.exists():
                    self.usd_price = (
                                             self.input_price / currency_exchange.from_currency_amount) * currency_exchange.to_currency_amount
                else:
                    self.usd_price = 0

    @api.one
    @api.depends('valid_from')
    def _take_modified_valid_date(self):
        if self.last_rfq_id.exists():
            if self.valid_from == self.orig_valid_from and self.valid_to == self.orig_valid_to:
                self.modified_valid_date = True
            else:
                self.modified_valid_date = False
        else:
            self.modified_valid_date = False

    @api.one
    @api.depends('input_price')
    def _take_cost_down(self):
        """
        参考最近有效的RFQ比较价格,判断是否降价
        :return:
        """

        if self.last_rfq_id.exists():
            if self.input_price < self.orig_input_price:
                self.cost_down = True
            else:
                self.cost_down = False
        else:
            self.cost_down = False

    @api.one
    @api.depends('vendor_id', 'part_id')
    def _take_new_material(self):
        """
        判断当前RFQ是否是新材料
        :return:
        """
        if not self.last_rfq_id.exists():
            self.new_material = True
        else:
            self.new_material = False

    @api.multi
    def _take_role_list(self):
        for r in self:
            self.env['iac.rfq.qh'].set_role_list(r)

    @api.model
    def _selection_cw(self):
        slist = []
        recs = self.env['iac.cw.rw'].search([('code_master_id', '=', 'Cancel window')])
        for item in recs:
            slist.append((item.description, item.description))
        return slist

    @api.model
    def _selection_rw(self):
        slist = []
        recs = self.env['iac.cw.rw'].search([('code_master_id', '=', 'Reschedule window')])
        for item in recs:
            slist.append((item.description, item.description))
        return slist

    @api.one
    def validate_record(self):
        if self.part_id.plant_id.id != self.vendor_id.plant.id:
            raise UserError('Material Vendor plant are not the same plant')
        # if self.buyer_code and self.part_id.buyer_erp_id != self.buyer_code.buyer_erp_id:
        #    raise UserError('Material buyer code and buyer_code are not the same')

        if self.moq < self.mpq:
            raise UserError("MOQ Must greater than MPQ")

        if self.valid_to or self.valid_from:
            delta = relativedelta(fields.Date.from_string(self.valid_to), fields.Date.from_string(self.valid_from))
            # if delta.years >= 2:
            #    raise ValidationError(_('Valid to date - Valid from date > 2 years!'))

            if delta.years >= 2 and delta.days >= 2:
                raise ValidationError(_('Valid to date - Valid from date > 2 years!'))
        # 价格必须大于0
        # if self.input_price<=0 :
        #    raise UserError(_('Price must greater than zero!'))
        # if self.mpq<=0:
        #    raise UserError(_('mpq must greater than zero!'))
        # if self.moq<=0:
        #    raise UserError(_('moq must greater than zero!'))
        # if self.mpq>self.moq:
        #    raise UserError(_('moq must greater than mpq!'))
        # if self.valid_from>self.valid_to:
        #    raise UserError(_('valid_to  must greater than valid_from!'))
        # if self.lt<=0:
        #    raise UserError(_('LTIME must greater than zero!'))

        if self.vendor_id.state != 'done':
            raise UserError(_('Vendor is not in done state! vendor code is %s' % (self.vendor_id.vendor_code,)))
        # orgin others 43 签合过程中不能重复创建
        last_rfq = self.search([('id', '!=', self.id), ('state', 'in', ['wf_ok', 'wf_fail', 'sap_fail']),
                                ('vendor_id', '=', self.vendor_id.id), ('part_id', '=', self.part_id.id)], limit=1)
        if last_rfq.exists() and self.type in ['rfq', 'mass']:
            raise ValidationError(_("another rfq:%s not complete" % last_rfq.name))

        # if self.currency_id:
        #    if self.currency_id.name not in ['RMB','TWD'] and self.tax != 'J0':
        #        raise ValidationError(_('Currency 選外幣,Tax 必须 J0 ！'))
        # if self.part_id.part_type!='ZROH':
        #     raise UserError('Part Type is not \'ZROH\'')

        if self.plant_id.plant_code in ['CP21', 'CP22'] and self.currency_id.name != 'RMB' and self.tax != 'J0':
            raise UserError(_('厂区为CP21或者CP22的并且币种不是人民币的情况下,tax 必须为 J0'))
        # if self.plant_id.plant_code in ['TP02'] and self.currency_id.name != 'TWD' and self.tax!='V0':
        #    raise UserError(_('厂区为TP02的并且币种不是台币的情况下,tax 必须为 V0'))

    @api.model
    def create(self, vals):

        # 默认生成RFQ 编码
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('iac.rfq') or 'New'

        # self._calcu_rfq_price(vals)
        # 更新价格信息
        result = super(IacRfq, self).create(vals)
        digits_count = result.currency_id.decimal_setting
        input_vals = {
            "input_price": result.input_price,
            "digits_count": digits_count
        }
        price_vals = calcu_rfq_price(input_vals)
        super(IacRfq, result).write(price_vals)

        # 当新入导入数据的情况下，补充last_rfq_id
        if not result.last_rfq_id.exists():
            domain = [('id', '<>', result.id)]
            domain += [('vendor_id', '=', result.vendor_id.id)]
            domain += [('part_id', '=', result.part_id.id)]
            domain += [('state', '=', 'sap_ok')]
            # domain+=[('new_type','<>','change_term')]  #2019/10/15 by PW注释掉，否则新增RFQ last RFQ ID抓不到change term修改的值
            domain += [('currency_id', '=', result.currency_id.id)]
            last_rfq_rec = self.env["iac.rfq"].search(domain, order='valid_from desc, id desc', limit=1)
            if last_rfq_rec.exists():
                super(IacRfq, result).write({"last_rfq_id": last_rfq_rec.id})

        # 如果上条rfq存在的情况下,计算是否涨价或者降价
        if result.last_rfq_id.exists():
            if result.last_rfq_id.input_price - result.input_price > 0.000001:
                change_factor_price = {
                    "last_price": result.last_rfq_id.input_price,
                    "change_factor_price": "down"
                }
                super(IacRfq, result).write(change_factor_price)
            elif result.input_price - result.last_rfq_id.input_price > 0.000001:
                change_factor_price = {
                    "last_price": result.last_rfq_id.input_price,
                    "change_factor_price": "up"
                }
                super(IacRfq, result).write(change_factor_price)
            else:
                change_factor_price = {
                    "last_price": result.last_rfq_id.input_price,
                    "change_factor_price": "equal"
                }
                super(IacRfq, result).write(change_factor_price)

        super(IacRfq, result).write({"division_id": result.part_id.division_id.id})
        if not result.buyer_code:
            super(IacRfq, self).write({"buyer_code": result.part_id.buyer_code_id.id})
            # r.buyer_code = r.part_id.buyer_code_id.id
        super(IacRfq, self).write({"source_code": result.part_id.sourcer})
        result.validate_record()
        return result

    @api.multi
    def write(self, vals):
        # self._calcu_rfq_price(vals)
        result = super(IacRfq, self).write(vals)

        for rfq in self:
            # 修改价格的情况下重新计算rfq_price
            if "input_price" in vals:
                # 更新价格信息
                digits_count = rfq.currency_id.decimal_setting
                input_vals = {
                    "input_price": vals.get("input_price", 0),
                    "digits_count": digits_count
                }
                price_vals = calcu_rfq_price(input_vals)
                super(IacRfq, rfq).write(price_vals)

            # 如果上条rfq存在的情况下,计算是否涨价或者降价
            if rfq.last_rfq_id.exists():
                if rfq.last_rfq_id.input_price - rfq.input_price > 0.000001:
                    change_factor_price = {
                        "last_price": rfq.last_rfq_id.input_price,
                        "change_factor_price": "down"
                    }
                    super(IacRfq, rfq).write(change_factor_price)
                elif rfq.input_price - rfq.last_rfq_id.input_price > 0.000001:
                    change_factor_price = {
                        "last_price": rfq.last_rfq_id.input_price,
                        "change_factor_price": "up"
                    }
                    super(IacRfq, rfq).write(change_factor_price)
                else:
                    change_factor_price = {
                        "last_price": rfq.last_rfq_id.input_price,
                        "change_factor_price": "equal"
                    }
                    super(IacRfq, rfq).write(change_factor_price)

            rfq.validate_record()
            super(IacRfq, rfq).write({"source_code": rfq.part_id.sourcer})
        return result

    def _calcu_rfq_price(self, vals):
        """
        在创建或者写入记录之前由记录集对象进行调用
        当修改input_price 或者修改 currency_id的时候
        需要重新计算rfq_price 和相应的price_unit
        根据当前记录对应的currency_id 获取货币能够支持的小数位
        input_priceX1000 得到的数字如果满足货币支持的小数位,那么这个乘积的结果就是 rfq_price,price_unit=1000
        如果 input_priceX1000 得到的数字不满足货币所支持小数位,那么尝试用10000
        如果1000 和 10000 都失败的情况下，抛出异常
        """
        # 获取当前货币的小数位
        if "input_price" not in vals:
            return
        digits_count = 0
        if "currency_id" in vals:
            currency = self.env["res.currency"].browse(vals["currency_id"])
            digits_count = currency.decimal_setting
        else:
            digits_count = self.currency_id.decimal_setting
        # 获取允许范围之外的小数部分
        input_price = vals["input_price"]
        try_price = input_price * 1000 * math.pow(10, digits_count)
        digits_part = float("%.2f" % (try_price)) - int("%.0d" % (try_price))
        price_unit = 0
        if (digits_part >= 0.01):
            # 1000的不满足,尝试10000
            try_price = input_price * 10000 * math.pow(10, digits_count)
            digits_part = float("%.2f" % (try_price)) - int("%.0d" % (try_price))
            if digits_part >= 0.01:
                # 抛出异常,小数位太多
                raise UserError(_("小数位数太多!不能超过6位!"))
            else:
                price_unit = 10000
                vals["price_unit"] = price_unit
        else:
            price_unit = 1000
            vals["price_unit"] = price_unit
        # 根据price_unit 进行价格转换
        rfq_price = input_price * price_unit
        vals["rfq_price"] = rfq_price

    @api.onchange('currency_id')
    def onchange_currency_id(self):
        """
        币别为RMB
            厂别为南京CP22,TAX默认为J0
        币别为TWD
            厂别为南京,TAX默认为空
        币别不等于RMB或者TWD
            厂别为南京,TAX默认为J0
        其他币别默认为空

        a.廠別為浦東默認:J0 (都可以修改) CP21
        b.廠別為南京幣別:RMB 默認J1,台幣默認:空,其他幣別默認: CP22
            J0 (都可以修改)
        c.其他廠區統一默認為空白,讓用戶選擇 .

        """
        currency = self.currency_id.name
        if self.plant_id.exists() and self.plant_id.plant_code == 'CP22':
            if currency == 'RMB':
                self.tax = 'J2'
            elif currency == 'TWD':
                self.tax = False
            else:
                self.tax = 'J0'
        elif self.plant_id.exists() and self.plant_id.plant_code == 'CP21':
            pass
        else:
            self.tax = False

    @api.multi
    def send_to_email(self, partner_id=None, template_name=None):
        template = self.env.ref(template_name)
        return template.send_mail(partner_id, force_send=True)

    @api.multi
    def action_no_price_down(self):
        # CM:oscg_vendor.IAC_CM_groups -N  BUY:oscg_vendor.IAC_buyer_groups -NY
        cmg = self.env.ref('oscg_vendor.IAC_CM_groups')
        buyg = self.env.ref('oscg_vendor.IAC_buyer_groups')
        user_id = self.env.user.id
        if user_id not in cmg.users.ids or user_id not in buyg.users.ids:
            raise UserError(_('You are not CM or Buyer'))
        self.filtered(lambda x: x.flag == 'n').write({'state': 'done'})
        ry = self.filtered(lambda x: x.flag == 'y')
        if ry:
            if user_id not in buyg.users.ids:
                raise UserError(_('You are not Buyer!'))
            ry.write({'state': 'rfq', 'type': 'rfq'})

    # 废弃无用的代码
    # @api.multi
    # def action_webflow(self):
    #    for r in self:
    #        if not (r.rfq_price and r.moq and r.mpq and r.rw and r.cw and r.tax and r.lt):
    #            raise UserError(_('Price and trade factors are required.'))
    #        if r.new_material:
    #            result = self.webflow_api('new')
    #            if result:
    #                self.sap_api('new_rfq')
    #            else:
    #                raise UserError(_('erro to do'))
    #        else:
    #            # modify price
    #            result = self.webflow_api('modify')
    #            if result:
    #                self.sap_api('new_rfq')
    #            else:
    #                raise UserError(_('erro to do'))

    @api.onchange('vendor_id', 'part_id', 'currency_id')
    def onchange_vendor_id_part_id(self):
        if not self.vendor_id.exists():
            return
        if self.part_id.exists():
            self.buyer_code = self.part_id.buyer_code_id
            self.division_id = self.part_id.division_id

        if not self.vendor_id or not self.part_id or not self.currency_id:
            return

        currency = self.currency_id.name
        if self.plant_id.exists() and self.plant_id.plant_code == 'CP22':
            if currency == 'RMB':
                self.tax = 'J2'
            elif currency == 'TWD':
                self.tax = False
            else:
                self.tax = 'J0'
        elif self.plant_id.exists() and self.plant_id.plant_code == 'CP21':
            pass
        else:
            self.tax = False

        domain = [('part_id', '=', self.part_id.id), ('vendor_id', '=', self.vendor_id.id), ('state', '=', 'sap_ok')]
        domain += [('currency_id', '=', self.currency_id.id)]
        rec = self.search(domain, limit=1, order='create_date desc')
        if rec:
            self.last_rfq_id = rec.id
            self.rfq_price = rec.rfq_price
            self.input_price = rec.input_price
            self.lt = rec.lt
            self.moq = rec.moq
            self.mpq = rec.mpq
            self.cw = rec.cw
            self.rw = rec.rw
            self.tax = rec.tax
            self.valid_from = rec.valid_from
            self.valid_to = rec.valid_to
            self.currency_id = rec.currency_id
            self.price_control = rec.price_control
            self.vendor_part_no = rec.vendor_part_no

        if not rec.exists():
            self.last_rfq_id = False
            self.rfq_price = 0
            self.input_price = 0
            self.lt = 0
            self.moq = 0
            self.mpq = 0
            self.cw = False
            self.rw = False
            # self.tax = False
            # self.valid_from = False
            # self.valid_to = False
            # self.currency_id = False
            # self.price_control = False
            # self.vendor_part_no = False

    @api.multi
    def sap_api(self):
        for r in self:
            vals = {
                "id": r.id,
                "biz_object_id": r.id,
            }
            try:
                rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
                    'iac.interface.rpc'].invoke_web_call_with_log(
                    'ODOO_RFQ_001', vals)
                if rpc_result:
                    r.state = 'sap_ok'
                    val = {}
                    val['rfq_id'] = r.id
                    val['create_by'] = self._uid
                    val['create_timestamp'] = datetime.datetime.now()
                    val['action_type'] = 'sap ok'
                    self.env['iac.rfq.quote.history'].create(val)
                    # r.message_post(body=u'•SAP API ODOO_RFQ_001: %s' % rpc_json_data['Message']['Message'])
                else:
                    r.write({'state': 'sap_fail'})
                    val = {}
                    val['rfq_id'] = r.id
                    val['create_by'] = self._uid
                    val['create_timestamp'] = datetime.datetime.now()
                    val['action_type'] = 'sap fail'
                    self.env['iac.rfq.quote.history'].create(val)
                    # r.message_post(body=u'•SAP API ODOO_RFQ_001: %s' % rpc_json_data['Message']['Message'])
            except Exception as e:
                traceback.print_exc()
                # r.message_post(body=u'•SAP API Except: %s'%str(e))
        return True

    def sap_odoo_rfq_001(self):
        """
        只能被单个RFQ记录对象调用
        :return:
        """
        vals = {
            "id": self.id,
            "biz_object_id": self.id,
        }
        rpc_result, rpc_json_data, log_line_id, exception_log = self.env['iac.interface.rpc'].invoke_web_call_with_log(
            'ODOO_RFQ_001', vals)
        if rpc_result:
            self.write({'state': 'sap_ok'})
            val = {}
            val['rfq_id'] = self.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'sap ok'
            self.env['iac.rfq.quote.history'].create(val)
        else:
            self.write({'state': 'sap_fail'})
            val = {}
            val['rfq_id'] = self.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'sap fail'
            self.env['iac.rfq.quote.history'].create(val)
        return rpc_result, rpc_json_data, log_line_id, exception_log

    @api.multi
    def grouping(self):
        groups = list(set([r.role_list for r in self]))
        iac_groups = []
        for g in groups:
            iac_group = self.env['iac.rfq.group'].create({'role_list': g})
            for r in self:
                if r.role_list == iac_group.role_list:
                    r.write({'group_id': iac_group.id})  # 'state':'pending',
                    self -= r
            iac_groups += [iac_group.id]
        return iac_groups

    @api.multi
    def group_and_webflow(self):
        # 检验料号状态是否为01或02
        str = ''
        for status in self:
            if status.part_id.part_status in ('04', '10', '12'):
                str += 'rfq no:' + status.name + '里料号:' + status.part_id.part_no + '状态为：' + status.part_id.part_status + '(' + status.part_id.part_status_id.description + ')' + ','
        if len(str) != 0:
            raise UserError(str + '请联系相关人员到PLM系统开单修改料号状态!')

        if self.filtered(lambda x: x.state not in ['rfq']):
            raise UserError(_('State must be RFQ!'))
        iac_groups = self.grouping()
        # 预设处理中的状态,避免重复提交webflow
        self.write({"state": "wf_ok"})
        self.env.cr.commit()
        # print iac_groups

        if iac_groups:
            self.env['iac.rfq.group'].browse(iac_groups).action_webflow()

        for item in self:
            val = {}
            # print rfq_line.id
            val['rfq_id'] = item.id
            val['create_by'] = self._uid
            val['create_timestamp'] = datetime.datetime.now()
            val['action_type'] = 'MM send to Webflow'
            self.env['iac.rfq.quote.history'].create(val)
        return True

    @api.onchange('plant_id')
    def onchange_plant_id(self):
        """
        a.廠別為浦東默認:J0 (都可以修改)
        b.廠別為南京幣別:RMB 默認J1,台幣默認:空,
            其他幣別默認:J0 (都可以修改)
        c.其他廠區統一默認為空白,讓用戶選擇 .
        """
        if self.plant_id.plant_code == 'CP21':
            self.tax = 'J0'
        elif self.plant_id.plant_code == 'CP22':
            if self.currency_id.exists():
                currency = self.currency_id.name
                if currency == 'RMB':
                    self.tax = 'J2'
                elif currency == 'TWD':
                    self.tax = False
                else:
                    self.tax = 'J0'
            else:
                self.tax = False
        else:
            self.tax = False


class IacRfqGroup(models.Model):
    """
    Make a group contains a list of RFQ lines base on User Roles
    """
    _name = 'iac.rfq.group'
    _description = 'RFQ Group'
    _rec_name = 'role_list'
    _order = 'id desc'

    role_list = fields.Char(string="Role List")
    approve_result = fields.Selection([('Y', 'Yes'), ('N', 'No')], string="Approve Result", default="N")
    approve_start = fields.Datetime(string="Approve Start Time")
    approve_end = fields.Datetime(string="Approve End Time")
    note = fields.Text('Memo')
    rfq_ids = fields.One2many('iac.rfq', 'group_id', 'RFQ Lines')
    state = fields.Selection([('pending', 'Pending'), ('sent', 'Sent'), ('done', 'Done'), ('rpc_failed', 'RPC Failed'),
                              ('app_failed', 'Approve Failed')], string='status', default='pending')

    active = fields.Boolean('Active', default=True)

    @api.multi
    def disactive(self):
        self.write({'active': False})

    @api.multi
    def action_webflow(self):
        for rfq_group_id in self.ids:
            rfq_group_rec = self.env["iac.rfq.group"].browse(rfq_group_id)
            role_list = eval(rfq_group_rec.role_list)
            for x in role_list:
                if x.split(':')[0] == 'division':
                    role_list.remove(x)
            vals = {
                "id": rfq_group_rec.id,
                "biz_object_id": rfq_group_rec.id,
                'flow_id': role_list
            }
            rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
                'iac.interface.rpc'].invoke_web_call_with_log('F06_B', vals)
            if rpc_result:
                rfq_group_rec.write({'state': 'sent', 'approve_start': fields.Datetime.now()})
                vals = {
                    'state': 'wf_ok',
                    'webflow_result': 'ok',
                    'webflow_number': rpc_json_data.get('EFormNO'),
                }
                rfq_group_rec.rfq_ids.write(vals)  # pending
                self.env.cr.commit()
            else:
                rfq_group_rec.write(
                    {'state': 'rpc_failed', 'approve_start': fields.Datetime.now(), 'note': rpc_json_data})
                # 送签失败的情况下,记录送签失败错误信息
                rfq_group_rec.rfq_ids.write(
                    {'state': 'wf_fail', 'webflow_result': 'fail', 'text': rpc_json_data.get('message', False), })
                for item in rfq_group_rec.rfq_ids:
                    # print item.id
                    val = {}
                    # print rfq_line.id
                    val['rfq_id'] = item.id
                    val['create_by'] = self._uid
                    val['create_timestamp'] = datetime.datetime.now()
                    val['action_type'] = 'webflow fail'
                    self.env['iac.rfq.quote.history'].create(val)
                self.env.cr.commit()
        return True

    @api.model
    def rfq_approve_callback(self, context=None):
        """
        回调函数说明
        """
        approve_status = context.get('approve_status')
        if approve_status:
            g = self.browse(int(context.get('data').get('id')))
            if not g.exists():
                ex_msg = "id is %s not exists in iac.rfq.group" % (context.get('data').get('id'),)
                return False, [ex_msg]
            rfq_ids = context['rpc_callback_data']['params']['rfq_ids']
            # 需要call sap的 rfq_id列表
            sap_rfq_ids = []
            for rfq in rfq_ids:
                # print rfq
                r = self.env['iac.rfq'].browse(int(rfq['id']))
                if not r.exists():
                    return False, ['rfq id:%s is not exsit' % rfq['id']]
                if rfq['PASS'] == 'Y':
                    sap_rfq_ids.append(int(rfq['id']))
                    r.write({'state': 'wf_approved',
                             'cost_up_reason_web': rfq['CostUpCauseID'],
                             'customer_duty_web': rfq['CostUpAbsorptionLoss'],
                             'effect_quantity_web': rfq['CostUpEffectQty'],
                             'request_by_web': rfq['CostUpRequest'],
                             'comment_web': rfq['CostUpMemo'],
                             'approve_date_web': datetime.datetime.now().strftime("%Y-%m-%d")
                             })
                    val = {}
                    # print rfq_line.id
                    val['rfq_id'] = int(rfq['id'])
                    val['create_by'] = self._uid
                    val['create_timestamp'] = datetime.datetime.now()
                    val['action_type'] = 'webflow approved'
                    self.env['iac.rfq.quote.history'].create(val)
                    # 使用单独线程处理call SAP操作
                    # try:
                    #    r.sap_api()
                    # except:
                    #    pass
                else:
                    if rfq['PASS'] in ['D', 'N']:
                        r.state = 'wf_unapproved'
                        val = {}
                        # print rfq_line.id
                        val['rfq_id'] = int(rfq['id'])
                        val['create_by'] = self._uid
                        val['create_timestamp'] = datetime.datetime.now()
                        val['action_type'] = 'webflow unapproved'
                        self.env['iac.rfq.quote.history'].create(val)
                    else:
                        r.write({'state': 'wf_fail'})
                        val = {}
                        # print rfq_line.id
                        val['rfq_id'] = int(rfq['id'])
                        val['create_by'] = self._uid
                        val['create_timestamp'] = datetime.datetime.now()
                        val['action_type'] = 'webflow fail'
                        self.env['iac.rfq.quote.history'].create(val)
            g.state = 'done'
            # 循环完成另外开立一个线程进行call sap 处理
            sap_rfq_vals = {
                "sap_rfq_ids": sap_rfq_ids,
            }
            rfq_call_sap_thread = threading.Thread(target=self.rfq_approve_call_sap, kwargs=sap_rfq_vals)
            rfq_call_sap_thread.start()
        else:
            return False, []
        return True, []

    @odoo_env
    def rfq_approve_call_sap(self, **kwargs):
        """
        单独开一个线程去处理rfq 签核完成后调用sap
        :param kwargs:
        :return:
        """
        sap_rfq_ids = kwargs.get("sap_rfq_ids")
        for rfq_id in sap_rfq_ids:
            try:
                rfq_rec = self.env['iac.rfq'].browse(rfq_id)
                if rfq_rec:
                    rfq_rec.sap_odoo_rfq_001()
                    self.env.cr.commit()
            except:
                traceback.print_exc()
                ex_msg = traceback.format_exc()
                self.env.cr.rollback()
                if rfq_rec:
                    vals = {
                        "ex_msg": ex_msg,
                        "state": "sap_fail"
                    }
                    rfq_rec.write(vals)
                    self.env.cr.commit()


class IacRfqQh(models.Model):
    _name = 'iac.rfq.qh'

    name = fields.Char(string='Name')
    key = fields.Text(string='Expression')
    value = fields.Text(string='Web Flow Groups')
    note = fields.Text(string='Note')
    active = fields.Boolean('Active', default=True)

    @api.model
    def create(self, vals):
        try:
            approve_role_json = json.loads(vals.get("value"))
            if not (type(approve_role_json) is types.ListType):
                memo = _(u'解析规则报错,签核的关卡不是合法的JSON中的list格式')
                raise UserError(memo)
        except:
            traceback.print_exc()
            memo = _(u'解析规则报错,签核的关卡不是合法的JSON中的list格式')
            raise UserError(memo)

        return super(IacRfqQh, vals)

    @api.multi
    def write(self, vals):
        if "value" in vals:
            try:
                approve_role_json = json.loads(vals.get("value"))
                if not (type(approve_role_json) is types.ListType):
                    memo = _(u'解析规则报错,签核的关卡不是合法的JSON中的list格式')
                    raise UserError(memo)
                return super(IacRfqQh, self)
            except:
                traceback.print_exc()
                memo = _(u'解析规则报错,签核的关卡不是合法的JSON中的list格式')
                raise UserError(memo)
        else:
            return super(IacRfqQh, self).write(vals)

    @api.model
    def set_role_list(self, r):
        role_list = []
        expressions = self.env['iac.rfq.qh'].search([])
        try:
            for exp in expressions:
                if eval(exp.key):
                    role_list += eval(exp.value)
            # division group
            if r.division_id:
                role_list += ['division:' + r.division_id.division]
            r.role_list = str(sorted(list(set(role_list))))
        except Exception as e:
            raise UserError(_(str(e)))
        return True


class IacJobLog(models.Model):
    _name = 'iac.job.log'

    name = fields.Char('Name')
    state = fields.Selection([('1', 'Start'), ('2', 'End'), ('3', 'Exception')])


class IacRfqReason(models.Model):
    _name = 'iac.rfq.reason'

    name = fields.Char('Reason')


if __name__ == '__main__':
    print 'begin'
