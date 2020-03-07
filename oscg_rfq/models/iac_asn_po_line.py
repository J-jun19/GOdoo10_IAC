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

class IacPoItem(models.Model):
    _inherit = "iac.purchase.order.line.asn"


    # 废弃字段 to open_qty
    remain = fields.Integer(string='Remain Qty')
    material_id = fields.Many2one('material.master', string="Material")
    currency=fields.Char('Currency',related="order_id.currency")

    @api.multi
    def create_asn(self,create_mode='buyer_create'):
        """
        对一批po_line 开asn
        对选定的po_line 进行分组,按照 plant_id vendor_id storage_location 分组
        分组相同的情况下,可以开到一个asn下面
        :return:
        """

        #判断 storage_location 分组是否唯一
        groups = []
        plant_id=0
        vendor_id=0
        #检查两个相同的料开在一个asn里
        #存放唯一的厂商加料号
        header_list = []
        #存放对应的数量
        qty_list = []
        for item in self:
            ven_id = item.order_id.vendor_id.id
            part_id = item.part_id.id
            vendor_code = item.order_id.vendor_id.vendor_code
            part_no = item.part_id.part_no
            buyer_id = item.part_id.buyer_code_id.id
            qty = item.new_asn_qty
            pla_id = item.order_id.vendor_id.plant.id
            part_type = item.part_id.part_type
            header_id = str(ven_id)+','+str(buyer_id)+','+str(part_id)+','+str(vendor_code)+','+str(part_no)+','+str(pla_id)
            #CP22和TP02的不判断
            if pla_id != 28 and pla_id != 41 and pla_id != 51:
                #part_type是ZROH的要卡控可交量
                if part_type == 'ZROH':
                    if header_id not in header_list:
                        header_list.append(header_id)
                        qty_list.append(qty)
                    else:
                        index = header_list.index(header_id)
                        qty_list[index] = qty+qty_list[index]

        if len(header_list)>0:
            for i in range(len(header_list)):
                flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(int((header_list[i].split(','))[0]), int((header_list[i].split(','))[1]), int((header_list[i].split(','))[2]),
                                                                           (header_list[i].split(','))[3], (header_list[i].split(','))[4],int((header_list[i].split(','))[5]))
                if flag == False:
                    continue
                else:
                    if qty_list[i]>max_qty:
                        err_msg = u"最大可交量不足,同一颗料数量累加,ASN数量为( %s ),最大可交量为( %s ),vendor_code 是 ( %s );part_no 是 ( %s )" % (qty_list[i], max_qty,(header_list[i].split(','))[3],(header_list[i].split(','))[4])
                        raise UserError(err_msg)

        for po_line in self:
            groups.append(po_line.storage_location)
            plant_id=po_line.order_id.vendor_id.plant.id
            vendor_id=po_line.order_id.vendor_id.id

        groups = list(set(groups))
        if len(groups)>1:
            raise UserError(u"storage_location 不唯一!无法继续创建ASN")

        asn_id_list=[]

        #每个分组独立创建一个asn表头
        cur_time=datetime.now()
        to_time=cur_time+timedelta(days=1)
        self.eta_date=to_time.date()
        asn_vals={
            'create_mode':create_mode,
            'plant_id': plant_id,
            'vendor_id': vendor_id,
            'storage_location': groups[0],
            'etd_date':cur_time.date(),
            'delivery_days':1,
            'eta_date':to_time.date()
        }

        asn = self.env['iac.asn'].create(asn_vals)

        for po_line in self:
            if po_line.new_asn_qty<=0:
                memo=u"开立ASN的数量必须大于0,开立ASN的数量是 ( %s );OPEN QTY 是 ( %s );PO NO 是( %s );PO Line NO 是( %s )"% \
                     (po_line.new_asn_qty,po_line.quantity-po_line.asn_qty,po_line.order_id.document_erp_id,po_line.document_line_erp_id)
                raise UserError(memo)
            if po_line.new_asn_qty>( po_line.quantity-po_line.asn_qty):
                memo=u"开立ASN的数量不能大于订单行的OPEN QTY,开立ASN的数量是 ( %s );OPEN QTY 是 ( %s );PO NO 是( %s );PO Line NO 是( %s )"%\
                     (po_line.new_asn_qty,po_line.quantity-po_line.asn_qty,po_line.order_id.document_erp_id,po_line.document_line_erp_id)
                raise UserError(memo)
            vals = {
                'asn_id': asn.id,
                'asn_no':asn.asn_no,
                'po_id': po_line.order_id.id,
                'part_id': po_line.part_id.id,
                'asn_qty': po_line.new_asn_qty,
                'cancel_qty': po_line.new_asn_qty,
                'storage_location': po_line.storage_location,
                'po_line_id': po_line.id,
                'vendor_id':po_line.order_id.vendor_id.id,
                'plant_id':po_line.order_id.plant_id.id,
                'buyer_id':po_line.order_id.buyer_id.id,
                'vendor_code_sap':po_line.order_id.vendor_id.vendor_code,
                'buyer_erp_id':po_line.order_id.buyer_erp_id,
                'po_code':po_line.order_id.document_erp_id,
                'po_line_code':po_line.document_line_erp_id,
                'plant_code':po_line.order_id.plant_id.plant_code
                }
            self.env['iac.asn.line'].create_with_max_qty_check(vals)
            po_line.with_context(state_change=True).write({"new_asn_qty":0})

        #同步数据到SAP系统
        asn.push_to_sap_asn_001()

        if create_mode=='buyer_create':
            action = self.env.ref('oscg_rfq.action_iac_asn_buyer_change')
            action_window={
                'name': action.name,
                'help': action.help,
                'type': action.type,
                'view_type': action.view_type,
                'view_mode': 'form',
                'res_model': action.res_model,
                'res_id':asn.id,
                'context':{
                    'no_send_sap':True,
                },
                'view_id':self.env.ref('oscg_rfq.view_iac_asn_buyer_change_form').id,
                }
            return action_window

        elif create_mode=='vendor_create':
            vals = {
                'action_type': 'Vendor Create ASN',
                'vendor_id':vendor_id
            }
            self.env['iac.supplier.key.action.log'].create(vals)
            self.env.cr.commit()
            action = self.env.ref('oscg_rfq.action_iac_asn_vendor_change')
            action_window={
                'name': action.name,
                'help': action.help,
                'type': action.type,
                'view_type': action.view_type,
                'view_mode': 'form',
                'res_model': action.res_model,
                'res_id':asn.id,
                'context':{
                    'no_send_sap':True,
                    },
                'view_id':self.env.ref('oscg_rfq.view_iac_asn_vendor_change_form').id,
                }
            return action_window
        #不符合2的返回默认视图
        action_window={
                'type': 'ir.actions.act_window',
                'name': 'ASN Created',
                'view_mode': 'tree,form',
                'res_model':'iac.asn'
            }
        return action_window

class IacPoItemBuyer(models.Model):
    _name='iac.purchase.order.line.buyer'
    _inherit = "iac.purchase.order.line.asn"
    _table="iac_purchase_order_line"

    @api.multi
    def create_asn(self):
        action= super(IacPoItemBuyer,self).create_asn('buyer_create')
        return action


class IacPoItemVendor(models.Model):
    _name = "iac.purchase.order.line.vendor"
    _inherit = "iac.purchase.order.line.asn"
    _table="iac_purchase_order_line"

    @api.multi
    def create_asn(self):
        action= super(IacPoItemVendor,self).create_asn('vendor_create')
        return action
