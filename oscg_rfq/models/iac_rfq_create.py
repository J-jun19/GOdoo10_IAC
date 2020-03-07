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
import utility

_logger = logging.getLogger(__name__)


class IacRfqCreate(models.Model):
    """rfq单笔创建的模型
    """
    _name = 'iac.rfq.create'
    _inherit='iac.rfq'
    _table="iac_rfq"


    @api.multi
    def action_quotation_send(self):
        # for r in self:
        #     r.send_to_email(r.vendor_id.user_id.partner_id.id)
        return self.write({'state':'sent'})

    @api.multi
    def buttonSubmit(self):



        if self.division_id.division:
            self._cr.execute(
                """ select division, * from iac_tmjkburelation where validflag = 'Y' and division = %s """,
                (self.division_id.division,))
            search_result = self._cr.fetchall()
            # 檢查 Division 是否有效
            if search_result:
                # 檢查該 Division 與 Plant 是否匹配
                self._cr.execute(""" select * from iac_bg_division_info where plant = %s and division = %s """,
                                 (self.part_id.plant_code, self.division_id.division))
                search_plant_division = self._cr.fetchall()
                if search_plant_division:
                    # 檢查 Plant + Division 是否有設定簽核人員,關卡 = CM
                    self._cr.execute(
                        """ select * from iac_tgroupuserinfo  where plant = %s and divisioncode = %s and levelname = 'CM' """,
                        (self.part_id.plant_code, self.division_id.division))
                    search_cm = self._cr.fetchall()
                    if not search_cm:
                        self._cr.execute(
                            """ select * from iac_tgroupuserinfo  where plant = %s and divisionname = 'ALL' and levelname = 'CM' """,
                            (self.part_id.plant_code,))
                        search_cm_all = self._cr.fetchall()
                        if not search_cm_all:
                            raise UserError(
                                u'料號對應的division %s 在webflow中沒有設定簽核關係，請確認料號與division的關係是否正確，如果關係不正確請修改對應關係;如果要新增簽核關係請聯繫8585設定' % (
                                    self.division_id.division))
                else:
                    raise UserError(u'division %s 不屬於 plant %s， 請與IT PM確認' % (
                        self.division_id.division, self.part_id.plant_code))

            else:
                raise UserError(u'料號對應的Division %s不可用，請修改料號對應的divsion后重新上傳' % (self.division_id.division))
        else:
            raise UserError(u'请选择Division')
        self.write({'state': 'rfq'})
        action=self.env.ref("oscg_rfq.action_iac_rfq_create")
        action_window={
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode': 'tree',
            'res_model': action.res_model,
            'domain': eval(action.domain),
            'view_id':self.env.ref('oscg_rfq.view_iac_rfq_create_list').id,
            }
        return action_window

    @api.multi
    def action_cancel(self):
        if self.filtered(lambda x:x.state not in ['draft','replay']):
            raise UserError(_('State must be draft or replay!'))
        self.write({'state': 'cancel','active': False})

    @api.multi
    def action_restate_rfq(self):
        self.filtered(lambda x:x.state in ['wf_fail','sap_fail']).write({'state': 'rfq'})

    @api.multi
    def action_replay_as_confirm(self):
        if self.filtered(lambda x:x.state != 'replay'):
            raise UserError(_('State must be replay'))
        self.write({'state': 'rfq','type':'rfq'})

    @api.model
    def create(self, vals):
        # utility.aaa(self,b)
        # 检验料号状态是否为01或02
        material_status_id = self.env['material.master'].search([('id', '=', vals.get('part_id'))])
        if material_status_id.part_status in ('04', '10', '12'):
            raise UserError(u'料号 %s 的状态为 %s(%s)，请联系相关人员到PLM系统开单修改料号状态!' %
                            (material_status_id.part_no, material_status_id.part_status, material_status_id.part_status_id.description))

        #判断是否有权限进行rfq 创建
        access_result,rule_id=self.env["iac.rfq.user.group"].check_rfq_create_access()
        if access_result==False:
            raise UserError('Access denied!You need Create Autherization')

        new_vals={
            "type":"rfq",
            "state":"draft",
            'new_type':"buyer_create",
        }
        vals.update(new_vals)
        result = super(IacRfqCreate,self).create(vals)

        # 调用utility中公用的方法产生对照资料
        utility.create_rfq_new_vs_old(self,result,'current_rfq_id',result.cost_up_reason_id)
        # 判断涨价原因是否合法
        utility.validate_costup_reason(self,result,'draft')

        val = {}
        # print rfq_line.id
        val['rfq_id'] = result.id
        val['create_by'] = self._uid
        val['create_timestamp'] = datetime.datetime.now()
        val['action_type'] = 'MM create RFQ singly'
        self.env['iac.rfq.quote.history'].create(val)
        result._uniq_check_rfq_create()
        return result

    # @api.multi
    # def unlink(self):
    #     result = super(IacRfqCreate,self).unlink()
    #     return result

    @api.one
    @api.constrains('vendor_id','part_id','lt','mpq','moq','cw','rw','currency_id','tax','reason_code','vendor_part_no')
    def _uniq_check_rfq_create(self):
        #如果有带出了上一条资料的情况下,不能修改交易条件,货币类型 ,vendor_part_no
        #if self.last_rfq_id.exists():
        #    if self.lt!=self.last_rfq_id.lt or self.moq!=self.last_rfq_id.moq or self.mpq!=self.last_rfq_id.mpq \
        #        or self.cw!=self.last_rfq_id.cw or self.rw!=self.last_rfq_id.rw \
        #        or self.currency_id.id !=self.last_rfq_id.currency_id.id or self.tax!=self.last_rfq_id.tax \
        #        or self.vendor_part_no!=self.last_rfq_id.vendor_part_no:
        #        err_msg=u"存在已经存在的RFQ的情况下，无法变更交易条件,RFQ 编码为 ( %s ) "%(self.last_rfq_id.name,)
        #        raise UserError(err_msg)
            #价格必须大于0
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
        if self.input_price<=0 :
            raise UserError(_('Price must greater than zero!'))
        if self.mpq<=0:
            raise UserError(_('mpq must greater than zero!'))
        if self.moq<=0:
            raise UserError(_('moq must greater than zero!'))
        if self.mpq>self.moq:
            raise UserError(_('moq must greater than mpq!'))
        if self.valid_from>self.valid_to:
            raise UserError(_('valid_to  must greater than valid_from!'))
        if self.lt<=0:
            raise UserError(_('LTIME must greater than zero!'))
        if self.plant_id.plant_code in ['CP21','CP22'] and self.currency_id.name != 'RMB' and self.tax!='J0':
            raise UserError(_('厂区为CP21或者CP22的并且币种不是人民币的情况下,tax 必须为 J0'))
        if self.plant_id.plant_code in ['TP02'] and self.currency_id.name != 'TWD' and self.tax!='V0':
            raise UserError(_('厂区为TP02的并且币种不是台币的情况下,tax 必须为 V0'))

    @api.onchange('vendor_id', 'part_id','currency_id')
    def onchange_vendor_id_part_id(self):
        if not self.vendor_id.exists():
            return
        if self.part_id.exists():
            self.buyer_code=self.part_id.buyer_code_id
            self.division_id=self.part_id.division_id
            print self.division_id.division, self.part_id.plant_code

            if self.division_id.division:
                self._cr.execute(
                    """ select division, * from iac_tmjkburelation where validflag = 'Y' and division = %s """,
                    (self.division_id.division,))
                search_result = self._cr.fetchall()
                # 檢查 Division 是否有效
                if search_result:
                    # 檢查該 Division 與 Plant 是否匹配
                    self._cr.execute(""" select * from iac_bg_division_info where plant = %s and division = %s """,
                                     (self.part_id.plant_code, self.division_id.division))
                    search_plant_division = self._cr.fetchall()
                    if search_plant_division:
                        # 檢查 Plant + Division 是否有設定簽核人員,關卡 = CM
                        self._cr.execute(
                            """ select * from iac_tgroupuserinfo  where plant = %s and divisioncode = %s and levelname = 'CM' """,
                            (self.part_id.plant_code, self.division_id.division))
                        search_cm = self._cr.fetchall()
                        if not search_cm:
                            raise UserError(
                                u'料號對應的division %s 在webflow中沒有設定簽核關係，請確認料號與division的關係是否正確，如果關係不正確請修改對應關係;如果要新增簽核關係請聯繫8585設定' % (
                                self.division_id.division))
                    else:
                        raise UserError(u'division %s 不屬於 plant %s， 請與IT PM確認' % (
                        self.division_id.division, self.part_id.plant_code))

                else:
                    raise UserError(u'料號對應的Division %s不可用，請修改料號對應的divsion后重新上傳' % (self.division_id.division))

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
        rec = self.search(domain,limit=1,order='valid_from desc, id desc')
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

        #if not rec.exists():
        #    self.last_rfq_id =False
        #    self.rfq_price = 0
        #    self.input_price=0
        #    self.lt = 0
        #    self.moq = 0
        #    self.mpq = 0
        #    self.cw = False
        #    self.rw = False
        #    self.tax = False
        #    self.valid_from = False
        #    self.valid_to = False
        #    self.currency_id = False
        #    self.price_control = False
        #    self.vendor_part_no = False

    @api.onchange('plant_id')
    def onchange_plant_id(self):
        """
        a.廠別為浦東默認:J0 (都可以修改)
        b.廠別為南京幣別:RMB 默認J1,台幣默認:空,
            其他幣別默認:J0 (都可以修改)
        c.其他廠區統一默認為空白,讓用戶選擇 .
        """
        if self.plant_id.plant_code=='CP21':
            self.tax='J0'
        elif self.plant_id.plant_code=='CP22':
            if self.currency_id.exists():
                currency = self.currency_id.name
                if currency=='RMB':
                    self.tax='J1'
                elif currency=='TWD':
                    self.tax=False
                else:
                    self.tax='J0'
            else:
                self.tax=False
        else:
            self.tax=False

