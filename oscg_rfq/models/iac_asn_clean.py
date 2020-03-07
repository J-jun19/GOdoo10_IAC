# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api,odoo_env
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from functools import wraps
from odoo.odoo_env import odoo_env
import  traceback
import threading


class iacASNClean(models.Model):
    _name = "iac.asn.clean"
    _order = "id desc"

    delivery=fields.Char(string='SAP KEY')
    asn_no=fields.Char(string='ASN NO')
    asn_item=fields.Char(string='ASN ITEM NO')
    date=fields.Char(string='Date From SAP')
    flag=fields.Char(string='Flag')
    time=fields.Char(string='Time')
    part_no=fields.Char(string='Part No')
    plant_code=fields.Char(string='Plant Code')
    asn_qty = fields.Float('ASN QTY',digits=(18,4))
    reduce_qty=fields.Float(string='Reduce Qty',digits=(18,4))
    document_erp_id=fields.Char('PO Code')
    document_erp_line_no=fields.Char('PO Line Code')
    asn_id=fields.Many2one('iac.asn','ASN Info')
    asn_line_id=fields.Many2one('iac.asn.line','ASN Line Info')
    state=fields.Selection([('draft','Draft'),
                            ('valid_fail','Valid Fail'),
                            ('valid_success','Valid Success'),
                            ('fail','Fail'),
                            ('success','Success'),
                            ('sap_fail','SAP Fail')],string="Status",default='draft')
    err_msg=fields.Text(string='Error Message')
    id = fields.Char('ID')
    create_date = fields.Datetime('Create Time')

    @api.model
    def asn_clean_to_sap(self,asn_id,asn_clean_id_list):
        """
        传入一个asn_id,首先修改asn_line 中的cancel_qty 数量
        ,然后再告知SAP系统,SAP调用完成后，根据SAP反馈进行处理
        :return:
        """
        asn_rec=self.env["iac.asn"].browse(asn_id)
        #根据asn_clean 中的记录修改数量
        asn_clean_fail_id_list=[]
        for asn_clean_id in asn_clean_id_list:
            try:
                asn_clean_rec=self.env["iac.asn.clean"].browse(asn_clean_id)
                asn_clean_rec.asn_line_id.cancel_qty=asn_clean_rec.reduce_qty
            except:
                asn_clean_vals={
                    "state":"fail",
                    "err_msg":traceback.format_exc()
                }
                asn_clean_rec.write(asn_clean_vals)
                asn_clean_fail_id_list.append(asn_clean_id)
                traceback.print_exc()


        asn_rec.push_to_sap_asn_002()
        if asn_rec.state=='sap_ok':
            for asn_clean_id in asn_clean_id_list:
                #不包含失败的记录
                if asn_clean_id in asn_clean_fail_id_list:
                    continue
                try:
                    #调用sap成功的情况下,应用cancel_qty 到真实的数量
                    asn_clean_rec.asn_line_id.apply_with_cancel_qty()
                    asn_clean_rec=self.env["iac.asn.clean"].browse(asn_clean_id)
                    asn_clean_vals={
                        "state":"success",
                        "err_msg":False
                    }
                    asn_clean_rec.write(asn_clean_vals)
                except:
                    asn_clean_vals={
                        "state":"fail",
                        "err_msg":traceback.format_exc()
                    }
                    asn_clean_rec.write(asn_clean_vals)
        else:
            for asn_clean_id in asn_clean_id_list:
                #不包含失败的记录
                if asn_clean_id in asn_clean_fail_id_list:
                    continue
                asn_clean_rec=self.env["iac.asn.clean"].browse(asn_clean_id)
                asn_clean_vals={
                    "state":"sap_fail",
                    "err_msg":False
                }
                asn_clean_rec.write(asn_clean_vals)

    @api.model
    def send_asn_list_to_sap(self,asn_id_list=[]):
        for asn_id in asn_id_list:
            asn_rec=self.env["iac.asn"].browse(asn_id)
            need_send_sap=False
            #只要存在需要cancel_qty的记录就跳出
            for asn_line_rec in asn_rec.line_ids:
                if asn_line_rec.asn_qty-asn_line_rec.cancel_qty>0.000001:
                    need_send_sap=True
                    break
                    #调用接口
            if need_send_sap==True:
                asn_rec.push_to_sap_asn_002()
                if asn_rec.state=='sap_ok':
                    #调用接口成功的情况下,更新odoo端的数量
                    for asn_line_rec in asn_rec.line_ids:
                        try:
                            asn_line_rec.apply_with_cancel_qty()
                        except:
                            err_msg=traceback.format_exc()
                    #更细iac_asn_clean中的状态
                    asn_clean=self.env["iac.asn.clean"].search([('asn_id','=',asn_id),('state','in',['draft','fail'])])
                    asn_clean.write({"state":"success"})
                else:
                    #更新iac_asn_clean中的状态
                    asn_clean=self.env["iac.asn.clean"].search([('asn_id','=',asn_id),('state','in',['draft','fail'])])
                    asn_clean.write({"state":"success"})



    @odoo_env
    @api.model
    def job_iac_asn_clean(self):
        """
        从SAP系统接口获取需要清理的ASN
        :return:
        """

        rpc_result, rpc_json_data = self.env['iac.asn'].sap_rpc_get('ODOO_ASN_003')
        if rpc_result==False:
            return

        item_list = rpc_json_data.get("rpc_callback_data").get('Document').get('ITEM')
        #key为asn_id value 为 asn_clean_id 列表
        asn_clean_map={}
        asn_id_list=[]
        for item_vals in item_list:
            asn_item=str(int(item_vals.get('ASN_ITEM')))
            self.env.cr.execute("""select id from iac_asn_clean where asn_no=%s and asn_item=%s order by id limit 1""",
                (item_vals.get('ASN_NO'),asn_item))
            pg_result=self.env.cr.fetchall()
            #判断记录是否存在
            asn_clean_rec=None
            if len(pg_result)>0:
                 asn_clean_rec=self.env['iac.asn.clean'].browse(pg_result[0][0])
            else:
                #创建ASN Clean 日志
                asn_clean_vals={
                    "delivery":item_vals.get('DELIVERY'),
                    "asn_no":item_vals.get('ASN_NO'),
                    "asn_item":asn_item,
                    "date":item_vals.get('DATE'),
                    "flag":item_vals.get('FLAG'),
                    "time":item_vals.get('TIME'),
                    "part_no":item_vals.get('PART_NO'),
                    "plant_code":item_vals.get('PLANT_ID'),
                    "asn_qty":item_vals.get('ASN_QTY'),
                    "reduce_qty":item_vals.get('REDUCE_QTY'),
                    "document_erp_id":item_vals.get('DOCUMENT_ERP_ID'),
                    "document_erp_line_no":str(int(item_vals.get('DOCUMENT_ERP_LINE_NO'))),
                    }
                asn_clean_rec=self.env['iac.asn.clean'].create(asn_clean_vals)
                self.env.cr.commit()

            #填充asn_line_id
            asn_line_rec=self.env["iac.asn.line"].search([('asn_line_no','=',int(item_vals.get('ASN_ITEM'))),('asn_no','=',item_vals.get('ASN_NO'))])

            if not asn_line_rec.exists():
                asn_clean_rec.write({'state':'valid_fail','err_msg':"can not find asn"})
                self.env.cr.commit()
                continue

            #回写asn_id 和asn_line_id
            asn_clean_rec.write({'asn_id':asn_line_rec.asn_id.id,'asn_line_id':asn_line_rec.id})
            self.env.cr.commit()

            #增加校验只能减少asn_qty 数量不能增加,不符合标准的数据将被跳过
            if asn_clean_rec.asn_line_id.asn_qty<asn_clean_rec.reduce_qty:
                err_msg=u"ASN单号为( %s ),ASN Line NO 为( %s ), 修改的ASN数量不能大于已经开立的ASN数量" % (asn_clean_rec.asn_no,asn_clean_rec.asn_item)
                asn_clean_rec.write({'state':'valid_fail','err_msg':err_msg})
                self.env.cr.commit()
                continue

            #当前条目校验通过的情况下,需要重置状态
            asn_clean_rec.write({'state':'valid_success','err_msg':False})
            asn_id_list.append(asn_line_rec.asn_id.id)

            #填充asn_clean_map
            asn_id=asn_line_rec.asn_id.id
            if asn_id in asn_clean_map:
                asn_clean_list=asn_clean_map[asn_id]
                if asn_clean_rec.id not in asn_clean_list:
                    asn_clean_list.append(asn_clean_rec.id)
                asn_clean_map[asn_id]=asn_clean_list
            else:
                asn_clean_list=[]
                asn_clean_list.append(asn_clean_rec.id)
                asn_clean_map[asn_id]=asn_clean_list

            #调用接口修改asn_数量
            asn_id_list=list(set(asn_id_list))

        #遍历ASN 进行asn_canel处理
        for asn_id in asn_clean_map:
            asn_clean_list=asn_clean_map[asn_id]
            self.env["iac.asn.clean"].asn_clean_to_sap(asn_id,asn_clean_list)

        #对调用SAP系统失败的条目,重新调用SAP系统修改资料
        asn_clean=self.env["iac.asn.clean"].search([('state','in',['sap_fail'])])
        asn_id_list=[]
        asn_clean_map={}
        for asn_clean_id in asn_clean.ids:
            asn_id_list.append(asn_clean_rec.asn_id.id)
            if asn_id in asn_clean_map:
                asn_clean_list=asn_clean_map[asn_id]
                if asn_clean_rec.id not in asn_clean_list:
                    asn_clean_list.append(asn_clean_rec.id)
                asn_clean_map[asn_id]=asn_clean_list
            else:
                asn_clean_list=[]
                asn_clean_list.append(asn_clean_rec.id)
                asn_clean_map[asn_id]=asn_clean_list
        # #遍历ASN 进行asn_canel处理
        for asn_id in asn_clean_map:
            asn_clean_list=asn_clean_map[asn_id]
            self.env["iac.asn.clean"].asn_clean_to_sap(asn_id,asn_clean_list)

        return True



