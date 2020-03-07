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


class IacRfqChangeTerm(models.Model):
    """rfq修改交易条件的模型
    """
    _name = 'iac.rfq.change.term'
    _inherit='iac.rfq'
    _table="iac_rfq"

    @api.multi
    def action_send(self):
        # for r in self:
        #     r.send_to_email(r.vendor_id.user_id.partner_id.id)
        self.write({'state': 'rfq','type':'rfq'})



    @api.multi
    def action_cancel(self):
        if self.filtered(lambda x:x.state not in ['draft','replay']):
            raise UserError(_('State must be draft or replay!'))
        self.write({'state': 'cancel','active': False})

    @api.multi
    def action_restate_rfq(self):
        self.filtered(lambda x:x.state in ['wf_fail','sap_fail']).write({'state': 'rfq'})



    @api.model
    def create(self, vals):
        if not vals.get("last_rfq_id",False):
            raise UserError("No RFQ Found !")
        last_rfq_rec=self.env["iac.rfq"].browse(vals["last_rfq_id"])
        #vals["buyer_code"]=last_rfq_rec.buyer_code.id
        #vals["division_id"]=last_rfq_rec.division_id.id
        vals["input_price"]=last_rfq_rec.input_price
        vals["valid_from"]=last_rfq_rec.valid_from
        vals["valid_to"]=last_rfq_rec.valid_to
        vals["currency_id"]=last_rfq_rec.currency_id.id
        vals["price_control"]=last_rfq_rec.price_control
        vals["new_type"]="change_term"
        vals["type"]="rfq"
        vals["state"]="rfq"
        result = super(IacRfqChangeTerm,self).create(vals)
        val = {}
        # print rfq_line.id
        val['rfq_id'] = result.id
        val['create_by'] = self._uid
        val['create_timestamp'] = datetime.datetime.now()
        val['action_type'] = 'MM submit terms change'
        self.env['iac.rfq.quote.history'].create(val)
        result.validate_record()
        return result

    @api.one
    def validate_record(self):
        if self.lt<=0:
            raise UserError('LTime must greater than zero')
        if self.moq<=0:
            raise UserError('MOQ must greater than zero')
        if self.mpq<=0:
            raise UserError('MPQ must greater than zero')
        if self.input_price<=0 :
            raise UserError(_('Price must greater than zero!'))
        if self.mpq>self.moq:
            raise UserError(_('moq must greater than mpq!'))

        #禁止录入重复数据
        if self.last_rfq_id.exists():
            if self.lt==self.last_rfq_id.lt \
                    and self.moq==self.last_rfq_id.moq\
                    and self.mpq==self.last_rfq_id.mpq\
                    and self.cw==self.last_rfq_id.cw \
                    and self.rw==self.last_rfq_id.rw \
                    and self.valid_from==self.last_rfq_id.valid_from \
                    and self.valid_to==self.last_rfq_id.valid_to \
                    and self.tax==self.last_rfq_id.tax \
                    and self.input_price==self.last_rfq_id.input_price\
                    and self.price_control==self.last_rfq_id.price_control:
                raise UserError(u"存在所有交易条件都相同的RFQ,RFQ 编码为%s"%(self.last_rfq_id.name))
    @api.onchange('vendor_id', 'part_id','currency_id')
    def onchange_vendor_id_part_id(self):
        if not self.vendor_id.exists():
            return
        if self.part_id.exists():
            self.buyer_code=self.part_id.buyer_code_id
            self.division_id=self.part_id.division_id

        if not self.vendor_id or not self.part_id or not self.currency_id:
            return

        currency = self.currency_id.name
        if self.plant_id.exists()  and  self.plant_id.plant_code=='CP22':
            if currency=='RMB':
                self.tax='J2'
            elif currency=='TWD' :
                self.tax=False
            else:
                self.tax='J0'
        elif self.plant_id.exists()  and  self.plant_id.plant_code=='CP21':
            pass
        else:
            self.tax=False

        domain=[('part_id', '=', self.part_id.id), ('vendor_id', '=', self.vendor_id.id),('state','=','sap_ok')]
        domain+=[('currency_id', '=', self.currency_id.id)]
        rec = self.search(domain,limit=1,order='create_date desc')
        if rec:
            self.last_rfq_id = rec.id
            self.rfq_price = rec.rfq_price
            self.input_price=rec.input_price
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
            self.reason_code=rec.reason_code

        if not rec.exists():
            self.last_rfq_id =False
            self.rfq_price = 0
            self.input_price=0
            self.lt = 0
            self.moq = 0
            self.mpq = 0
            self.cw = False
            self.rw = False
            self.tax = False
            self.valid_from = False
            self.valid_to = False
            self.currency_id = False
            self.price_control = False
            self.vendor_part_no = False