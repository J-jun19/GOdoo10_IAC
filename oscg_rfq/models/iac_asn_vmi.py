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


class iacASN(models.Model):
    _inherit = 'iac.asn'
    vmi_asn_id = fields.Many2one('iac.asn.vmi','VMI ASN')

class iacASNLine(models.Model):
    _inherit = 'iac.asn.line'
    vmi_asn_line_id = fields.Many2one('iac.asn.line.vmi','VMI ASN Line')
    vmi_asn_id = fields.Many2one('iac.asn.vmi','VMI ASN')

class IacAsnVmi(models.Model):
    _name = "iac.asn.vmi"
    _order = "id desc"

    plant_id = fields.Char('Plant Code From SAP')
    vmi_code = fields.Char("VMI CODE")
    pull_signal_id = fields.Char("PULL_SIGNAL_ID")
    item_counts = fields.Char("ITEM_COUNTS")
    owner = fields.Char("OWNER")
    item = fields.Text("ITEM")
    state = fields.Selection([('draft','Draft'),
                              ('done','Done'),
                              ('validate_success','Validate Success'),
                              ('validate_fail','Validate Fail'),
                              ('rule_fail','Rule Fail'),
                              ('rule_success','Rule Success'),
                              ('asn_create_fail','Asn Create Fail'),
                              ('asn_create_success','Asn Create Success'),
                              ('sap_fail','Send SAP Fail')
                             ],default='draft',string='status')
    note = fields.Text('Text')
    asn_id = fields.Many2one('iac.asn',string='ASN')
    line_ids = fields.One2many('iac.asn.line.vmi','vmi_asn_id','Lines')
    vendor_id = fields.Many2one('iac.vendor',string='Vendor Info')
    odoo_plant_id = fields.Many2one('pur.org.data',string='Plant Info')
    err_msg = fields.Text('Error Message')
    sap_flag=fields.Selection([('Y','YES'),('N','NO')],string="Send To SAP Flag",default="N")
    storage_location = fields.Char('Storage location')
    ep_status = fields.Char('EP Status')
    id = fields.Char('ID')
    create_date = fields.Datetime('Create Time')


    @api.model
    def load_vmi_asn_data(self):
        """
        调用SAP接口获取ASN VMI 数据
        :return:
        """
        rpc_result, rpc_json_data = self.env['iac.asn'].sap_rpc_get('ODOO_ASN_005')

        #测试数据
        #rpc_result=True
        #rpc_json_object={
        #    "Message" : {
        #        "Status" : "Y",
        #        "Message" : ""
        #    },
        #    "Document" : {
        #        "HEADER" : [ {
        #                         "PLANT_ID" : "CP21",
        #                         "VMI_CODE" : "B",
        #                         "PULL_SIGNAL_ID" : "B380077170905",
        #                         "ITEM_COUNTS" : "1",
        #                         "OWNER" : "IAC",
        #                         "ITEM" : [ {
        #                                        "PS_ITEM" : "10",
        #                                        "VENDOR_ERP_ID" : "380077",
        #                                        "PO_NO" : "4501154752",
        #                                        "PO_ITEM" : "00010",
        #                                        "PART_NO" : "111BRB224106",
        #                                        "PULL_QTY" : "10",
        #                                        "MEINS" : "EA"
        #                                    }]
        #                     } ]
        #    }
        #}
        #rpc_json_data={}
        #rpc_json_data["rpc_callback_data"]=rpc_json_data

        if rpc_result:
            # 记录本次资料的所有vendor
            vendor_list = []
            asn_list = rpc_json_data.get("rpc_callback_data").get('Document').get('HEADER')
            for vals in asn_list:
                last_asn_vmi=self.env["iac.asn.vmi"].search([('pull_signal_id','=',vals.get('PULL_SIGNAL_ID'))])
                #判断是否已经存在asn,已经存在的情况下,退出当前循环
                if last_asn_vmi.exists():
                    continue
                vmi_asn_vals={
                    "plant_id":vals["PLANT_ID"],
                    "vmi_code":vals["VMI_CODE"],
                    "pull_signal_id":vals["PULL_SIGNAL_ID"],
                    "item_counts":vals["ITEM_COUNTS"],
                    "owner":vals["OWNER"],
                }
                line_ids = []


                for item in vals.get('ITEM'):
                    po_item=str(int(item.get("PO_ITEM")))
                    po_item=po_item.zfill(5)
                    vendor_list.append(item.get("VENDOR_ERP_ID"))
                    item_vals={
                        "ps_item":	item.get("PS_ITEM")	,
                        "vendor_erp_id":	item.get("VENDOR_ERP_ID")	,
                        "po_no":	item.get("PO_NO")	,
                        "po_item":	po_item	,
                        "part_no":	item.get("PART_NO")	,
                        "pull_qty":	item.get("PULL_QTY")	,
                        "meins":	item.get("MEINS")	,

                    }
                    line_ids += [(0,0,item_vals)]
                vmi_asn_vals['line_ids'] = line_ids

                self.env["iac.asn.vmi"].create(vmi_asn_vals)
                self.env.cr.commit()

            # 筛选掉重复vendor
            vendor_list = list(set(vendor_list))
            for vendor_code in vendor_list:
                vendor_id = self.env['iac.vendor'].search([('vendor_code', '=', vendor_code)]).id
                self._cr.execute(
                    "insert into iac_supplier_key_action_log(action_type,vendor_id,create_date,write_date) values(%s,%s,%s,%s)",
                    ('Vendor Create ASN', vendor_id, datetime.now(), datetime.now()))
                self.env.cr.commit()

    @api.model
    def validate_data(self):
        """
        校验数据,补充关键字段
        :return:
        """
        #处理没有补充关键字段的asn vmi
        asn_vmis=self.env["iac.asn.vmi"].search([('state','in',['draft','validate_fail']),('sap_flag','=','N')])
        for asn_vmi in asn_vmis:
            plant_id = self.env['pur.org.data'].search([('plant_code','=',asn_vmi.plant_id)],limit=1)
            err_msg_list=[]
            storage_location=False
            #排除异常信息
            if not plant_id.exists():
                err_msg="plant_code dose not exits (%s)" %(asn_vmi.plant_id,)
                err_msg_list.append(err_msg)
                asn_vmi.write({
                    "state":"validate_fail",
                    "err_msg":err_msg,
                    })
                continue

            asn_vmi.write({
                "odoo_plant_id":plant_id.id,
                })
            self.env.cr.commit()


            #遍历所有的子条目更新关键字段
            odoo_vendor_id=False
            for asn_vmi_line in asn_vmi.line_ids:
                line_err_msg_list=[]
                part_id=self.env["material.master"].search([('part_no','=',asn_vmi_line.part_no),('plant_id','=',plant_id.id)],limit=1)
                #排除异常信息
                if not part_id.exists():
                    err_msg="part_no dose not exits (%s)" %(asn_vmi_line.part_no,)
                    line_err_msg_list.append(err_msg)

                local_vendor_id=self.env["iac.vendor"].search([('vendor_code','=',asn_vmi_line.vendor_erp_id)],limit=1)
                #排除异常信息
                if not local_vendor_id.exists():
                    err_msg="vendor code dose not exits (%s)" %(asn_vmi_line.vendor_erp_id,)
                    line_err_msg_list.append(err_msg)

                po_id=self.env["iac.purchase.order"].search([('document_erp_id','=',asn_vmi_line.po_no)],limit=1)
                #排除异常信息
                #if not po_id.exists():
                #    err_msg="order code dose not exits (%s)" %(asn_vmi_line.po_no,)
                #    line_err_msg_list.append(err_msg)
#
                #po_line_id=self.env["iac.purchase.order.line"].search([('document_erp_id','=',asn_vmi_line.po_no),('document_line_erp_id','=',asn_vmi_line.po_item)],limit=1)
                ##排除异常信息
                #if not po_line_id.exists():
                #    err_msg="order item code dose not exits (%s)" %(asn_vmi_line.po_item,)
                #    line_err_msg_list.append(err_msg)


                if not po_id.exists():
                    err_msg="order code dose not exits (%s)" %(asn_vmi_line.po_no,)
                    line_err_msg_list.append(err_msg)
                else:
                    if po_id.approve_flag==False:
                        err_msg="approve_flag is not true"
                        line_err_msg_list.append(err_msg)
                    if po_id.state in ['to_approve']:
                        err_msg="po is not in valid state"
                        line_err_msg_list.append(err_msg)
                po_line_id=self.env["iac.purchase.order.line"].search([('document_erp_id','=',asn_vmi_line.po_no),('order_line_code','=',asn_vmi_line.po_item)],limit=1)

                #排除异常信息
                if not po_line_id.exists():
                    err_msg="order item code dose not exits,PO NO is (%s), PO Line No is ( %s ) " %(asn_vmi_line.po_no,asn_vmi_line.po_item)
                    line_err_msg_list.append(err_msg)
                else:
                    if po_line_id.odoo_deletion_flag==True:
                        err_msg="order item code is deleted,PO NO is (%s), PO Line No is ( %s ) " %(asn_vmi_line.po_no,asn_vmi_line.po_item)
                        line_err_msg_list.append(err_msg)
                    if po_id.plant_id.plant_code=='CP22' and po_line_id.state in ['wait_vendor_confirm','vendor_exception']:
                        err_msg="order item code is not confirmed,PO NO is (%s), PO Line No is ( %s ) " %(asn_vmi_line.po_no,asn_vmi_line.po_item)
                        line_err_msg_list.append(err_msg)
                #异常信息记录之后
                if len(line_err_msg_list)>0:
                    line_vals={
                        "state":"validate_fail",
                        "ERROR_MESSAGE":line_err_msg_list,
                        }
                    asn_vmi_line.write(line_vals)
                    err_msg_list+=line_err_msg_list
                    continue

                #校验没有发生异常的情况下
                line_vals={
                    "state":"validate_success",
                    "vendor_id":local_vendor_id.id,
                    "plant_id":plant_id.id,
                    "po_id":po_id.id,
                    "po_line_id":po_line_id.id,
                    "part_id":part_id.id,
                    "storage_location":po_line_id.storage_location,
                    }
                storage_location=po_line_id.storage_location
                odoo_vendor_id=local_vendor_id.id
                asn_vmi_line.write(line_vals)
                self.env.cr.commit()
                err_msg_list+=line_err_msg_list

            #判断在vmi asn的条目中是否有异常
            if len(err_msg_list)>0:
                asn_vmi_vals={
                    "state":"validate_fail",
                    "err_msg":err_msg_list,
                    }
                asn_vmi.write(asn_vmi_vals)
            else:
                asn_vmi_vals={
                    "vendor_id":odoo_vendor_id,
                    "state":"validate_success",
                    "storage_location":storage_location,
                    }
                asn_vmi.write(asn_vmi_vals)
            self.env.cr.commit()

        # ning add 191118 同一颗料数量累加判断可交量是否满足
        for asn_vmi in asn_vmis:
            # 存放唯一的厂商加料号
            header_list = []
            # 存放对应的数量
            qty_list = []
            for asn_vmi_line in asn_vmi.line_ids:
                vendor_id = asn_vmi_line.vendor_id.id
                part_id = asn_vmi_line.part_id.id
                vendor_code = asn_vmi_line.vendor_id.vendor_code
                part_no = asn_vmi_line.part_id.part_no
                buyer_id = asn_vmi_line.part_id.buyer_code_id.id
                qty = int(float(asn_vmi_line.pull_qty))
                plant_id = asn_vmi_line.plant_id.id
                part_type = asn_vmi_line.part_id.part_type
                header_id = str(vendor_id) + ',' + str(buyer_id) + ',' + str(part_id) + ',' + str(
                    vendor_code) + ',' + str(
                    part_no) + ',' + str(plant_id)
                # CP22和TP02的不判断
                if plant_id != 28 and plant_id != 41 and plant_id != 51:
                    # part_type是ZROH的要卡控可交量
                    if part_type == 'ZROH':
                        if header_id not in header_list:
                            header_list.append(header_id)
                            qty_list.append(qty)
                        else:
                            index = header_list.index(header_id)
                            qty_list[index] = qty + qty_list[index]

            if len(header_list) > 0:
                for i in range(len(header_list)):
                    try:
                        flag, max_qty, max_qty_id = self.env["asn.jitrule"].kakong(int((header_list[i].split(','))[0]),
                                                                                   int((header_list[i].split(','))[1]),
                                                                                   int((header_list[i].split(','))[2]),
                                                                                   (header_list[i].split(','))[3],
                                                                                   (header_list[i].split(','))[4],
                                                                                   int((header_list[i].split(','))[5]))
                        if flag == False:
                            continue
                        else:
                            if qty_list[i] > max_qty:
                                err_msg = u"最大可交量不足,同一颗料数量累加,ASN数量为( %s ),最大可交量为( %s ),vendor_code 是 ( %s );part_no 是 ( %s )" % (
                                qty_list[i], max_qty, (header_list[i].split(','))[3], (header_list[i].split(','))[4])
                                line_vals = {
                                    "state": "validate_fail",
                                    "error_message": err_msg,
                                }

                                for asn_vmi_line in asn_vmi.line_ids:
                                    if asn_vmi_line.part_no == (header_list[i].split(','))[4]:
                                        asn_vmi_line.write(line_vals)
                                asn_vmi_vals = {
                                    "state": "validate_fail",
                                    "err_msg": err_msg,
                                }
                                asn_vmi.write(asn_vmi_vals)
                    except:
                        # 保存状态信息
                        l_err_msg = traceback.format_exc()
                        try:
                            error_msg = str(traceback.format_exc()).split('UserError:')[1]
                        except:
                            error_msg = l_err_msg
                        line_vals = {
                            "state": "validate_fail",
                            "error_message": error_msg,
                        }

                        for asn_vmi_line in asn_vmi.line_ids:
                            if asn_vmi_line.part_no == (header_list[i].split(','))[4]:
                                asn_vmi_line.write(line_vals)
                        asn_vmi_vals = {
                            "state": "validate_fail",
                            "err_msg": error_msg,
                        }
                        asn_vmi.write(asn_vmi_vals)
        self.env.cr.commit()

    @api.model
    def validate_rule(self):
        """
        进行业务规则校验,目前只校验asn中的storage_location
        """
        asn_vmis=self.env["iac.asn.vmi"].search([('state','in',['validate_success',]),('sap_flag','=','N')])
        for asn_vmi in asn_vmis:

            #校验 storage_location
            storage_locations = []
            for asn_vmi_line in asn_vmi.line_ids:
                storage_locations += [asn_vmi_line.storage_location]
            if len(set(storage_locations)) > 1:
                asn_vmi_vals={
                    "state":"rule_fail",
                    "err_msg":"Storage Location is different",
                    }
                asn_vmi.write(asn_vmi_vals)
                continue
            asn_vmi.write({
                "storage_location":storage_locations[0],
                "state":"rule_success",
                })
        self.env.cr.commit()


    @api.model
    def create_asn(self):
        """
        对业务校验通过的数据进行创建asn操作
        :return:
        """
        #业务校验完成的情况下，对业务校验的通过的数据进行创建asn工作
        asn_vmis=self.env["iac.asn.vmi"].search([('state','in',['rule_success','asn_create_fail',]),('sap_flag','=','N')])
        for asn_vmi in asn_vmis:
            asn_vals={
                "vmi_asn_id":asn_vmi.id,
                "plant_id":asn_vmi.odoo_plant_id.id,
                "vendor_id":asn_vmi.vendor_id.id,
                "customer_country":asn_vmi.vendor_id.bank_country.id,
                "customer_currency":asn_vmi.vendor_id.currency.id,
                "storage_location":asn_vmi.storage_location,
                "create_mode":"auto_create"
                #"buyer_erp_id":asn_vmi.part_id.buyer_code,
            }
            #遍历 vmi asn 的条目,所有条目必须都成功才提交
            asn_result=self.env["iac.asn"].create(asn_vals)
            asn_vmi.write({"asn_id":asn_result.id})

            #遍历asn_vmi的条目,进行创建数据准备操作
            line_item_list = []
            for asn_vmi_line in asn_vmi.line_ids:
                #--buyer_code,plant_code,po_code,po_line_code,part_no
                line_vals={
                    "vendor_id":asn_vmi.vendor_id.id,
                    "part_id":asn_vmi_line.part_id.id,
                    "po_id":asn_vmi_line.po_id.id,
                    "po_line_id":asn_vmi_line.po_line_id.id,
                    "asn_qty":float(asn_vmi_line.pull_qty),
                    "storage_location":asn_vmi_line.storage_location,
                    "vmi_asn_id":asn_vmi.id,
                    "vmi_asn_line_id":asn_vmi_line.id,
                    "pull_signal_id":asn_vmi.pull_signal_id,
                    "asn_no":asn_result.asn_no,
                    "plant_id":asn_vmi_line.plant_id.id,
                    "buyer_id":asn_vmi_line.po_id.buyer_id.id,
                    "buyer_code":asn_vmi_line.po_id.buyer_id.buyer_erp_id,
                    "buyer_erp_id":asn_vmi_line.po_id.buyer_id.buyer_erp_id,
                    "plant_code":asn_vmi_line.plant_id.plant_code,
                    "po_code":asn_vmi_line.po_no,
                    "po_line_code":asn_vmi_line.po_item.zfill(5),
                    "part_no":asn_vmi_line.part_no,
                    "cancel_qty":float(asn_vmi_line.pull_qty),
                }
                line_item_list.append(line_vals)



            #存储创建asn条目的结果信息,key为vmi_asn_line_id
            asn_line_create_result={}
            asn_line_fail_result={}
            for asn_line_vals in line_item_list:
                try:
                    asn_line_vals["asn_id"]=asn_result.id
                    #判断po_line的open_qty是否符合条件,符合条件的才会开立asn
                    po_line_rec=self.env["iac.purchase.order.line"].browse(asn_line_vals.get("po_line_id"))

                    self.env.cr.execute("SELECT                                     " \
                                        "	o_gr_count,o_asn_count,o_open_count      " \
                                        "FROM                                       " \
                                        "	public.proc_po_part_info (              " \
                                        "		%s,                      " \
                                        "		%s,                      " \
                                        "		%s                       " \
                                        "	)                             ",
                                        (po_line_rec.order_id.id, po_line_rec.id,
                                         po_line_rec.part_id.id,))
                    gr_count=0
                    asn_count=0
                    open_count=0
                    part_result=self.env.cr.fetchall()

                    gr_count=part_result[0][0]
                    asn_count=part_result[0][1]
                    open_count=part_result[0][2]
                    if po_line_rec.exists() and open_count>=asn_line_vals.get("asn_qty"):
                        asn_line_rec=self.env["iac.asn.line"].create_with_max_qty_check(asn_line_vals)
                        asn_line_rec.vmi_asn_line_id.write({"state":"asn_create_success"})

                        #保存状态信息
                        asn_line_vals_2={
                            "asn_id":asn_result.id,
                            "asn_line_id":asn_line_rec.id,
                            'error_message':False,
                            "state":"asn_create_success",
                        }
                        #保存创建asn line 的创建结果信息
                        asn_line_create_result[asn_line_vals["vmi_asn_line_id"]]=asn_line_vals_2

                    else:
                        #保存状态信息
                        asn_line_vals_2={
                            "error_message":"asn_qty must less then open_qty,asn_qty is %s open qty is %s" %(asn_line_vals.get("asn_qty"),open_count),
                            "state":"asn_create_fail",
                            }
                        #保存创建asn line 的创建结果信息
                        asn_line_create_result[asn_line_vals["vmi_asn_line_id"]]=asn_line_vals_2
                        asn_line_fail_result[asn_line_vals["vmi_asn_line_id"]]=asn_line_vals_2

                except:
                    #保存状态信息
                    l_err_msg = traceback.format_exc()
                    try:
                        error_msg = str(traceback.format_exc()).split('UserError:')[1]
                    except:
                        error_msg = l_err_msg
                    asn_line_vals_2={
                        "error_message":error_msg,
                        "state":"asn_create_fail",
                        }
                    #保存创建asn line 的创建结果信息
                    asn_line_create_result[asn_line_vals["vmi_asn_line_id"]]=asn_line_vals_2
                    asn_line_fail_result[asn_line_vals["vmi_asn_line_id"]]=asn_line_vals_2
                    #开立asn line 出现异常,记录异常信息后，抛出异常让上层处理环节捕获
                    #vmi_asn_line_rec=self.env["iac.asn.line.vmi"].browse(asn_line_vals["vmi_asn_line_id"])
                    #vmi_asn_line_rec.write({"error_message":traceback.format_exc(),"state":"asn_create_fail"})

            #所有条目都没有创建成功的情况下回滚记录
            #if not asn_result.line_ids.exists():

            #只要存在开立失败的条目，那么立即回滚数据，记录错误日志信息
            if len(asn_line_fail_result)>0:
                self.env.cr.rollback()

                #所有条目都创建失败,header的状态为asn_create_fail
                asn_vmi.write({
                    "state":"asn_create_fail",
                    "ep_status":"F",
                    })
                self.env.cr.commit()

                #更新asn_line_vmi的失败状态信息
                for asn_line_id_vmi in asn_line_fail_result:
                    asn_line_vmi_rec=self.env["iac.asn.line.vmi"].browse(asn_line_id_vmi)
                    asn_line_vmi_vals=asn_line_fail_result.get(asn_line_id_vmi)
                    asn_line_vmi_rec.write(asn_line_vmi_vals)
                self.env.cr.commit()
            else:
                #更新asn_line_vmi的状态信息
                for asn_line_id_vmi in asn_line_create_result:
                    asn_line_vmi_rec=self.env["iac.asn.line.vmi"].browse(asn_line_id_vmi)
                    asn_line_vmi_vals=asn_line_create_result.get(asn_line_id_vmi)
                    asn_line_vmi_rec.write(asn_line_vmi_vals)
                self.env.cr.commit()

                #存在asn条目成功的情况下,判断是否存在失败的条目
                asn_line_fail=asn_vmi.line_ids.filtered(lambda x: x.state == 'asn_create_fail')
                if asn_line_fail.exists():
                    asn_vmi.write({
                        "state":"asn_create_fail",
                        "ep_status":"F",
                        })
                    self.env.cr.commit()
                else:
                    #所有条目都创建成功的情况下
                    asn_vmi.write(
                        {
                            "state":"asn_create_success",
                            "asn_id":asn_result.id,
                            "ep_status":"S",
                            "err_msg":False,
                            }
                    )
                    self.env.cr.commit()


    @api.model
    def send_vmi_asn_to_sap(self):
        """
        处理header 为 asn_create_fail 中的,detail 中为 asn_create_success 的状态,调用006 接口保持
        header状态不变
        :return:
        """
        asn_vmis=self.env["iac.asn.vmi"].search([('state','in',['asn_create_fail',]),('sap_flag','=','N')])
        for asn_vmi in asn_vmis:
            rpc_result=asn_vmi.sap_api_odoo_asn_006()
            #存在创建成功的asn的情况下,调用001接口
            asn_line_vmi_list=asn_vmi.line_ids.filtered(lambda x: x.state == 'asn_create_success')
            asn_id_list=[]
            for asn_line_vmi in asn_line_vmi_list:
                asn_id_list.append(asn_line_vmi.asn_id.id)
            asn_id_list=list(set(asn_id_list))

            for asn_id in asn_id_list:
                asn_rec=self.env["iac.asn"].browse(asn_id)
                asn_rec.push_to_sap_asn_001()
                #针对asn_line_vmi回写状态
                if asn_rec.state=='sap_ok':
                    asn_line_vmi=self.env["iac.asn.line.vmi"].search([('asn_id','=',asn_id)])
                    if asn_line_vmi.exists():
                        asn_line_vmi.write({"state":"done"})




        #数据处理过程完成之后,进行接口调用,包括调用sap系统失败的和刚创建asn成功的状态
        asn_vmis=self.env["iac.asn.vmi"].search([('state','in',['sap_fail','asn_create_success',]),('sap_flag','=','N')])
        for asn_vmi in asn_vmis:
            try:
                rpc_result=asn_vmi.sap_api_odoo_asn_006()
                if rpc_result==True:
                    asn_vmi.write({
                        "state":"done",
                        "sap_flag":"Y",
                    })
                else:
                    asn_vmi.write({
                        "state":"sap_fail",
                        "sap_flag":"N",
                    })

                #存在创建成功的asn的情况下,调用001接口
                asn_line_vmi_list=asn_vmi.line_ids.filtered(lambda x: x.state == 'asn_create_success')
                asn_id_list=[]
                for asn_line_vmi in asn_line_vmi_list:
                    asn_id_list.append(asn_line_vmi.asn_id.id)
                asn_id_list=list(set(asn_id_list))

                for asn_id in asn_id_list:
                    asn_rec=self.env["iac.asn"].browse(asn_id)
                    asn_rec.push_to_sap_asn_001()
                    #针对asn_line_vmi回写状态
                    if asn_rec.state=='sap_ok':
                        asn_line_vmi=self.env["iac.asn.line.vmi"].search([('asn_id','=',asn_id)])
                        if asn_line_vmi.exists():
                            asn_line_vmi.write({"state":"done"})

            except:
                traceback.print_exc()
                asn_vmi.write({
                        "state":"sap_fail",
                        "sap_flag":"N",
                    })


    @odoo_env
    @api.model
    def job_iac_asn_vmi(self):
        """
        处理vmi asn

        进行数据有效性校验
        对数据有效进行业务规则校验
        对通过业务规则校验的创建asn
        提交数据校验失败的、业务规则校验失败的、创建asn失败的进行提交到sap
        提交创建asn成功的进行提交到sap
        :return:
        """
        #获取vmi asn
        self.load_vmi_asn_data()

        #数据有效性校验
        self.validate_data()

        #业务规则校验
        self.validate_rule()

        #创建asn数据
        self.create_asn()

        #数据处理过程完成之后,进行接口调用,包括调用sap系统失败的和刚创建asn成功的状态
        self.send_vmi_asn_to_sap()



    def sap_api_odoo_asn_006(self):
        sequence = self.env['ir.sequence'].next_by_code('iac.interface.rpc')
        data = {
            "id": self.id,
            "biz_object_id": self.id,
            "odoo_key":sequence,
        }
        rpc_result, rpc_json_data, log_line_id, exception_log = self.env[
            'iac.interface.rpc'].invoke_web_call_with_log('ODOO_ASN_006', data)
        if not rpc_result:
            return False
        return True

class iacAsnLineVmi(models.Model):
    _name = "iac.asn.line.vmi"

    vmi_asn_id = fields.Many2one('iac.asn.vmi','PULL_SIGNAL_ID')
    ps_item = fields.Char("PS_ITEM")
    vendor_erp_id = fields.Char("VENDOR_ERP_ID")
    po_no = fields.Char("PO_NO")
    po_item = fields.Char("PO_ITEM")
    part_no = fields.Char("PART_NO")
    pull_qty = fields.Char("PULL_QTY")
    meins = fields.Char("MEINS")
    error_message = fields.Text('ERROR_MESSAGE')

    plant_id = fields.Many2one('pur.org.data',string='Plant Info')
    vendor_id = fields.Many2one('iac.vendor',string='Vendor Info')
    po_id = fields.Many2one('iac.purchase.order',string='PO Info')
    po_line_id = fields.Many2one('iac.purchase.order.line',string='PO Line Info')
    part_id = fields.Many2one('material.master',string='Material Info')
    state = fields.Selection([('draft','Draft'),
                          ('done','Done'),
                          ('validate_success','Validate Success'),
                          ('validate_fail','Validate Fail'),
                          ('rule_fail','Rule Fail'),
                          ('rule_success','Rule Success'),
                          ('asn_create_fail','Asn Create Fail'),
                          ('asn_create_success','Asn Create Success'),
                          ('sap_fail','Send SAP Fail')
                         ],default='draft',string='status')
    storage_location=fields.Char(string="Storage Location")
    asn_id = fields.Many2one('iac.asn',string='Asn Info')
    asn_line_id = fields.Many2one('iac.asn.line',string='Asn Line Info')
