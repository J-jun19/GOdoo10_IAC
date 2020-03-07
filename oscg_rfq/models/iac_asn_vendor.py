# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from functools import wraps
import  traceback
import threading
from datetime import datetime,timedelta

class iacASNVendorChange(models.Model):
    _name = 'iac.asn.vendor.change'
    _inherit = "iac.asn"
    _table="iac_asn"
    _order='id desc'

    line_ids = fields.One2many('iac.asn.line.vendor.change','asn_id','ASN Line')

    @api.onchange('etd_date','delivery_days')
    @api.depends('etd_date','delivery_days')
    def on_change_etd_date(self):
        #cur_time=datetime.now()
        if self.etd_date!=False  and self.delivery_days!=False:
            dt_etd_date=datetime.now().strptime(self.etd_date,'%Y-%m-%d')
            to_time=dt_etd_date+timedelta(days=self.delivery_days)
            self.eta_date=to_time.date()


    @api.multi
    def push_to_sap(self):
        """
        提供action 菜单对需要同步的数据进行同步
        :return:
        """
        super(iacASNVendorChange,self).push_to_sap_asn_004()

    @api.multi
    def write(self,vals):
        """
        发生表头修改的时候,需要调用SAP接口同步数据
        :param vals:
        :return:
        """
        super(iacASNVendorChange,self).write(vals)
        if "no_send_sap" in self._context:
            pass
        else:
            self.push_to_sap_asn_004()
        return True

class iacASNLineVendorChange(models.Model):
    _name = 'iac.asn.line.vendor.change'
    _inherit = "iac.asn.line"
    _table="iac_asn_line"
    asn_id = fields.Many2one('iac.asn.vendor.change','ASN')


class iacASNVendorCancel(models.Model):
    _name = 'iac.asn.vendor.cancel'
    _inherit = "iac.asn"
    _table="iac_asn"
    line_ids = fields.One2many('iac.asn.line.vendor.cancel','asn_id','ASN Line')

    @api.multi
    def write(self,vals):

        # 轉資料的job正在執行,就不能執行程式20190419 ning add ___begin
        self._cr.execute("  select count(*) as job_count  from ep_temp_master.extractlog "
                         "  where extractname in ( select extractname from ep_temp_master.extractgroup "
                         "                                        where extractgroup = 'ASN' ) "
                         "      and extractstatus = 'ODOO_PROCESS'   ")
        for job in self.env.cr.dictfetchall():
            if job['job_count'] and job['job_count'] > 0:
                raise UserError(' 正在轉資料 ,請勿操作 ! ')
                # 轉資料的job正在執行,就不能執行程式20190419 ning add ___end
        result=super(iacASNVendorCancel,self).write(vals)
        vals = {
            'action_type': 'Vendor Cancel ASN',
            'vendor_id':self.vendor_id.id
        }
        self.env['iac.supplier.key.action.log'].create(vals)
        self.env.cr.commit()
        #对发生数量变更的asn记录才调用接口
        for asn_id in self.ids:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            need_send_sap=False
            for asn_line_rec in asn_rec.line_ids:
                if asn_line_rec.asn_qty-asn_line_rec.cancel_qty>0.000001:
                    need_send_sap=True
                    break
                #调用接口
            if need_send_sap==True:
                self.push_to_sap_asn_002()
                if self.state=='sap_ok':
                    #调用接口成功的情况下,更新odoo端的数量
                    for asn_rec in self:
                        for asn_line_rec in asn_rec.line_ids:
                            asn_line_rec.apply_with_cancel_qty()
        return result

    @api.multi
    def push_to_sap(self):
        """
        提供action 菜单对需要同步的数据进行同步
        :return:
        """
        #批量调用接口同步数据到SAP系统
        for asn_id in self.ids:
            asn_rec=self.env["iac.asn"].browse(asn_id)

            # 卡控如果是刚刚创建的ASN就不能在MM cancel这个菜单中送SAP
            if asn_rec.state == 'sap_fail':
                cancel_item_flag = 0
                for asn_lines in asn_rec.line_ids:
                    if asn_lines.asn_qty != asn_lines.cancel_qty:
                        cancel_item_flag += 1
                        break
                if cancel_item_flag == 0:
                    raise UserError(u'当前ASN是创建时失败的asn,无法在此按钮送SAP,请回到ASN List菜单中送SAP！')

            asn_rec.push_to_sap_asn_002()

    @api.multi
    def sap_fail_cancel(self):
        """
        对sap_fail 状态的数据，odoo侧不调用sap接口，直接返回最大可交量
        :return:
        """
        for asn_id in self.ids:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            if asn_rec.state!='sap_fail':
                raise UserError("Only in state sap_fail can do this")

        #校验完成后,进行遍历cancel 所有asn条目
        for asn_id in self.ids:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            for asn_line in asn_rec.line_ids:
                asn_vals={
                    "vendor_id":asn_rec.vendor_id.id,
                    "plant_id":asn_rec.plant_id.id,
                    "part_id":asn_line.part_id.id,
                    "part_no":asn_line.part_id.part_no,
                    "asn_qty":asn_line.asn_qty,
                    }
                max_qty_rec=self.env["asn.maxqty"].return_asn_qty(asn_vals)
                asn_line.write({"asn_qty":0})
            asn_rec.write({"state":"odoo_cancel"})


class iacASNLineVendorCancel(models.Model):
    _name = 'iac.asn.line.vendor.cancel'
    _inherit = "iac.asn.line"
    _table="iac_asn_line"
    asn_id = fields.Many2one('iac.asn.vendor.cancel','ASN')

    @api.multi
    def write(self,vals):
        result=super(iacASNLineVendorCancel,self).write_with_cancel_qty_check(vals)
        return result

class iacASNVendorCreateWizardVendor(models.TransientModel):
    _name = "iac.asn.vendor.create.wizard"
    _description = u"asn create wizard"

    vendor_id = fields.Many2one('iac.vendor','Vendor',required=True)
    po_lst = fields.Text('PO No. list')
    part_lst = fields.Text('Part No. list')
    date_from = fields.Date('Date from')
    date_to = fields.Date('Date to')
    storage_location_id = fields.Many2one('iac.storage.location.address', string='Storage Location')

    @api.onchange('vendor_id')
    def _onchange_vendor_id_location(self):
        if self.vendor_id:
            return {'domain':{'storage_location_id':[('plant','=',self.vendor_id.plant.plant_code)]}}

    @api.multi
    def action_confirm(self):
        domain = [('state','in',['vendor_confirmed','wait_vendor_confirm','vendor_exception']),('vendor_id','=',self.vendor_id.id)]
        if self.po_lst:
            po_list = self.po_lst.split('\n')
            new_po_list=[]
            for item in po_list:
                new_po_list.append(item.strip())

            domain += [('name','in',new_po_list)]

        if self.date_from:
            domain += [('order_date','>=',self.date_from)]
        if self.date_to:
            domain += [('order_date','<=',self.date_to)]
            #增加buyer_id_list 条件

        #domain += [('buyer_id','in',self.env.user.buyer_id_list)]
        domain += [('approve_flag','=',True)]
        domain += [('state','not in',['to_approve'])]
        # 191105 ning add 增加storage location的查询条件
        domain += [('storage_location_id', '=', self.storage_location_id.id)]
        order_list = self.env['iac.purchase.order'].search(domain)


        #再次搜索po line
        domain = [('order_id','in',order_list.ids)]
        domain+=[('odoo_deletion_flag','=',False)]
        if self.part_lst:
            part_list = self.part_lst.split('\n')
            new_part_list=[]
            for part_no in part_list:
                new_part_list.append(part_no.strip())
            domain += [('part_no','in',new_part_list)]
        order_line_list = self.env['iac.purchase.order.line'].search(domain)

        po_line_ids=[]
        for po_line in order_line_list:
            if po_line.plant_id.plant_code=='CP22' and po_line.state in ['wait_vendor_confirm','vendor_exception']:
               continue
            #gr_qty>po_line quantity 的情况不能开
            if po_line.gr_qty>=po_line.quantity :
                continue
            if po_line.open_qty>0 :
                po_line_ids.append(po_line.id)
                #po_line.write({"new_asn_qty":0})
                po_line.with_context(state_change=True).write({"new_asn_qty":po_line.open_qty})
        self.env.cr.commit()
        if len(po_line_ids)==0:
            raise UserError('No Record found !')
        action = {
            'name': 'PO Line',
            'type': 'ir.actions.act_window',
            'res_model': 'iac.purchase.order.line.vendor',
            'view_mode': 'tree',
            'view_type': 'form',
            'view_id':  self.env.ref('oscg_rfq.view_po_line_list').id,
            'search_view_id': self.env.ref("oscg_rfq.view_po_line_search").id,
            'domain': [('id','in',po_line_ids)],

            }
        return action