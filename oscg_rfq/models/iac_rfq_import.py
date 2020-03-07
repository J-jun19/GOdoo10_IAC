# -*- coding: utf-8 -*-

import json
import xlwt
import time,base64
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

_logger = logging.getLogger(__name__)


class IacRfqImport(models.Model):
    """rfq的上传数据,首先上传到当前模型，验证无误的情况下，到正式模型中创建
    """
    _name = 'iac.rfq.import'

    note = fields.Text('Memo')
    # vendor input
    input_price = fields.Float(string="Price",digits=(18,6))
    rfq_price = fields.Float(string="Price") #readonly=True, states={'draft': [('readonly', False)]}
    valid_from = fields.Date('Valid From')
    valid_to = fields.Date('Valid To')
    moq = fields.Float(string="MOQ")
    mpq = fields.Float(string="MPQ")
    lt = fields.Integer(string="LTIME")
    cw = fields.Selection(string="CW",selection='_selection_cw')
    rw = fields.Selection(string="RW",selection='_selection_rw')
    document_base = fields.Selection([('po','PO base'),('delivery','Delivery Base')],string='Document base')
    # six factor: moq/mpq/lt/cw/rw/tax
    tax = fields.Selection([
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
                               ],string="Tax")

    price_unit = fields.Float('Price unit')
    vendor_id = fields.Many2one('iac.vendor', string='Vendor',domain=[('state','=','done'),('vendor_type','in',['normal','spot'])])
    part_id = fields.Many2one('material.master.asn',string='Part No#',compute='_compute_fields',store=True)
    part_code = fields.Char('Part NO.',required=True)
    plant_id = fields.Many2one('pur.org.data',string='Plant Code')
    division_id = fields.Many2one('division.code',string='Divsion',compute='_compute_fields',store=True)
    buyer_code = fields.Many2one('buyer.code',string='BuyerCode',compute='_compute_fields',store=True)
    purchase_org_id = fields.Many2one('vendor.plant','Purchase Orgnization')
    text = fields.Text('Text')
    currency_id = fields.Many2one('res.currency', string='Currency')
    state = fields.Selection([
                                 ('cm_uploaded', 'CM Uploaded'), #quote
                                 ('as_uploaded', 'AS Uploaded'),
                                 ('mm_updated', 'MM Updated'),
                                 ('mm_update_fail', 'MM Update Fail'),
                                 ('cancel', 'Cancel'),
                                 ('done', 'Done'),
                                 ('reason', 'Reason')
                                 ], string='Status', default='as_uploaded',)
    sap_price = fields.Monetary('Current SAP Price')
    cost_up = fields.Boolean(string="Cost Up")
    low_by_all_site = fields.Boolean(string="Low Price By All Site")
    disapproval_comm = fields.Text(string="Disapproval Comments")
    reason_code = fields.Text(string="Reason Code")
    manufacturer_part_no = fields.Char('Manufacturer Part No')
    release_flag = fields.Char('Release Flag')
    buyer_erp_id = fields.Many2one('res.partner','Buyer ERP ID')
    uom = fields.Integer('Uom')
    line_text = fields.Char(string="Line text")
    vendor_part_no = fields.Char('Vendor Part No')
    order_reason = fields.Char(string="order_reason")


    payment_term = fields.Char(string="Payment_term")
    incoterm = fields.Char(string="Incoterm")
    incoterm2 = fields.Char(string="Incoterm2")
    price_control = fields.Selection([('1','by PO date'),('2','by delivery date')],string="Price control")
    active = fields.Boolean(string="Active",default=True)

    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.user.company_id.id)

    supplier_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
    sap_approve_date = fields.Date('SAP approve date')
    flag = fields.Selection([('c','C'),('n','N'),('y','Y')],string='Flag')
    new_type = fields.Selection([
                                    ('old_ep','Old Ep'),
                                    ('as_upload','As Upload'),
                                    ('quote_create','Quote Create'),
                                    ('buyer_create','Buyer Create'),
                                    ('job_create','Idle Job Create'),
                                    ('change_term','Change Term Create')],string='RFQ Create Type',default="old_ep")
    country_code = fields.Char('Country Code')


    active = fields.Boolean('Active',default=True)
    no_down_reason_id = fields.Many2one('iac.rfq.reason',string="Reason Code")
    # drop fields.
    contract_pirce = fields.Monetary('Contract Price')
    #文件id
    as_file_id=fields.Many2one('ir.attachment',string="AS Uploaded File Id")
    mm_file_id=fields.Many2one('ir.attachment',string="MM Uploaded File Id")
    cm_file_id=fields.Many2one('ir.attachment',string="CM Uploaded File Id")
    file_line_no=fields.Integer(string="File Line No")
    as_upload_id=fields.Many2one("iac.rfq.import","AS Upload Data Info")
    as_upload_id_value=fields.Integer("AS Upload ID Value")
    #为数据权限配置增加的字段
    source_code=fields.Char(string="Source Code",index=True,compute='_compute_fields',store=True)
    rfq_id=fields.Many2one('iac.rfq',string="RFQ Info")
    import_source=fields.Selection([
                                    ('as_import','AS Import'),
                                    ('mm_import','MM Import'),
                                    ('cm_import','Cm Import'),
                                    ],string='RFQ Import Type')

    # 为填写涨价原因添加的字段
    costup_reason_id = fields.Many2one('iac.rfq.cost.up.reason',string='Costup Reason',index=True)
    import_new_vs_old_ids = fields.One2many('iac.rfq.new.vs.old', 'import_rfq_id', domain=[('new_flag','=','Y')], string='New Vs Old RFQ Import')


    @api.one
    def validate_record(self):
        if self.part_code==False:
            raise UserError('Material can not be null!')
        if not self.vendor_id.exists():
            raise UserError('Vendor can not be null!')

        if not self.currency_id.exists():
            raise UserError('Currency can not be null!')

        if  self.price_control==False:
            raise UserError('Price Control can not be null!')

        if  self.input_price<=0:
            raise UserError('Price must greater than tero!')

        if  self.valid_from==False:
            raise UserError('valid_from can not be null!')

        if  self.valid_to==False:
            raise UserError('valid_to can not be null!')

        if  self.valid_to<self.valid_from:
            raise UserError('valid_to must greater than valid_from !')

        #if not self.part_id.exists():
        #    raise UserError('Material is not valid ,please check source_code or division or buyer')

        if self.part_id.exists() and self.part_id.plant_id.id != self.vendor_id.plant.id:
            raise UserError('Material Vendor plant are not the same plant')

        # if self.part_id.exists() and self.part_id.part_type!='ZROH':
        #     raise UserError('Part Type is not \'ZROH\'')
    @api.model
    def _selection_cw(self):
        slist = []
        recs = self.env['iac.cw.rw'].search([('code_master_id','=','Cancel window')])
        for item in recs:
            slist.append((item.description, item.description))
        return slist

    @api.model
    def _selection_rw(self):
        slist = []
        recs = self.env['iac.cw.rw'].search([('code_master_id','=','Reschedule window')])
        for item in recs:
            slist.append((item.description, item.description))
        return slist

    @api.multi
    @api.depends('part_code', 'plant_id')
    def _compute_fields(self):
        for r in self:
            part = self.env['material.master.asn'].search(
                [('plant_id', '=', r.plant_id and r.plant_id.id or False), ('part_no', '=', r.part_code)])
            if not part.exists():
                raise UserError('Part Code is not valid %s'%(r.part_code,))
            r.part_id = part and part[0].id or False
            r.source_code=part.sourcer
            r.buyer_code=part.buyer_code_id
            r.division_id=part.division_id

    @api.model
    def create(self,vals):
        result=super(IacRfqImport,self).create(vals)
        result.validate_record()
        return result

    @api.multi
    def write(self,vals):
        result=super(IacRfqImport,self).write(vals)
        self.validate_record()
        return result
